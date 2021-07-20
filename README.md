# Storage Benchmark for K8s

## Prerequisites

* Access to cluster
* [kubestr](https://kubestr.io/)
* Python 3.8
  * `matplotlib` for rendering plots of results


## Usage

Call `bench.py -s mystorageclass` to run full set of benchmarks for StorageClass `mystorageclass`.

Check `bench.py -h` for available options

## Local setup

We recommend that you setup a virtualenv to run the scripts locally.

```bash
git clone https://github.com/vshn/k8s-storage-bench.git
cd k8s-storage-bench
python3.8 -m venv .virtualenv
. .virtualenv/bin/activate
pip install -r requirements.txt
# Show help
./bench.py -h
# Run all benchmarks for storage class mystorageclass
./bench.py -s mystorageclass
```

## Container image and deploy manifests

The container image is available on quay.io/vshn/k8s-storage-bench.

### Building the container image

The included `Dockerfile` can be used to build a container image based on `python:3.8-slim`.

### Running the benchmark as a K8s job

Adjust `deploy/job.yaml` to customize the benchmark configuration.

Then you can execute the provided `run.sh` to run the benchmark with the default settings.
