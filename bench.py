#!/usr/bin/env python3.8

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import textwrap
import time

from datetime import datetime
from enum import Enum
from pprint import PrettyPrinter
from typing import Dict

pp = PrettyPrinter(indent=2)


class Op(Enum):
    READ_IOPS = ("read", "iops")
    WRITE_IOPS = ("write", "iops")
    READ_BW = ("read", "bw")
    WRITE_BW = ("write", "bw")

    @property
    def unit(self):
        if self.value[1] == "iops":
            return "IOPS"
        if self.value[1] == "bw":
            return "KB/s"
        raise NotImplemented(f"unit not implemented for Op: {self.name}, {self.value[1]}")

    @property
    def data_key_suffixes(self):
        data_key_suffixes = ["max", "mean", "min"]
        if self.value[1] == "iops":
            data_key_suffixes.append("stddev")
            return data_key_suffixes
        if self.value[1] == "bw":
            data_key_suffixes.append("dev")
            return data_key_suffixes
        raise NotImplemented(
            f"data_key_suffixes not implemented for Op: {self.name}, {self.value[1]}"
        )


def extract_results(op: Op, result: Dict):
    try:
        data = result["Raw"]["result"]["jobs"][0][op.value[0]]
    except Exception as e:
        print(e)
        print(result)
        raise e
    pruned = {"display": data[op.value[1]]}

    def _clean(suffix):
        """
        Ensure we have same keys for all results
        """
        if suffix == "dev":
            return "stddev"
        return suffix

    for suffix in op.data_key_suffixes:
        key = f"{op.value[1]}_{suffix}"
        pruned[_clean(suffix)] = data[key]
    return pruned


def render_fio_config(op: Op, ramp_sec=5, run_sec=30, sync=0):
    name = f"{op.value[0]}_{op.value[1]}"

    if op.value[0] == "read":
        rw = "randread"
    elif op.value[0] == "write":
        rw = "randwrite"
    else:
        raise ValueError(f"Unknown Op: {op.name}, {op.value[0]}")

    if op.value[1] == "iops":
        blocksize = "4K"
    elif op.value[1] == "bw":
        blocksize = "128K"
    else:
        raise ValueError(f"Unknown Op: {op.name}, {op.value[1]}")

    return textwrap.dedent(
        f"""
        [global]
        randrepeat=0
        verify=0
        ioengine=libaio
        direct=1
        gtod_reduce=1
        [job]
        name={name}
        bs={blocksize}
        iodepth=64
        size=2G
        readwrite={rw}
        time_based
        ramp_time={ramp_sec}s
        runtime={run_sec}s
        fsync={sync}
        """
    ).strip()


BENCHMARKS = {
    "read_iops": {
        "fio_op": Op.READ_IOPS,
        "params": {},
    },
    "write_iops": {
        "fio_op": Op.WRITE_IOPS,
        "params": {},
    },
    "write_iops_fsync:1": {
        "fio_op": Op.WRITE_IOPS,
        "params": {
            "sync": 1,
        },
    },
    "write_iops_fsync:32": {
        "fio_op": Op.WRITE_IOPS,
        "params": {
            "sync": 32,
        },
    },
    "write_iops_fsync:128": {
        "fio_op": Op.WRITE_IOPS,
        "params": {
            "sync": 128,
        },
    },
    "read_bw": {
        "fio_op": Op.READ_BW,
        "params": {},
    },
    "write_bw": {
        "fio_op": Op.WRITE_BW,
        "params": {},
    },
    "write_bw_fsync:1": {
        "fio_op": Op.WRITE_BW,
        "params": {
            "sync": 1,
        },
    },
    "write_bw_fsync:32": {
        "fio_op": Op.WRITE_BW,
        "params": {
            "sync": 32,
        },
    },
    "write_bw_fsync:128": {
        "fio_op": Op.WRITE_BW,
        "params": {
            "sync": 128,
        },
    },
}


def run_kubestr(storage_class: str, fio_config: str, existing_pvc=None, namespace=None):
    tmpf = tempfile.NamedTemporaryFile(delete=False)
    tmpf.write(fio_config.encode("utf-8"))
    tmpf.close()
    kubestr_cmd = [
        "kubestr",
        "fio",
        "-s",
        storage_class,
        "-f",
        tmpf.name,
        "-z",
        "20Gi",
        "-o",
        "json",
    ]
    if existing_pvc != None:
        kubestr_cmd.extend(["-p", existing_pvc])
    if namespace != None:
        kubestr_cmd.extend(["-n", namespace])
    result = subprocess.run(
        kubestr_cmd,
        capture_output=True,
    )
    os.unlink(tmpf.name)
    if result.returncode != 0:
        raise Exception(f"Error running kubestr: {result.stderr}")
    result = result.stdout.decode("utf-8")
    json_start = 0
    resultlines = result.splitlines()
    for idx, line in enumerate(resultlines):
        if line.startswith("{"):
            json_start = idx
            break
    try:
        return json.loads("\n".join(resultlines[json_start:]))
    except:
        raise Exception(f"No JSON in kubestr output: {result}")


