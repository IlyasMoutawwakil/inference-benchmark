# List of targets that are not associated with files
.PHONY: quality style install build_docker_cpu build_docker_cuda build_docker_rocm run_docker_cpu run_docker_cuda run_docker_rocm install_api_cpu_extras install_api_misc_extras install_api_cuda_extras install_api_rocm_extras install_cli_misc_extras install_cli_cpu_pytorch_extras install_cli_cpu_openvino_extras install_cli_cpu_onnxruntime_extras install_cli_cpu_neural_compressor_extras install_cli_cuda_pytorch_extras install_cli_rocm_pytorch_extras install_cli_cuda_torch_ort_extras install_cli_cuda_onnxruntime_extras

PWD := $(shell pwd)
USER_ID := $(shell id -u)
GROUP_ID := $(shell id -g)

quality:
	ruff check .
	ruff format --check .

style:
	ruff format .
	ruff check --fix .

install:
	pip install -e .

## Docker builds

build_docker_cpu:
	docker build --build-arg USER_ID=$(USER_ID) --build-arg GROUP_ID=$(GROUP_ID) -t opt-bench-cpu:local docker/cpu

build_docker_cuda:
	docker build --build-arg USER_ID=$(USER_ID) --build-arg GROUP_ID=$(GROUP_ID) -t opt-bench-cuda:local docker/cuda

build_docker_rocm:
	docker build --build-arg USER_ID=$(USER_ID) --build-arg GROUP_ID=$(GROUP_ID) -t opt-bench-rocm:local docker/rocm

# Docker run

run_docker_cpu:
	docker run \
	-it \
	--rm \
	--entrypoint /bin/bash \
	--volume $(PWD):/workspace \
	--workdir /workspace \
	opt-bench-cpu:local

run_docker_cuda:
	docker run \
	-it \
	--rm \
	--gpus all \
	--shm-size 64G \
	--entrypoint /bin/bash \
	--env PROCESS_SPECIFIC_VRAM="0" \
	--volume $(PWD):/workspace \
	--workdir /workspace \
	opt-bench-cuda:local

run_docker_rocm:
	docker run \
	-it \
	--rm \
	--shm-size 64G \
	--device /dev/kfd/ \
	--device /dev/dri/ \
	--entrypoint /bin/bash \
	--volume $(PWD):/workspace \
	--workdir /workspace \
	opt-bench-rocm:local

## Install extras

install_api_misc_extras:
	pip install -e .[testing,timm,diffusers,peft]

install_api_cpu_extras:
	pip install -e .[testing,timm,diffusers,peft]

install_api_cuda_extras:
	pip install -e .[testing,timm,diffusers,peft]

install_api_rocm_extras:
	pip install -e .[testing,timm,diffusers,peft]

install_cli_misc_extras:
	pip install -e .[testing,timm,diffusers,peft]

install_cli_cpu_pytorch_extras:
	pip install -e .[testing,peft,timm,diffusers]

install_cli_cpu_openvino_extras:
	pip install -e .[testing,peft,timm,diffusers,openvino]

install_cli_cpu_onnxruntime_extras:
	pip install -e .[testing,peft,timm,diffusers,onnxruntime]

install_cli_cpu_neural_compressor_extras:
	pip install -e .[testing,peft,timm,diffusers,neural-compressor]

install_cli_cuda_pytorch_extras:
	pip install -e .[testing,timm,diffusers,peft,autoawq,auto-gptq,bitsandbytes,deepspeed]

install_cli_rocm_pytorch_extras:
	pip install -e .[testing,timm,diffusers,peft,autoawq,auto-gptq,deepspeed]

install_cli_cuda_torch_ort_extras:
	pip install -e .[testing,timm,diffusers,peft,torch-ort,deepspeed]

install_cli_cuda_onnxruntime_extras:
	pip install -e .[testing,timm,diffusers,peft,onnxruntime-gpu]

# Test

test_api_misc:
	pytest -s -k "api and not (cpu or cuda)

test_api_cpu:
	pytest -s -k "api and cpu"

test_api_cuda:
	pytest -s -k "api and cuda"

test_api_rocm:
	pytest -s -k "api and cuda"

test_cli_misc:
	pytest -s -k "cli and not (cpu or cuda)"

test_cli_cpu_neural_compressor:
	pytest -s -k "cli and cpu and neural-compressor"

test_cli_cpu_onnxruntime:
	pytest -s -k "cli and cpu and onnxruntime"

test_cli_cpu_openvino:
	pytest -s -k "cli and cpu and openvino"

test_cli_cpu_pytorch:
	pytest -s -k "cli and cpu and pytorch"

test_cli_cuda_onnxruntime:
	pytest -s -k "cli and cuda and onnxruntime"

test_cli_cuda_pytorch_multi_gpu:
	pytest -s -k "cli and cuda and pytorch and (dp or ddp or device_map or deepspeed)"

test_cli_cuda_pytorch_single_gpu:
	pytest -s -k "cli and cuda and pytorch and not (dp or ddp or device_map or deepspeed)"

test_cli_rocm_pytorch_multi_gpu:
	pytest -s -k "cli and rocm and pytorch and (dp or ddp or device_map or deepspeed)"

test_cli_rocm_pytorch_single_gpu:
	pytest -s -k "cli and rocm and pytorch and not (dp or ddp or device_map or deepspeed)"

test_cli_cuda_torch_ort_multi_gpu:
	pytest -s -k "cli and cuda and torch-ort and (dp or ddp or device_map or deepspeed)"

test_cli_cuda_torch_ort_single_gpu:
	pytest -s -k "cli and cuda and torch-ort and not (dp or ddp or device_map or deepspeed)"
