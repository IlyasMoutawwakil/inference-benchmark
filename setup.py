import importlib.util
import os
import subprocess

from setuptools import find_packages, setup

OPTIMUM_BENCHMARK_VERSION = "0.2.0"

MIN_OPTIMUM_VERSION = "1.16.0"
INSTALL_REQUIRES = [
    # Mandatory HF dependencies
    "transformers",
    "accelerate",
    "datasets",
    # Hydra
    "hydra_colorlog",
    "hydra-core",
    "omegaconf",
    # CPU Memory
    "psutil",
    # Reporting
    "flatten_dict",
    "pandas",
]

try:
    subprocess.run(["nvidia-smi"], check=True)
    IS_NVIDIA_SYSTEM = True
except Exception:
    IS_NVIDIA_SYSTEM = False

try:
    subprocess.run(["rocm-smi"], check=True)
    IS_ROCM_SYSTEM = True
except Exception:
    IS_ROCM_SYSTEM = False

USE_CUDA = (os.environ.get("USE_CUDA", None) == "1") or IS_NVIDIA_SYSTEM
USE_ROCM = (os.environ.get("USE_ROCM", None) == "1") or IS_ROCM_SYSTEM

if USE_CUDA:
    INSTALL_REQUIRES.append("nvidia-ml-py")

PYRSMI = "pyrsmi@git+https://github.com/ROCm/pyrsmi.git"
if USE_ROCM:
    if not importlib.util.find_spec("amdsmi"):
        INSTALL_REQUIRES.append(PYRSMI)

if PYRSMI in INSTALL_REQUIRES:
    print("ROCm GPU detected without amdsmi installed. Using pyrsmi instead but some features may not work.")


EXTRAS_REQUIRE = {
    "quality": ["ruff"],
    "testing": ["pytest", "hydra-joblib-launcher"],
    # optimum backends
    "openvino": [f"optimum[openvino,nncf]>={MIN_OPTIMUM_VERSION}"],
    "onnxruntime": [f"optimum[onnxruntime]>={MIN_OPTIMUM_VERSION}"],
    "onnxruntime-gpu": [f"optimum[onnxruntime-gpu]>={MIN_OPTIMUM_VERSION}"],
    "neural-compressor": [f"optimum[neural-compressor]>={MIN_OPTIMUM_VERSION}"],
    "torch-ort": ["torch-ort", "onnxruntime-training", f"optimum>={MIN_OPTIMUM_VERSION}"],
    # other backends
    "llm-swarm": ["llm-swarm@git+https://github.com/huggingface/llm-swarm.git"],
    "py-txi": ["py-txi@git+https://github.com/IlyasMoutawwakil/py-txi.git"],
    # optional dependencies
    "codecarbon": ["codecarbon"],
    "deepspeed": ["deepspeed"],
    "diffusers": ["diffusers"],
    "timm": ["timm"],
    "peft": ["peft"],
    "autoawq": ["autoawq@git+https://github.com/casper-hansen/AutoAWQ.git"],
    "bitsandbytes": ["bitsandbytes"],
}


setup(
    name="optimum-benchmark",
    version=OPTIMUM_BENCHMARK_VERSION,
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    packages=find_packages(),
    entry_points={"console_scripts": ["optimum-benchmark=optimum_benchmark.cli:benchmark_cli"]},
)
