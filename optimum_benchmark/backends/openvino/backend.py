import gc
import os
import inspect
from typing import Any, Dict
from logging import getLogger
from tempfile import TemporaryDirectory

import torch
from hydra.utils import get_class
from openvino.runtime import properties
from safetensors.torch import save_file
from optimum.intel.openvino import OVQuantizer
from transformers.modeling_utils import no_init_weights
from transformers.utils import ModelOutput
from transformers.utils.logging import set_verbosity_error
from optimum.intel.openvino import OVConfig as OVQuantizationConfig  # naming conflict

from ..base import Backend
from .config import OVConfig
from .utils import TASKS_TO_OVMODEL
from ...task_utils import TEXT_GENERATION_TASKS
from ..transformers_utils import randomize_weights
from ...generators.dataset_generator import DatasetGenerator


# disable transformers logging
set_verbosity_error()

LOGGER = getLogger("openvino")


class OVBackend(Backend[OVConfig]):
    NAME: str = "openvino"

    def __init__(self, config: OVConfig) -> None:
        super().__init__(config)
        self.validate_task()

        self.ovmodel_class = get_class(TASKS_TO_OVMODEL[self.config.task])
        LOGGER.info(f"\t+ Using OVModel class {self.ovmodel_class.__name__}")

        if self.config.inter_op_num_threads is not None:
            self.set_inter_op_num_threads()

        self.tmpdir = TemporaryDirectory()

        if self.config.quantization:
            if self.config.no_weights:
                self.load_automodel_with_no_weights()
            else:
                self.load_automodel_from_pretrained()
            original_export = self.config.export
            self.config.export = False
            self.quantize_automodel()
            self.load_ovmodel_from_pretrained()
            self.config.export = original_export
        elif self.config.no_weights:
            self.load_ovmodel_with_no_weights()
        else:
            self.load_ovmodel_from_pretrained()

        self.tmpdir.cleanup()

    def validate_task(self) -> None:
        if self.config.task not in TASKS_TO_OVMODEL:
            raise NotImplementedError(f"OVBackend does not support task {self.config.task}")

    def set_inter_op_num_threads(self) -> None:
        LOGGER.info(f"\t+ Setting inter_op_num_threads to {self.config.inter_op_num_threads}")
        self.config.openvino_config[properties.inference_num_threads()] = self.config.inter_op_num_threads

    def create_no_weights_model(self) -> None:
        LOGGER.info("\t+ Creating no weights model directory")
        self.no_weights_model = os.path.join(self.tmpdir.name, "no_weights")
        os.makedirs(self.no_weights_model, exist_ok=True)

        LOGGER.info("\t+ Saving pretrained config")
        self.pretrained_config.save_pretrained(save_directory=self.no_weights_model)

        LOGGER.info("\t+ Creating no weights model state dict")
        state_dict = torch.nn.Linear(1, 1).state_dict()

        LOGGER.info("\t+ Saving no weights model state dict")
        save_file(
            filename=os.path.join(self.no_weights_model, "model.safetensors"),
            metadata={"format": "pt"},
            tensors=state_dict,
        )

    def load_automodel_with_no_weights(self) -> None:
        self.create_no_weights_model()

        with no_init_weights():
            original_model = self.config.model
            self.config.model = self.no_weights_model
            LOGGER.info("\t+ Loading no weights model")
            self.load_automodel_from_pretrained()
            self.config.model = original_model

        LOGGER.info("\t+ Randomizing weights")
        randomize_weights(self.pretrained_model)
        LOGGER.info("\t+ Tying model weights")
        self.pretrained_model.tie_weights()

    def load_automodel_from_pretrained(self) -> None:
        self.pretrained_model = self.automodel_class.from_pretrained(self.config.model, **self.config.hub_kwargs)

    def load_ovmodel_with_no_weights(self) -> None:
        self.create_no_weights_model()

        with no_init_weights():
            original_model = self.config.model
            self.config.model = self.no_weights_model
            LOGGER.info("\t+ Loading OVModel with no weights")
            self.load_ovmodel_from_pretrained()
            self.config.model = original_model

    def load_ovmodel_from_pretrained(self) -> None:
        self.pretrained_model = self.ovmodel_class.from_pretrained(
            self.config.model,
            export=self.config.export,
            ov_config=self.config.openvino_config,
            **self.config.hub_kwargs,
            **self.ovmodel_kwargs,
        )

    @property
    def ovmodel_kwargs(self) -> Dict[str, Any]:
        kwargs = {}

        if self.config.task in TEXT_GENERATION_TASKS:
            kwargs["use_cache"] = self.config.use_cache
            kwargs["use_merged"] = self.config.use_merged

        return kwargs

    def quantize_automodel(self) -> None:
        LOGGER.info("\t+ Attempting quantization")
        quantized_model_path = f"{self.tmpdir.name}/quantized"
        LOGGER.info("\t+ Processing quantization config")
        quantization_config = OVQuantizationConfig(**self.config.quantization_config)
        LOGGER.info("\t+ Creating quantizer")
        quantizer = OVQuantizer.from_pretrained(self.pretrained_model, task=self.config.task, seed=self.config.seed)

        if self.config.calibration:
            LOGGER.info("\t+ Generating calibration dataset")
            dataset_shapes = {
                "dataset_size": 1,
                "sequence_length": 1,
                **self.model_shapes,
            }
            calibration_dataset = DatasetGenerator(task=self.config.task, dataset_shapes=dataset_shapes).generate()
            columns_to_be_removed = list(set(calibration_dataset.column_names) - set(quantizer._export_input_names))
            calibration_dataset = calibration_dataset.remove_columns(columns_to_be_removed)
        else:
            calibration_dataset = None

        LOGGER.info("\t+ Quantizing model")
        quantizer.quantize(
            save_directory=quantized_model_path,
            quantization_config=quantization_config,
            calibration_dataset=calibration_dataset,
            # TODO: add support for these (maybe)
            remove_unused_columns=True,
            data_collator=None,
            weights_only=False,
            file_name=None,
            batch_size=1,
        )
        self.config.model = quantized_model_path

    def prepare_for_inference(self, **kwargs) -> None:
        if self.config.reshape:
            static_shapes = {
                key: value
                for key, value in kwargs.items()
                if key in inspect.getfullargspec(self.pretrained_model.reshape).args
            }
            if (static_shapes.get("height", None) is not None) and ("sequence_length" in static_shapes):
                static_shapes["sequence_length"] = kwargs.get("num_channels", 3)

            LOGGER.info(f"\t+ Reshaping model with static shapes: {static_shapes}")
            self.pretrained_model.reshape(**static_shapes)

        if self.config.half:
            LOGGER.info("\t+ Converting model to half precision")
            self.pretrained_model.half()

        if self.config.reshape or self.config.half:
            LOGGER.info("\t+ Compiling model")
            self.pretrained_model.compile()

    def prepare_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if self.config.library == "diffusers":
            return {"prompt": inputs["prompt"]}

        return inputs

    def forward(self, inputs: Dict[str, Any], kwargs: Dict[str, Any]) -> ModelOutput:
        return self.pretrained_model(**inputs, **kwargs)

    def generate(self, inputs: Dict[str, Any], kwargs: Dict[str, Any]) -> ModelOutput:
        return self.pretrained_model.generate(**inputs, **kwargs)

    def clean(self) -> None:
        super().clean()

        if hasattr(self, "tmpdir"):
            self.tmpdir.cleanup()

        gc.collect()
