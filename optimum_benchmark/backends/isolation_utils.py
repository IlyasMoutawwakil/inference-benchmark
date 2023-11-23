import logging.config
import os
import signal
import time
from logging import getLogger
from typing import Dict, List

from omegaconf import OmegaConf

from ..env_utils import is_nvidia_system, is_rocm_system
from ..import_utils import is_amdsmi_available, is_py3nvml_available, torch_version

LOGGER = getLogger("isolation")


def check_cuda_isolation(isolated_devices: List[int], permitted_pids: List[int]) -> None:
    """
    Raises a RuntimeError if any process other than the permitted ones is running on the specified CUDA devices.
    """
    pids: Dict[int, set] = {}
    for device_id in isolated_devices:
        pids[device_id] = set()

    if is_nvidia_system():
        if not is_py3nvml_available():
            raise ValueError(
                "check_no_process_is_running_on_cuda_device requires py3nvml. "
                "Please install it with `pip install py3nvml`."
            )
        import py3nvml.py3nvml as nvml

        nvml.nvmlInit()
        for device_id in isolated_devices:
            device_handle = nvml.nvmlDeviceGetHandleByIndex(device_id)
            device_processes = nvml.nvmlDeviceGetComputeRunningProcesses(device_handle)
            for device_process in device_processes:
                if device_process.pid not in permitted_pids:
                    LOGGER.warning(f"Found unexpected process {device_process.pid} on device {device_id}.")
                    LOGGER.warning(f"Process info: {device_process}")

                pids[device_id].add(device_process.pid)

        nvml.nvmlShutdown()
    elif is_rocm_system():
        rocm_version = torch_version().split("rocm")[-1]

        if not is_amdsmi_available():
            raise ValueError(
                "check_no_process_is_running_on_cuda_device requires amdsmi. "
                "Please follow the instructions at https://github.com/RadeonOpenCompute/amdsmi/tree/master"
            )
        import amdsmi

        amdsmi.amdsmi_init()

        if rocm_version >= "5.7":
            # starting from rocm 5.7, the api seems to have changed names
            devices_handles = amdsmi.amdsmi_get_processor_handles()
            for device_id in isolated_devices:
                device_handle = devices_handles[device_id]
                try:
                    # these functions fail a lot for no apparent reason
                    processes_handles = amdsmi.amdsmi_get_gpu_process_list(device_handle)
                except Exception:
                    continue

                for process_handle in processes_handles:
                    try:
                        # these functions fail a lot for no apparent reason
                        info = amdsmi.amdsmi_get_gpu_process_info(device_handle, process_handle)
                    except Exception:
                        continue

                    if info["memory_usage"]["vram_mem"] == 4096:
                        continue

                    if info["pid"] not in permitted_pids:
                        LOGGER.warning(f"Found unexpected process {info['pid']} on device {device_id}.")
                        LOGGER.warning(f"Process info: {info}")

                    pids[device_id].add(info["pid"])
        else:
            devices_handles = amdsmi.amdsmi_get_device_handles()
            for device_id in isolated_devices:
                device_handle = devices_handles[device_id]
                try:
                    # these functions fail a lot for no apparent reason
                    processes_handles = amdsmi.amdsmi_get_process_list(device_handle)
                except Exception:
                    continue

                for process_handle in processes_handles:
                    try:
                        # these functions fail a lot for no apparent reason
                        info = amdsmi.amdsmi_get_process_info(device_handle, process_handle)
                    except Exception:
                        continue

                    if info["memory_usage"]["vram_mem"] == 4096:
                        continue

                    if info["pid"] not in permitted_pids:
                        LOGGER.warning(f"Found unexpected process {info['pid']} on device {device_id}.")
                        LOGGER.warning(f"Process info: {info}")

                    pids[device_id].add(info["pid"])

        amdsmi.amdsmi_shut_down()
    else:
        raise ValueError("check_no_process_is_running_on_cuda_device is only supported on NVIDIA and AMD GPUs.")

    all_pids = set()
    for device_id in isolated_devices:
        all_pids |= pids[device_id]
    other_pids = all_pids - set(permitted_pids)

    if len(other_pids) > 0:
        error_message = (
            f"Expected only process(se) {permitted_pids} on device(s) {isolated_devices}, but found {other_pids}."
        )
        raise RuntimeError(error_message)


def check_cuda_continuous_isolation(isolated_pid: int, isolation_check_interval: int = 1) -> None:
    """
    Kills the isolated process if any other process than the permitted ones is running on the specified CUDA devices.
    """

    hydra_conf = OmegaConf.load(".hydra/hydra.yaml")
    logging.config.dictConfig(OmegaConf.to_container(hydra_conf.hydra.job_logging, resolve=True))

    # distributed setting is tricky
    if os.environ.get("LOCAL_WORLD_SIZE", None) is not None:
        from torch.distributed import TCPStore

        local_rank = os.environ["LOCAL_RANK"]
        all_isolated_keys = [f"isolated_{other_rank}" for other_rank in range(int(os.environ["LOCAL_WORLD_SIZE"]))]
        all_isolators_keys = [f"isolator_{other_rank}" for other_rank in range(int(os.environ["LOCAL_WORLD_SIZE"]))]

        store = TCPStore(host_name=os.environ["MASTER_ADDR"], port=int(os.environ["MASTER_PORT"]))

        store.add(f"isolator_{local_rank}", os.getpid())
        store.add(f"isolated_{local_rank}", isolated_pid)
        store.wait(all_isolated_keys + all_isolators_keys)

        all_isolated_pids = [int(store.get(name)) for name in all_isolated_keys]
        all_isolators_pids = [int(store.get(name)) for name in all_isolators_keys]
        permitted_pids = all_isolated_pids + all_isolators_pids
        assert len(permitted_pids) == len(set(permitted_pids)), "Found duplicated pids in the distributed setting"
    else:
        isolator_pid = os.getpid()
        permitted_pids = [isolator_pid, isolated_pid]

    isolated_devices = [int(device) for device in os.environ["CUDA_VISIBLE_DEVICES"].split(",")]

    LOGGER.info(
        f"Continuously checking only process(es) {permitted_pids} is/are running on device(s) {isolated_devices}"
    )

    while True:
        try:
            check_cuda_isolation(isolated_devices, permitted_pids)
            time.sleep(isolation_check_interval)
        except RuntimeError as e:
            LOGGER.error("Error while checking CUDA isolation:")
            LOGGER.error(e)
            LOGGER.error("Killing isolated process...")
            os.kill(isolated_pid, signal.SIGTERM)  # graceful kill, will trigger the backend cleanup
            e.with_traceback()
