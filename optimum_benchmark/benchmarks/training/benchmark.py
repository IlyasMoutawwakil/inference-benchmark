from logging import getLogger
from contextlib import ExitStack

from ..base import Benchmark
from .config import TrainingConfig
from .report import TrainingReport
from ...trackers.memory import MemoryTracker
from ...backends.base import Backend, BackendConfigT
from ...trackers.energy import EnergyTracker, Efficiency
from ...generators.dataset_generator import DatasetGenerator
from ...trackers.latency import LatencyTrainerCallback, Throughput

from transformers import default_data_collator

LOGGER = getLogger("training")

TRAIN_THROUGHPUT_UNIT = "samples/s"
TRAIN_EFFICIENCY_UNIT = "samples/kWh"


class TrainingBenchmark(Benchmark[TrainingConfig]):
    NAME = "training"

    def __init__(self, config: TrainingConfig) -> None:
        super().__init__(config)

    def run(self, backend: Backend[BackendConfigT]) -> None:
        LOGGER.info("\t+ Creating dataset generator")
        dataset_generator = DatasetGenerator(
            task=backend.config.task,
            model_shapes=backend.model_shapes,
            dataset_shapes=self.config.dataset_shapes,
        )

        LOGGER.info("\t+ Generating training dataset")
        training_dataset = dataset_generator()

        LOGGER.info("\t+ Initializing training report")
        self.report = TrainingReport()

        training_callbackes = []
        if self.config.latency:
            LOGGER.info("\t+ Adding latency measuring callback")
            latency_callback = LatencyTrainerCallback(device=backend.config.device, backend=backend.config.name)
            training_callbackes.append(latency_callback)

        training_trackers = []
        if self.config.memory:
            LOGGER.info("\t+ Adding memory tracking context manager")
            memory_tracker = MemoryTracker(
                device=backend.config.device, backend=backend.config.name, device_ids=backend.config.device_ids
            )
            training_trackers.append(memory_tracker.track())

        if self.config.energy:
            LOGGER.info("\t+ Adding energy tracking context manager")
            energy_tracker = EnergyTracker(device=backend.config.device, device_ids=backend.config.device_ids)
            training_trackers.append(energy_tracker.track())

        with ExitStack() as stack:
            for tracker in training_trackers:
                stack.enter_context(tracker)

            backend.train(
                training_dataset=training_dataset,
                training_callbacks=training_callbackes,
                training_data_collator=default_data_collator,
                training_arguments=self.config.training_arguments,
            )

        if self.config.memory:
            # it's the same
            self.report.overall.max_memory = memory_tracker.get_max_memory()
            self.report.warmup.max_memory = memory_tracker.get_max_memory()
            self.report.train.max_memory = memory_tracker.get_max_memory()

            self.report.log_memory()

        if self.config.latency:
            self.report.overall.latency = latency_callback.get_latency()
            self.report.overall.throughput = Throughput.from_latency(
                self.report.overall.latency,
                volume=self.overall_volume,
                unit=TRAIN_THROUGHPUT_UNIT,
            )
            self.report.warmup.latency = self.report.overall.latency[: self.config.warmup_steps]
            self.report.warmup.throughput = Throughput.from_latency(
                self.report.warmup.latency,
                volume=self.warmup_volume,
                unit=TRAIN_THROUGHPUT_UNIT,
            )
            self.report.train.latency = self.report.overall.latency[self.config.warmup_steps :]
            self.report.train.throughput = Throughput.from_latency(
                self.report.train.latency,
                volume=self.train_volume,
                unit=TRAIN_THROUGHPUT_UNIT,
            )

            self.report.log_latency()
            self.report.log_throughput()

        if self.config.energy:
            # can only get overall energy consumption
            self.report.overall.energy = energy_tracker.get_energy()
            self.report.overall.efficiency = Efficiency.from_energy(
                self.report.overall.energy,
                volume=self.overall_volume,
                unit=TRAIN_EFFICIENCY_UNIT,
            )

            self.report.log_energy()
            self.report.log_efficiency()

    @property
    def overall_volume(self) -> int:
        return (
            self.config.max_steps
            * self.config.training_arguments["per_device_train_batch_size"]
            * self.config.training_arguments["gradient_accumulation_steps"]
        )

    @property
    def warmup_volume(self) -> int:
        return (
            self.config.warmup_steps
            * self.config.training_arguments["per_device_train_batch_size"]
            * self.config.training_arguments["gradient_accumulation_steps"]
        )

    @property
    def train_volume(self) -> int:
        return self.overall_volume - self.warmup_volume

    def get_report(self) -> TrainingReport:
        return self.report
