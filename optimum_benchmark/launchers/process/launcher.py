import multiprocessing as mp
from logging import getLogger
from typing import Callable

from ...benchmarks.report import BenchmarkReport
from ...logging_utils import setup_logging
from ..base import Launcher
from ..isolation_utils import device_isolation
from .config import ProcessConfig

LOGGER = getLogger("process")


class ProcessLauncher(Launcher[ProcessConfig]):
    NAME = "process"

    def __init__(self, config: ProcessConfig):
        super().__init__(config)

        if mp.get_start_method(allow_none=True) != self.config.start_method:
            LOGGER.info(f"\t+ Setting multiprocessing start method to {self.config.start_method}.")
            mp.set_start_method(self.config.start_method, force=True)

    def launch(self, worker: Callable, *worker_args) -> BenchmarkReport:
        ctx = mp.get_context(self.config.start_method)
        log_level = ctx.get_logger().getEffectiveLevel()
        queue = ctx.Queue()
        lock = ctx.Lock()

        process = mp.Process(target=target, args=(worker, queue, lock, log_level, *worker_args), daemon=False)
        process.start()

        with device_isolation(
            enable=self.config.device_isolation, action=self.config.device_isolation_action, isolated_pids={process.pid}
        ):
            process.join()

            if process.exitcode != 0 and queue.empty():
                raise RuntimeError(f"Process exited with code {process.exitcode}.")

            report: BenchmarkReport = queue.get()

        return report


def target(worker, queue, lock, log_level, *worker_args):
    setup_logging(log_level, prefix="ISOLATED-PROCESS")

    worker_output = worker(*worker_args)

    lock.acquire()
    queue.put(worker_output)
    lock.release()
