import os
from logging import getLogger

import pytest

from optimum_benchmark.logging_utils import run_subprocess_and_log_stream_output

LOGGER = getLogger("test-cli")

TEST_CONFIG_DIR = "/".join(__file__.split("/")[:-1] + ["configs"])
TEST_CONFIG_NAMES = [
    config.split(".")[0]
    for config in os.listdir(TEST_CONFIG_DIR)
    if config.endswith(".yaml") and not (config.startswith("_") or config.endswith("_"))
]


@pytest.mark.parametrize("config_name", TEST_CONFIG_NAMES)
def test_cli_configs(config_name):
    args = [
        "optimum-benchmark",
        "--config-dir",
        TEST_CONFIG_DIR,
        "--config-name",
        config_name,
        # to run config sweeps when defined
        "--multirun",
        # to run the tests faster (comment for debugging)
        "hydra/launcher=joblib",
    ]

    popen = run_subprocess_and_log_stream_output(LOGGER, args)
    assert popen.returncode == 0, f"Failed to run {config_name}"


def test_cli_exit_code():
    args_0 = [
        "optimum-benchmark",
        "--config-dir",
        TEST_CONFIG_DIR,
        "--config-name",
        "cpu_inference_pytorch_text_encoders",
        # compatible task and model
        "backend.task=text-classification",
        "backend.model=bert-base-uncased",
    ]

    popen_0 = run_subprocess_and_log_stream_output(LOGGER, args_0)
    assert popen_0.returncode == 0

    args_1 = [
        "optimum-benchmark",
        "--config-dir",
        TEST_CONFIG_DIR,
        "--config-name",
        "cpu_inference_pytorch_text_encoders",
        # incompatible task and model to trigger error
        "backend.task=image-classification",
        "backend.model=bert-base-uncased",
    ]

    popen_1 = run_subprocess_and_log_stream_output(LOGGER, args_1)
    assert popen_1.returncode == 1