def run_benchmark(
    benchname,
    bench,
    storageclass,
    iters=5,
    verbose=False,
    existing_pvc=None,
    namespace=None,
):
    print(f"Running {benchname} benchmark", file=sys.stderr)
    op = bench["fio_op"]
    fio_config = render_fio_config(op, **bench["params"])
    results = []
    i = 0
    retry = 0
    while i < iters:
        try:
            print(f"Executing iteration {i+1}", file=sys.stderr)
            result = run_kubestr(
                storageclass, fio_config, existing_pvc=existing_pvc, namespace=namespace
            )
            data = extract_results(op, result)
            if verbose:
                pp.pprint(data)
            results.append(data)
            i = i + 1
            retry = 0
            time.sleep(5)
        except Exception as e:
            print(f"Error during iteration {i}:")
            print(e)
            if retry < 3:
                print("Retrying iteration")
                retry = retry + 1
            else:
                print(f"Giving up on iteration {i} after {retry} tries")
                i = i + 1
                retry = 0

    mean_of_means = statistics.mean([r["mean"] for r in results])
    if len(results) > 1:
        stdev_of_means = statistics.stdev([r["mean"] for r in results])
    else:
        stdev_of_means = 0
    unit = op.unit
    print(f"Mean {mean_of_means:.2f}{unit} +- {stdev_of_means:.2f}{unit}")

    return {
        "name": benchname,
        "storageclass": sc,
        "iterations": iters,
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run fio benchmarks on a K8s storage class")

    storage_class_default = None
    if "STORAGE_CLASSES" in os.environ:
        storage_class_default = os.environ["STORAGE_CLASSES"].split(",")

    parser.add_argument(
        "-s",
        "--storage-class",
        action="append",
        help="Select storage class(es) to benchmark. Can be repeated. "
        + " Defaults to the value of environment variable STORAGE_CLASSES."
        + " Multiple values can be separated by commas in the environment variable.",
        default=storage_class_default,
    )
    benchmark_default = None
    if "BENCHMARKS" in os.environ:
        benchmark_default = os.environ["BENCHMARKS"].split(",")
    parser.add_argument(
        "-b",
        "--benchmark",
        choices=BENCHMARKS.keys(),
        action="append",
        help="Select benchmark(s) to run. Can be repeated. If omitted, all benchmarks are run."
        + " Defaults to the value of environment variable BENCHMARKS."
        + " Multiple values can be separated by commas in the environment variable.",
        default=benchmark_default,
    )
    default_iters = 5
    try:
        default_iters = int(os.environ.get("BENCH_ITERATIONS", "5"))
    except:
        print("Unable to parse value of environment variable BENCH_ITERATIONS as int, ignoring it")
    parser.add_argument(
        "-i",
        "--iterations",
        type=int,
        default=default_iters,
        help="Amount of iterations for each benchmark,storage class pair"
        + " Defaults to the value of environment variable BENCH_ITERATIONS.",
    )

    verbose_default_str = os.environ.get("VERBOSE", "false")
    verbose_default = verbose_default_str in ["True", "true", "1", "yes"]
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=verbose_default,
        help="Verbose output. Defaults to value of environment variable VERBOSE."
        + " Valid values to enable verbose mode are 'True', 'true', '1' and 'yes'.",
    )
    parser.add_argument(
        "-O",
        "--output-directory",
        default=os.environ.get("OUTPUT_DIRECTORY", "."),
        help="Directory in which the json results are stored."
        + " Defaults to the value of environment variable OUTPUT_DIRECTORY.",
    )
    parser.add_argument(
        "-e",
        "--existing-pvc",
        default=os.environ.get("EXISTING_PVC"),
        help="Provide existing PVC for kubestr. Requires patched kubestr."
        + " Defaults to the value of environment variable EXISTING_PVC.",
    )
    parser.add_argument(
        "-n",
        "--namespace",
        default=os.environ.get("BENCH_NAMESPACE"),
        help="Namespace in which to run the benchmark."
        + " Defaults to the value of environment variable BENCH_NAMESPACE.",
    )
    args = parser.parse_args()

    if args.storage_class is None or len(args.storage_class) == 0:
        parser.print_help()
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    filename = f"{args.output_directory}/results_{timestamp}"

    results = []
    for sc in args.storage_class:
        print(f"Running benchmarks for storage class {sc}")

        items = []
        if args.benchmark is not None:
            for b in args.benchmark:
                items.append((b, BENCHMARKS[b]))
        else:
            items = BENCHMARKS.items()

        for benchname, bench in items:
            r = run_benchmark(
                benchname,
                bench,
                sc,
                iters=args.iterations,
                verbose=args.verbose,
                existing_pvc=args.existing_pvc,
                namespace=args.namespace,
            )
            results.append(r)

            print("Updating results file")
            with open(f"{filename}.json", "w") as resf:
                json.dump(results, resf)
