# Storage Benchmark for K8s

## Prerequisites

* Access to cluster
* [kubestr](https://kubestr.io/)
* Python 3.8
  * `matplotlib` for rendering plots of results


## Usage

Call `bench.py -s mystorageclass` to run full set of benchmarks for StorageClass `mystorageclass`.
Check `bench.py -h` for available options.
The benchmark script will save the results into JSON file `results_%Y_%m_%d_%H%M%S.json` (Python `strftime` format).

You can visualize the results by running `./render.py <resultfile>.json`.
This command will produce a PDF file with plots for the benchmark results.

To extract statistical information from a results file, you can run `./data.py <results.json>`.
This command prints the same statistical information which is printed during the benchmark run.

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
If you want to run the benchmark in a namespace other than `default`, adjust the RoleBinding in `deploy/rbac.yaml` accordingly.

Then you can execute the provided `run.sh` to run the benchmark with the default settings.
