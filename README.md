About
------
In this repository I've included/implemented various sorting algorithms in order to carry out performance analysis under different powercaps and configurations. <br>
<br>
**Parallel Algorithms include**:
- Quick Sort Parallel
- Quick Sort SIMD Parallel
- Merge Sort
- Radix Sort Parallel
- Bitonic Sort Parallel
- Counting Sort Parallel

**Sequential Algorithms include**:
- STL Sort
- Quick Sort
- Quick Sort SIMD
- Bitonic Sort
- Radix Sort
- Bitonic Sort
- Counting Sort

Initialization (need root permissions)
-------
Clone this repository and run:
```
./scripts/init.sh
```

Initialization (Docker)
------
Althought app doesn't GPU features, StEP by default checks for NVIDIA GPU Drivers. Make sure the following are installed on the host:
- NVIDIA GPU drivers (recommended: nvidia-driver-535 or newer)

Install with:
```sh
sudo apt-get update
sudo apt-get install -y nvidia-driver-535
```

To have Docker support you also need:
- NVIDIA Container Toolkit

Install [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

Then restart Docker:
```sh
sudo systemctl restart docker
```

Build container and run container in privileged mode:
```sh
docker build -t sort-app .
docker run --gpus all --privileged -it sort-app
```

Build and Use
-------
To build the project run (in REPO_ROOT_DIR):

```sh
make
```
This will compile the `sort` binary into the `build/` directory and also copy it to `tools/split/minibenchmarks/openmp`. 

To run the program, use:

```sh
./build/sort <mode> <algorithm> [--size <N>] [--threads <N>]
```

**Examples:**
```sh
./build/sort bench qs
./build/sort all stl --size 1000000
```

For a full list of algorithms and options run:
```sh
./build/sort --help
```
Tools
-------
### SPLiT (Software Power Limiting Tools)

An open source collection of tools designed
for supporting energy-aware high-performance computing.
So far the repository supports Intel based CPUs and NVIDIA GPUs. [Link](https://projects.task.gda.pl/akrz/split/)

#### StEP (Static Energy Profile) (SPLiT suite)

This tool is designed for static exploration of the energy characteristic of the given Device.

To use with StEP (in tools/split directory):
```
sudo ./build/apps/StEP/StEP ./minibenchmarks/openmp/sort <options>
```

License
-------
This project is licensed under the Apache License 2.0. See the `LICENSE` file for the full text.

Third-party components:
- x86simdsort – BSD 3-Clause License (c) 2022 Intel

All licenses are permissive and compatible; attribution notices are preserved. By contributing you agree your contributions will be released under Apache-2.0.