import inspect
from collections import OrderedDict
from tempfile import TemporaryDirectory
from typing import Any, Dict

import torch
from hydra.utils import get_class

from ...import_utils import is_accelerate_available, is_torch_distributed_available
from ..base import Backend
from ..transformers_utils import fast_weights_init
from .config import OVConfig as OVBackendConfig
from .utils import TASKS_OVPIPELINE, TASKS_TO_OVMODEL

if is_accelerate_available():
    from accelerate import Accelerator

if is_torch_distributed_available():
    import torch.distributed


class OVBackend(Backend[OVBackendConfig]):
    NAME: str = "openvino"

    def __init__(self, config: OVBackendConfig) -> None:
        super().__init__(config)

        if self.config.task in TASKS_TO_OVMODEL:
            self.ovmodel_class = get_class(TASKS_TO_OVMODEL[self.config.task])
            self.logger.info(f"\t+ Using OVModel class {self.ovmodel_class.__name__}")
        elif self.config.task in TASKS_OVPIPELINE:
            self.ovmodel_class = get_class(TASKS_OVPIPELINE[self.config.task])
            self.logger.info(f"\t+ Using OVDiffusionPipeline class {self.ovmodel_class.__name__}")
        else:
            raise NotImplementedError(f"OVBackend does not support task {self.config.task}")

    def load(self) -> None:
        self.logger.info("\t+ Creating backend temporary directory")
        self.tmpdir = TemporaryDirectory()

        if self.config.no_weights:
            self.logger.info("\t+ Creating no weights OVModel")
            self.create_no_weights_model()
            self.logger.info("\t+ Loading no weights OVModel")
            self._load_ovmodel_with_no_weights()
        else:
            self.logger.info("\t+ Loading pretrained OVModel")
            self._load_ovmodel_from_pretrained()

        if self.config.reshape:
            static_shapes = {
                key: value
                for key, value in self.model_shapes.items()
                if key in inspect.getfullargspec(self.pretrained_model.reshape).args
            }

            self.logger.info(f"\t+ Reshaping model with static shapes: {static_shapes}")
            self.pretrained_model.reshape(**static_shapes)

        if self.config.half:
            self.logger.info("\t+ Converting model to half precision")
            self.pretrained_model.half()

        if self.config.reshape or self.config.half:
            self.logger.info("\t+ Compiling model")
            self.pretrained_model.compile()

        self.tmpdir.cleanup()

    def _load_ovmodel_from_pretrained(self) -> None:
        self.pretrained_model = self.ovmodel_class.from_pretrained(
            self.config.model,
            **self.config.model_kwargs,
            **self.ovmodel_kwargs,
        )

    def _load_ovmodel_with_no_weights(self) -> None:
        with fast_weights_init():
            original_model, self.config.model = self.config.model, self.no_weights_model
            original_export, self.config.export = self.config.export, True
            self.logger.info("\t+ Loading no weights OVModel")
            self._load_ovmodel_from_pretrained()
            self.config.export = original_export
            self.config.model = original_model

    @property
    def ovmodel_kwargs(self) -> Dict[str, Any]:
        kwargs = {}

        if self.config.export is not None:
            kwargs["export"] = self.config.export

        if self.config.use_cache is not None:
            kwargs["use_cache"] = self.config.use_cache

        if self.config.use_merged is not None:
            kwargs["use_merged"] = self.config.use_merged

        if self.config.load_in_8bit is not None:
            kwargs["load_in_8bit"] = self.config.load_in_8bit

        if self.config.load_in_4bit is not None:
            kwargs["load_in_4bit"] = self.config.load_in_4bit

        return kwargs

    @property
    def split_between_processes(self) -> bool:
        return is_torch_distributed_available() and torch.distributed.is_initialized()

    def prepare_inputs_before_load(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if self.split_between_processes:
            with Accelerator().split_between_processes(inputs=inputs, apply_padding=False) as process_inputs:
                inputs = process_inputs

        if "input_ids" in inputs:
            self.model_shapes.update(dict(zip(["batch_size", "sequence_length"], inputs["input_ids"].shape)))

        if "pixel_values" in inputs:
            self.model_shapes.update(
                dict(zip(["batch_size", "num_channels", "height", "width"], inputs["pixel_values"].shape))
            )

        return inputs

    def prepare_inputs_after_load(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        for key in list(inputs.keys()):
            if hasattr(self.pretrained_model, "input_names") and key not in self.pretrained_model.input_names:
                inputs.pop(key)

        return inputs

    def forward(self, inputs: Dict[str, Any], kwargs: Dict[str, Any]) -> OrderedDict:
        return self.pretrained_model.forward(**inputs, **kwargs)

    def prefill(self, inputs: Dict[str, Any], kwargs: Dict[str, Any]) -> OrderedDict:
        return self.pretrained_model.generate(**inputs, **kwargs)

    def generate(self, inputs: Dict[str, Any], kwargs: Dict[str, Any]) -> OrderedDict:
        return self.pretrained_model.generate(**inputs, **kwargs)

    def call(self, inputs: Dict[str, Any], kwargs: Dict[str, Any]) -> OrderedDict:
        return self.pretrained_model(**inputs, **kwargs)
