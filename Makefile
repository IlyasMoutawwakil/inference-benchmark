# List of targets that are not associated with files
.PHONY: quality style install build_docker_cpu build_docker_cuda build_docker_rocm run_docker_cpu run_docker_cuda run_docker_rocm install_api_misc install_api_cpu install_api_cuda install_api_rocm install_cli_misc install_cli_cpu_pytorch install_cli_cpu_openvino install_cli_cpu_onnxruntime install_cli_cpu_neural_compressor install_cli_cuda_pytorch install_cli_rocm_pytorch install_cli_cuda_torch_ort install_cli_cuda_onnxruntime test_api_misc test_api_cpu test_api_cuda test_api_rocm test_cli_misc test_cli_cpu_pytorch test_cli_cpu_openvino test_cli_cpu_onnxruntime test_cli_cpu_neural_compressor test_cli_cuda_onnxruntime test_cli_cuda_pytorch_multi_gpu test_cli_cuda_pytorch_single_gpu test_cli_cuda_torch_ort_multi_gpu test_cli_cuda_torch_ort_single_gpu test_cli_rocm_pytorch_multi_gpu test_cli_rocm_pytorch_single_gpu

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

## Build docker

build_docker_cpu:
	docker build --build-arg USER_ID=$(USER_ID) --build-arg GROUP_ID=$(GROUP_ID) -t opt-bench-cpu:22.04 docker/cpu

build_docker_cuda:
	docker build --build-arg USER_ID=$(USER_ID) --build-arg GROUP_ID=$(GROUP_ID) -t opt-bench-cuda:11.8.0 docker/cuda

build_docker_rocm:
	docker build --build-arg USER_ID=$(USER_ID) --build-arg GROUP_ID=$(GROUP_ID) -t opt-bench-rocm:5.7.1 docker/rocm

# Run docker

run_docker_cpu:
	docker run \
	-it \
	--rm \
	--volume $(PWD):/workspace \
	--entrypoint /bin/bash \
	--workdir /workspace \
	opt-bench-cpu:22.04

run_docker_cuda:
	docker run \
	-it \
	--rm \
	--gpus all \
	--shm-size 64G \
	--volume $(PWD):/workspace \
	--entrypoint /bin/bash \
	--workdir /workspace \
	opt-bench-cuda:11.8.0

run_docker_rocm:
	docker run \
	-it \
	--rm \
	--shm-size 64G \
	--device /dev/kfd \
	--device /dev/dri \
	--volume $(PWD):/workspace \
	--entrypoint /bin/bash \
	--workdir /workspace \
	opt-bench-rocm:5.7.1

## Install extras

install_api_misc:
	pip install -e .[testing,timm,diffusers,peft]

install_api_cpu:
	pip install -e .[testing,timm,diffusers,peft]

install_api_cuda:
	pip install -e .[testing,timm,diffusers,peft]

install_api_rocm:
	pip install -e .[testing,timm,diffusers,peft]

install_cli_misc:
	pip install -e .[testing,timm,diffusers,peft]

install_cli_cpu_pytorch:
	pip install -e .[testing,peft,timm,diffusers]

install_cli_cpu_openvino:
	pip install -e .[testing,peft,timm,diffusers,openvino]

install_cli_cpu_onnxruntime:
	pip install -e .[testing,peft,timm,diffusers,onnxruntime]

install_cli_cpu_neural_compressor:
	pip install -e .[testing,peft,timm,diffusers,neural-compressor]

install_cli_cuda_pytorch:
	pip install -e .[testing,timm,diffusers,peft,autoawq,auto-gptq,bitsandbytes,deepspeed]

install_cli_rocm_pytorch:
	pip install -e .[testing,timm,diffusers,peft,autoawq,auto-gptq,deepspeed]

install_cli_cuda_torch_ort:
	pip install -e .[testing,timm,diffusers,peft,torch-ort,deepspeed]
	python -m torch_ort.configure

install_cli_cuda_onnxruntime:
	pip install -e .[testing,timm,diffusers,peft,onnxruntime-gpu]

# Run tests

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

test_cli_cpu_pytorch:
	pytest -s -k "cli and cpu and pytorch"

test_cli_cpu_openvino:
	pytest -s -k "cli and cpu and openvino"

test_cli_cpu_onnxruntime:
	pytest -s -k "cli and cpu and onnxruntime"

test_cli_cpu_neural_compressor:
	pytest -s -k "cli and cpu and neural-compressor"

test_cli_cuda_onnxruntime:
	pytest -s -k "cli and cuda and onnxruntime"

test_cli_cuda_pytorch_multi_gpu:
	pytest -s -k "cli and cuda and pytorch and (dp or ddp or device_map or deepspeed) and not awq"

test_cli_cuda_pytorch_single_gpu:
	pytest -s -k "cli and cuda and pytorch and not (dp or ddp or device_map or deepspeed) and not awq"

test_cli_cuda_torch_ort_multi_gpu:
	pytest -s -k "cli and cuda and torch-ort and (dp or ddp or device_map or deepspeed) and not peft"

test_cli_cuda_torch_ort_single_gpu:
	pytest -s -k "cli and cuda and torch-ort and not (dp or ddp or device_map or deepspeed) and not peft"

test_cli_rocm_pytorch_multi_gpu:
	pytest -s -k "cli and rocm and pytorch and (dp or ddp or device_map or deepspeed) and not (bnb or awq)"

test_cli_rocm_pytorch_single_gpu:
	pytest -s -k "cli and rocm and pytorch and not (dp or ddp or device_map or deepspeed) and not (bnb or awq)"