from dataclasses import dataclass, field
from omegaconf import DictConfig
from logging import getLogger
from pandas import DataFrame
from typing import List, Dict
import statistics
import csv
from collections import defaultdict


from optimum_benchmark.backends.base import Backend
from optimum_benchmark.trackers.memory import memory_tracker_class_for_backend
from optimum_benchmark.trackers.latency import latency_tracker_class_for_backend
from optimum_benchmark.generators.dummy_input import DummyInputGenerator
from optimum_benchmark.benchmarks.base import Benchmark, BenchmarkConfig


LOGGER = getLogger("inference")


@dataclass
class InferenceConfig(BenchmarkConfig):
    name: str = "inference"
    _target_: str = "optimum_benchmark.benchmarks.inference.InferenceBenchmark"

    # run options
    memory: bool = False
    profile: bool = False

    # loop options
    warmup_runs: int = 10
    benchmark_duration: int = 10

    # input options
    input_shapes: Dict = field(default_factory=lambda: {
            "batch_size": 1,
            # text
            "sequence_length": 16,
            "num_choices": 1,
            # image
            "width": 64,
            "height": 64,
            "num_channels": 3,
            "point_batch_size": 3,
            "nb_points_per_image": 2,
            # audio
            "feature_size": 80,
            "nb_max_frames": 3000,
            "audio_sequence_length": 16000,
        }
    )

    # generation options
    new_tokens: int = 100


