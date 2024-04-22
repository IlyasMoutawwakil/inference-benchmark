import os
from logging import getLogger
from typing import Callable

from ...benchmarks.report import BenchmarkReport
from ..base import Launcher
from ..isolation_utils import device_isolation
from .config import InlineConfig

LOGGER = getLogger("inline")


class InlineLauncher(Launcher[InlineConfig]):
    NAME = "inline"

    def __init__(self, config: InlineConfig):
        super().__init__(config)

    def launch(self, worker: Callable, *worker_args) -> BenchmarkReport:
        with device_isolation(
            enable=self.config.device_isolation,
            action=self.config.device_isolation_action,
            isolated_pids={os.getpid()},
        ):
            LOGGER.info(f"\t+ Running benchmark in the main process with PID {os.getpid()}.")
            report = worker(*worker_args)

        return report
