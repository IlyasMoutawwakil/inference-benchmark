# List of targets that are not associated with files
.PHONY:	quality style install build_docker_cpu build_docker_cuda build_docker_rocm build_docker_tensorrt test_api_misc test_api_cpu test_api_cuda test_api_rocm test_api_tensorrt test_cli_misc test_cli_cpu_pytorch test_cli_cpu_neural_compressor test_cli_cpu_onnxruntime test_cli_cpu_openvino test_cli_cuda_pytorch test_cli_rocm_pytorch test_cli_tensorrt_onnxruntime test_cli_tensorrt_llm

, := ,
PWD := $(shell pwd)
USER_ID := $(shell id -u)
GROUP_ID := $(shell id -g)

API_MISC_REQS := testing
API_CPU_REQS := testing,timm,diffusers
API_CUDA_REQS := testing,timm,diffusers
API_ROCM_REQS := testing,timm,diffusers

CLI_MISC_REQS := testing
CLI_CPU_PYTORCH_REQS := testing,peft,timm,diffusers
CLI_CPU_OPENVINO_REQS := testing,openvino,timm,diffusers
CLI_CPU_ONNXRUNTIME_REQS := testing,onnxruntime,timm,diffusers
CLI_CPU_NEURAL_COMPRESSOR_REQS := testing,neural-compressor,timm,diffusers

CLI_CUDA_ONNXRUNTIME_REQS := testing,timm,diffusers
CLI_ROCM_ONNXRUNTIME_REQS := testing,timm,diffusers
CLI_ROCM_PYTORCH_REQS := testing,timm,diffusers,deepspeed,peft,autoawq,auto-gptq
CLI_CUDA_PYTORCH_REQS := testing,timm,diffusers,deepspeed,peft,autoawq,auto-gptq,bitsandbytes

quality:
	ruff check .
	ruff format --check .

style:
	ruff format .
	ruff check --fix .

install:
	pip install -e .

## Docker builds

define build_docker
	docker build --build-arg USER_ID=$(USER_ID) --build-arg GROUP_ID=$(GROUP_ID) -t opt-bench-$(1):local docker/$(1)
endef

build_docker_cpu:
	$(call build_docker,cpu)

build_docker_cuda:
	$(call build_docker,cuda)

build_docker_rocm:
	$(call build_docker,rocm)


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

## Tests

define test_cpu
	docker run \
	--rm \
	--shm-size 64G \
	--entrypoint /bin/bash \
	--volume $(PWD):/workspace \
	--workdir /workspace \
	opt-bench-cpu:local -c "pip install -e .[$(1)] && pytest -x -s -k '$(2)'"
endef

define test_cuda
	docker run \
	--rm \
	--shm-size 64G \
	--gpus '"device=0,1"' \
	--entrypoint /bin/bash \
	--volume $(PWD):/workspace \
	--workdir /workspace \
	opt-bench-cuda:local -c "pip install -e .[$(1)] && pytest -x -s -k '$(2)'"
endef

define test_rocm
	docker run \
	--rm \
	--shm-size 64G \
	--device /dev/kfd/ \
	--device /dev/dri/renderD128 \
	--device /dev/dri/renderD129 \
	--entrypoint /bin/bash \
	--volume $(PWD):/workspace \
	--workdir /workspace \
	opt-bench-cuda:local -c "pip install -e .[$(1)] && pytest -x -s -k '$(2)'"
endef
