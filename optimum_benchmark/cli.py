import os
import glob
from logging import getLogger

import hydra
from omegaconf import DictConfig, OmegaConf
from hydra.core.config_store import ConfigStore

from .launchers.inline.config import InlineConfig
from .launchers.process.config import ProcessConfig
from .launchers.torchrun.config import TorchrunConfig

from .backends.openvino.config import OVConfig
from .backends.pytorch.config import PyTorchConfig
from .backends.onnxruntime.config import ORTConfig
from .backends.torch_ort.config import TorchORTConfig
from .backends.tensorrt_llm.config import TRTLLMConfig
from .backends.neural_compressor.config import INCConfig
from .backends.text_generation_inference.config import TGIConfig

from .experiment import launch, ExperimentConfig
from .benchmarks.training.config import TrainingConfig
from .benchmarks.inference.config import InferenceConfig
from .benchmarks.report import BenchmarkReport


LOGGER = getLogger("cli")

# Register configurations
cs = ConfigStore.instance()
cs.store(name="experiment", node=ExperimentConfig)
# backends configurations
cs.store(group="backend", name=OVConfig.name, node=OVConfig)
cs.store(group="backend", name=PyTorchConfig.name, node=PyTorchConfig)
cs.store(group="backend", name=ORTConfig.name, node=ORTConfig)
cs.store(group="backend", name=TorchORTConfig.name, node=TorchORTConfig)
cs.store(group="backend", name=TRTLLMConfig.name, node=TRTLLMConfig)
cs.store(group="backend", name=INCConfig.name, node=INCConfig)
cs.store(group="backend", name=TGIConfig.name, node=TGIConfig)
# benchmarks configurations
cs.store(group="benchmark", name=TrainingConfig.name, node=TrainingConfig)
cs.store(group="benchmark", name=InferenceConfig.name, node=InferenceConfig)
# launchers configurations
cs.store(group="launcher", name=InlineConfig.name, node=InlineConfig)
cs.store(group="launcher", name=ProcessConfig.name, node=ProcessConfig)
cs.store(group="launcher", name=TorchrunConfig.name, node=TorchrunConfig)


# optimum-benchmark
@hydra.main(version_base=None)
def benchmark_cli(experiment_config: DictConfig) -> None:
    os.environ["BENCHMARK_INTERFACE"] = "CLI"

    if glob.glob("benchmark_report.json") and os.environ.get("OVERRIDE_BENCHMARKS", "0") != "1":
        LOGGER.warning(
            "Benchmark report already exists. If you want to override it, set the environment variable OVERRIDE_BENCHMARKS=1"
        )
        return

    # Instantiate the experiment configuration and trigger its __post_init__
    experiment_config: ExperimentConfig = OmegaConf.to_object(experiment_config)
    experiment_config.to_json("experiment_config.json")

    benchmark_report: BenchmarkReport = launch(experiment_config=experiment_config)
    benchmark_report.to_json("benchmark_report.json")
