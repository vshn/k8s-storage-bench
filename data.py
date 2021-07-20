#!/usr/bin/env python3.8

import json
import math
import numpy
import statistics
import sys

import humanize


class BenchData:
    def __init__(self, result):
        self._op = result["name"]
        self._storageclass = result["storageclass"]
        self._iterations = result["iterations"]
        self._means = numpy.empty(self.iterations)
        self._stddevs = numpy.empty(self.iterations)
        self._mins = numpy.empty(self.iterations)
        self._maxs = numpy.empty(self.iterations)
        for i, d in enumerate(result["results"]):
            self._means[i] = d["mean"]
            self._stddevs[i] = d["stddev"]
            self._mins[i] = d["min"]
            self._maxs[i] = d["max"]

    @property
    def name(self):
        return f"{self.op}_{self.storageclass}"

    @property
    def op(self):
        return self._op

    @property
    def storageclass(self):
        return self._storageclass

    @property
    def means(self):
        return self._means

    @property
    def mins(self):
        return self._mins

    @property
    def maxs(self):
        return self._maxs

    @property
    def stddevs(self):
        return self._stddevs

    @property
    def iterations(self):
        return self._iterations

    @property
    def unit(self):
        if "iops" in self.op:
            return "IOPS"
        if "bw" in self.op:
            return "KB/s"
        raise ValueError(f"Unknown unit for {self.op}")

    @property
    def type(self):
        if "write" in self.op:
            return "write"
        if "read" in self.op:
            return "read"
        raise ValueError(f"Unknown type for {self.op}")

    @property
    def ylim(self):
        """
        Compute next "round" number for magnitude of number, e.g. 50000 for 48745
        """
        ymax = numpy.max(self.maxs)
        ylim_floor = 10 ** math.floor(math.log(ymax, 10))
        return math.ceil(ymax / ylim_floor) * ylim_floor

    @property
    def fsync(self):
        if ":" in self.op:
            _, fsync = self.op.split(":")
            return int(fsync)
        return 0

    def __repr__(self):
        return f"BenchData(op={self.op}, storageclass={self.storageclass}, means={self.means}, stddevs={self.stddevs}, mins={self.mins}, maxs={self.maxs})"

    def info(self):
        mean_of_means = statistics.mean(self.means)
        if len(self.means) > 1:
            stdev_of_means = statistics.stdev(self.means)
        else:
            stdev_of_means = 0
        unit = self.unit
        if unit == "KB/s":
            mean_of_means = humanize.naturalsize(mean_of_means * 1000, format="%.3f")
            stdev_of_means = humanize.naturalsize(stdev_of_means * 1000, format="%.3f")
        else:
            mean_of_means = f"{mean_of_means:.2f}{unit}"
            stdev_of_means = f"{stdev_of_means:.2f}{unit}"

        return f"Mean {mean_of_means}/s +- {stdev_of_means}/s"


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help"]:
        print(f"Usage {sys.argv[0]} <results-file>\n")
        print(
            "This command can be used to print statistical information for the benchmark\n"
            + "results in <results-file>. The command expects that the results are in the\n"
            + "JSON format emitted by the bundled `bench.py` script."
        )
        sys.exit(1)

    with open(sys.argv[1]) as resf:
        results = [BenchData(r) for r in json.load(resf)]

    for r in results:
        print(f"StorageClass: {r.storageclass}")
        print(f"Benchmark: {r.op}")
        print(r.info())