class InferenceBenchmark(Benchmark):
    def __init__(self):
        super().__init__()

        # initialize inference results
        self.forward_peak_memory: int = 0
        self.forward_latencies: List[float] = []
        self.generate_latencies: List[float] = []

    def configure(self, config: InferenceConfig):
        super().configure(config)

        self.memory = config.memory
        self.profile = config.profile

        self.warmup_runs = config.warmup_runs
        self.benchmark_duration = config.benchmark_duration

        self.new_tokens = config.new_tokens
        self.batch_size = config.input_shapes.batch_size

        self.dummy_input_generator = DummyInputGenerator(
            input_shapes=config.input_shapes
        )

    def run(self, backend: Backend) -> None:
        LOGGER.info("Running inference benchmark")
        self.can_generate = backend.can_generate()

        if self.memory:
            # if requested, run memory tracking
            self.run_memory_tracking(backend)

        # ALWAYS run forward pass
        self.run_forward_tracking(backend)

        if self.can_generate:
            # if possible, run generation pass
            self.run_generate_tracking(backend)
            
        if self.profile:
            self.run_forward_profiling(backend)
        
        

    def run_forward_profiling(self, backend: Backend) -> None:
        forward_input, forward_input_shapes = self.dummy_input_generator.generate(
            mode="forward",
            backend=backend,
        )

        backend.prepare_for_profiling(
            input_names=forward_input.keys(),
            input_shapes=forward_input_shapes,
        )

        LOGGER.info("\t+ Warming up the forward pass")
        for _ in range(self.warmup_runs):
            _ = backend.forward(forward_input)
            
        LOGGER.info("\t+ Profiling records")
        node_runtimes = defaultdict(list)
        profiling_records = backend.pretrained_model.get_profiling_records()

        for node_name, node_op, node_runtime in profiling_records:
            node_runtimes[node_name].append((node_op, node_runtime))

        # Calculate the average runtime and variance for each node.name
        result_records = []
        for node_name, records in node_runtimes.items():
            runtimes = [record[1] for record in records]
            node_op = records[0][0]  # Take the first operation type as a representative
            mean_runtime = statistics.mean(runtimes)
            std_runtime = statistics.stdev(runtimes) if len(runtimes) > 1 else 0
            result_records.append((node_name, node_op, mean_runtime, std_runtime))

        # Write the results to a CSV file
        with open('profiling_results.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Node Name', 'Node Operation', 'Mean Runtime (seconds)', 'Standard Deviation (seconds)'])  # Write the header
            writer.writerows(result_records)  # Write the records


    def run_memory_tracking(self, backend: Backend) -> None:
        memory_input, memory_input_shapes = self.dummy_input_generator.generate(
            mode="forward",
            backend=backend,
        )

        backend.prepare_for_inference(
            input_names=memory_input.keys(),
            input_shapes=memory_input_shapes,
        )

        LOGGER.info("\t+ Tracking forward pass peak memory")
        memory_tracker = memory_tracker_class_for_backend[backend.config.name](backend)
        with memory_tracker.track(interval=self.benchmark_duration // 100):
            _ = backend.forward(memory_input)

        self.forward_peak_memory = memory_tracker.get_peak_memory()
        LOGGER.info(f"\t+ Forward pass peak memory: {self.forward_peak_memory} (MB)")

    def run_forward_tracking(self, backend: Backend) -> None:
        forward_input, forward_input_shapes = self.dummy_input_generator.generate(
            mode="forward",
            backend=backend,
        )

        backend.prepare_for_inference(
            input_names=forward_input.keys(),
            input_shapes=forward_input_shapes,
        )

        LOGGER.info("\t+ Warming up the forward pass")
        for _ in range(self.warmup_runs):
            _ = backend.forward(forward_input)

        LOGGER.info("\t+ Tracking forward pass latency and throughput")
        latency_tracker = latency_tracker_class_for_backend[backend.config.name](backend)
        while sum(self.forward_latencies) < self.benchmark_duration:
            with latency_tracker.track():
                _ = backend.forward(forward_input)
            self.forward_latencies = latency_tracker.get_latencies()

        LOGGER.info(f"\t+ Forward pass latency: {self.forward_latency:.2e} (s)")
        LOGGER.info(
            f"\t+ Forward pass throughput: {self.forward_throughput:.2f} (samples/s)"
        )

    def run_generate_tracking(self, backend: Backend) -> None:
        generate_input, _ = self.dummy_input_generator.generate(
            mode="generate",
            backend=backend,
        )

        LOGGER.info("\t+ Warming up the generation pass")
        _ = backend.generate(
            input=generate_input,
            max_new_tokens=self.new_tokens,
            min_new_tokens=self.new_tokens,
            do_sample=False,
            use_cache=True,
            pad_token_id=0,
            num_beams=1,
        )

        LOGGER.info("\t+ Tracking generation latency and throughput")
        latency_tracker = latency_tracker_class_for_backend[backend.config.name](backend)
        while sum(self.generate_latencies) < self.benchmark_duration:
            with latency_tracker.track():
                _ = backend.generate(
                    generate_input,
                    max_new_tokens=self.new_tokens,
                    min_new_tokens=self.new_tokens,
                )
            self.generate_latencies = latency_tracker.get_latencies()

        LOGGER.info(f"\t+ Generation pass latency: {self.generate_latency:.2e} (s)")

        LOGGER.info(
            f"\t+ Generation pass throughput: {self.generate_throughput:.2f} (tokens/s)"
        )

    # Metrics
    @property
    def forward_latency(self) -> float:
        return significant_figures(statistics.mean(self.forward_latencies))

    @property
    def forward_throughput(self) -> float:
        return significant_figures(self.batch_size / self.forward_latency)

    @property
    def generate_latency(self) -> float:
        return significant_figures(statistics.mean(self.generate_latencies))

    @property
    def generate_throughput(self) -> float:
        return significant_figures(
            self.new_tokens * self.batch_size / self.generate_latency
        )

    def get_results_df(self) -> DataFrame:
        results_dict = dict()

        if self.memory:
            results_dict["forward.peak_memory(MB)"] = self.forward_peak_memory

        results_dict["forward.latency(s)"] = self.forward_latency
        results_dict["forward.throughput(samples/s)"] = self.forward_throughput

        if self.can_generate:
            results_dict["generate.latency(s)"] = self.generate_latency
            results_dict["generate.throughput(tokens/s)"] = self.generate_throughput

        return DataFrame(results_dict, index=[0])

    def save(self) -> None:
        LOGGER.info("Saving inference results")
        results_df = self.get_results_df()
        results_df.to_csv("inference_results.csv")


def significant_figures(x):
    return float(f"{x:.3g}")
