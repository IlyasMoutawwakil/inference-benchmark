# List of targets that are not associated with files
.PHONY:	quality style install build_docker_cpu build_docker_cuda build_docker_rocm test_cli_cpu_neural_compressor test_cli_cpu_onnxruntime test_cli_cpu_openvino test_cli_cpu_pytorch test_cli_rocm_pytorch test_cli_cuda_pytorch test_api_cpu test_api_cuda test_api_rocm test_api_misc

quality:
	ruff check .
	ruff format --check .

style:
	ruff format .
	ruff check --fix .

install:
	pip install -e .

build_docker_cpu:
	docker build -f docker/cpu.dockerfile  --build-arg USER_ID=$(shell id -u) --build-arg GROUP_ID=$(shell id -g) -t opt-bench-cpu:latest .

build_docker_cuda:
	docker build -f docker/cuda.dockerfile  --build-arg USER_ID=$(shell id -u) --build-arg GROUP_ID=$(shell id -g) -t opt-bench-cuda:latest . 

build_docker_rocm:
	docker build -f docker/rocm.dockerfile  --build-arg USER_ID=$(shell id -u) --build-arg GROUP_ID=$(shell id -g) -t opt-bench-rocm:latest . 

test_cli_cpu_neural_compressor:
	docker run \
	--rm \
	--pid=host \
	--entrypoint /bin/bash \
	--volume $(PWD):/workspace \
	--workdir /workspace \
	opt-bench-cpu:latest -c "pip install -e .[testing,neural-compressor,diffusers,timm] && pytest tests/ -k 'cli and cpu and neural_compressor' -x"

test_cli_cpu_onnxruntime:
	docker run \
	--rm \
	--pid=host \
	--entrypoint /bin/bash \
	--volume $(PWD):/workspace \
	--workdir /workspace \
	opt-bench-cpu:latest -c "pip install -e .[testing,onnxruntime,diffusers,timm] && pytest tests/ -k 'cli and cpu and onnxruntime' -x"

test_cli_cpu_openvino:
	docker run \
	--rm \
	--pid=host \
	--entrypoint /bin/bash \
	--volume $(PWD):/workspace \
	--workdir /workspace \
	opt-bench-cpu:latest -c "pip install -e .[testing,openvino,diffusers,timm] && pytest tests/ -k 'cli and cpu and openvino' -x"

test_cli_cpu_pytorch:
	docker run \
	--rm \
	--pid=host \
	--entrypoint /bin/bash \
	--volume $(PWD):/workspace \
	--workdir /workspace \
	opt-bench-cpu:latest -c "pip install -e .[testing,diffusers,timm] && pytest tests/ -k 'cli and cpu and pytorch' -x"

test_cli_rocm_pytorch:
	docker run \
	--rm \
	--pid=host \
	--device=/dev/kfd \
	--device /dev/dri/renderD128 \
	--device /dev/dri/renderD129 \
	--group-add video \
	--entrypoint /bin/bash \
	--volume $(PWD):/workspace \
	--workdir /workspace \
	opt-bench-rocm:latest -c "pip install -e .[testing,diffusers,timm,deepspeed,peft] && pytest tests/ -k 'cli and cuda and pytorch' -x"

test_cli_cuda_pytorch:
	docker run \
	--rm \
	--pid=host \
	--gpus '"device=0,1"' \
	--entrypoint /bin/bash \
	--volume $(PWD):/workspace \
	--workdir /workspace \
	opt-bench-cuda:latest -c "pip install -e .[testing,diffusers,timm,deepspeed,peft] && pytest tests/ -k 'cli and cuda and pytorch' -x"

test_api_cpu:
	docker run \
	--rm \
	--pid=host \
	--entrypoint /bin/bash \
	--volume $(PWD):/workspace \
	--workdir /workspace \
	opt-bench-cpu:latest -c "pip install -e .[testing,timm,diffusers] && pytest tests/ -k 'api and cpu' -x"

test_api_cuda:
	docker run \
	--rm \
	--pid=host \
	--gpus '"device=0,1"' \
	--entrypoint /bin/bash \
	--volume $(PWD):/workspace \
	--workdir /workspace \
	opt-bench-cuda:latest -c "pip install -e .[testing,timm,diffusers] && pytest tests/ -k 'api and cuda' -x"

test_api_rocm:
	docker run \
	--rm \
	--pid=host \
	--device=/dev/kfd \
	--device /dev/dri/renderD128 \
	--device /dev/dri/renderD129 \
	--group-add video \
	--entrypoint /bin/bash \
	--volume $(PWD):/workspace \
	--workdir /workspace \
	opt-bench-rocm:latest -c "pip install -e .[testing,timm,diffusers] && pytest tests/ -k 'api and cuda' -x"

test_api_misc:
	docker run \
	--rm \
	--pid=host \
	--entrypoint /bin/bash \
	--volume $(PWD):/workspace \
	--workdir /workspace \
	opt-bench-cpu:latest -c "pip install -e .[testing,timm,diffusers] && pytest tests/ -k 'api and not (cpu or cuda or rocm or tensorrt)' -x"
