from logging import getLogger
from typing import Any, Dict

from hydra.utils import get_class
from transformers.utils import ModelOutput

from ..base import Backend
from .config import TRTLLMConfig
from .utils import MODEL_TYPE_TO_TRTLLMMODEL

LOGGER = getLogger("tensorrt-llm")


class TRTLLMBackend(Backend[TRTLLMConfig]):
    NAME = "tensorrt-llm"

    def __init__(self, config: TRTLLMConfig):
        super().__init__(config)
        self.validate_model_type()

        self.load_trtmodel_from_pretrained()

    def validate_model_type(self) -> None:
        if self.model_type not in MODEL_TYPE_TO_TRTLLMMODEL:
            raise NotImplementedError(f"TRTLLMBackend does not support model_type {self.model_type}")

        self.trtmodel_class = get_class(MODEL_TYPE_TO_TRTLLMMODEL[self.model_type])
        LOGGER.info(f"\t+ Using TRTLLMModel class {self.trtmodel_class.__name__}")

    def load_trtmodel_from_pretrained(self) -> None:
        self.pretrained_model = self.trtmodel_class.from_pretrained(
            self.config.model,
            tp=self.config.tp,
            pp=self.config.pp,
            dtype=self.config.dtype,
            use_fp8=self.config.use_fp8,
            world_size=self.config.world_size,
            gpus_per_node=self.config.gpus_per_node,
            use_cuda_graph=self.config.use_cuda_graph,
            optimization_level=self.config.optimization_level,
            max_prompt_length=self.config.max_prompt_length,
            max_batch_size=self.config.max_batch_size,
            max_new_tokens=self.config.max_new_tokens,
            max_beam_width=self.config.max_beam_width,
            **self.config.hub_kwargs,
        )

    def forward(self, inputs: Dict[str, Any], kwargs: Dict[str, Any]) -> ModelOutput:
        return self.pretrained_model.generate(
            input_ids=inputs.get("input_ids"),
            attention_mask=inputs.get("attention_mask"),
            max_new_tokens=1,
        )

    def generate(self, inputs: Dict[str, Any], kwargs: Dict[str, Any]) -> ModelOutput:
        return self.pretrained_model.generate(
            input_ids=inputs.get("input_ids"),
            attention_mask=inputs.get("attention_mask"),
            # important for benchmarking
            max_new_tokens=kwargs.get("max_new_tokens", -1),
            min_length=kwargs.get("min_new_tokens", -1),  # why different ?
            num_beams=kwargs.get("num_beams", 1),
            # not really important but just in case
            repetition_penalty=kwargs.get("repetition_penalty", 1.0),
            length_penalty=kwargs.get("length_penalty", 1.0),
            pad_token_id=kwargs.get("pad_token_id", 0),
            bos_token_id=kwargs.get("bos_token_id", 1),
            eos_token_id=kwargs.get("eos_token_id", 2),
            temperature=kwargs.get("temperature", 1.0),
            top_k=kwargs.get("top_k", 50),
            top_p=kwargs.get("top_p", 1.0),
            seed=kwargs.get("seed", 42),
        )
