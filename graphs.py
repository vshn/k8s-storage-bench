from collections import UserDict

import humanize
import statistics

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from data import BenchData


def gen_colors(count, drop_high=True):
    """Generate spread of `count` colors from matplotlib inferno colormap"""
    # drop the top end of the color range by defining the norm with one
    # element too many
    cvals = range(0, count + drop_high)
    # and dropping the last element when calculating the normed values
    cvals = plt.Normalize(min(cvals), max(cvals))(cvals[0 : len(cvals) - drop_high])
    # we're using the 'inferno' colormap from matplotlib
    colors = plt.cm.inferno(cvals)
    return colors


class Benchmarks(UserDict):
    def __init__(self, initdata={}):
        super(Benchmarks, self).__init__(initdata)
        self.data_by_type = {
            "KB/s": {
                "read": [],
                "write": [],
            },
            "IOPS": {
                "read": [],
                "write": [],
            },
        }
        self._storageclasses = set()

    def __setitem__(self, k, v):
        self.data_by_type[v.unit][v.type].append(v)
        return super(Benchmarks, self).__setitem__(k, v)

    def __delitem__(self, k):
        v = self.data[k]
        self.data_by_type[v.unit][v.type].remove(v)
        return super(Benchmarks, self).__delitem__(k)

    @staticmethod
    def _include_series(d, fsync=-1, sc=None):
        if sc is not None:
            if fsync == -1:
                return d.storageclass == sc

            return d.storageclass == sc and d.fsync == fsync

        if fsync != -1:
            return d.fsync == fsync

        return True

    @staticmethod
    def _render_label(d: BenchData, fsync=-1, sc=None, add_mean=False):
        label = d.storageclass

        if d.type == "write":
            label = "no fsync"
            if d.fsync > 0:
                label = f"fsync={d.fsync}"
            if sc is None:
                label = f"{d.storageclass} / {label}"

        if add_mean:
            m = statistics.mean(d.means)
            if d.unit == "KB/s":
                m = humanize.naturalsize(m * 1000, format="%.1f")
                m = f"{m}/s"
            else:
                if m > 1000:
                    m = m / 1000.0
                    unit = f"k{d.unit}"
                else:
                    unit = d.unit
                m = f"{m:.1f} {unit}"

            label = f"{label}, mean={m}"

        return label

    def labels(self, typ, fsync=-1, sc=None, add_mean=False):
        datas = self.data_by_type[typ]
        labels = {
            "read": [],
            "write": [],
        }
        for k, v in datas.items():
            for d in v:
                assert d.type == k
                if Benchmarks._include_series(d, fsync=fsync, sc=sc):
                    labels[d.type].append(
                        Benchmarks._render_label(d, fsync=fsync, sc=sc, add_mean=add_mean)
                    )
        return labels

    def means(self, typ, fsync=-1, sc=None):
        datas = self.data_by_type[typ]
        means = {}
        for k, v in datas.items():
            means[k] = [d.means for d in v if Benchmarks._include_series(d, fsync=fsync, sc=sc)]
        return means

    def stddevs(self, typ, fsync=-1, sc=None):
        datas = self.data_by_type[typ]
        stddevs = {}
        for k, v in datas.items():
            stddevs[k] = [d.stddevs for d in v if Benchmarks._include_series(d, fsync=fsync, sc=sc)]
        return stddevs

    def ylims(self, typ, fsync=-1, sc=None):
        datas = self.data_by_type[typ]
        ylims = {
            "read": 0,
            "write": 0,
        }
        for k, v in datas.items():
            for d in v:
                assert d.type == k
                if Benchmarks._include_series(d, fsync=fsync, sc=sc):
                    if d.ylim > ylims[d.type]:
                        ylims[d.type] = d.ylim
        return ylims

    @property
    def storageclasses(self):
        for d in self.data.values():
            self._storageclasses.add(d.storageclass)
        return self._storageclasses


FIGSIZE = (6, 4)
FIGSIZE_LEGEND = (6, 5.5)


def plot_all_sc(pdf, title, unit, bench_data: Benchmarks, fsync=-1):
    labels = bench_data.labels(unit, fsync=fsync, add_mean=True)
    means = bench_data.means(unit, fsync=fsync)
    stddevs = bench_data.stddevs(unit, fsync=fsync)
    ylims = bench_data.ylims(unit, fsync=fsync)

    return plot_series(pdf, title, unit, labels, means, stddevs, ylims)


def plot_sc(pdf, unit, sc, bench_data: Benchmarks):
    labels = bench_data.labels(unit, sc=sc, add_mean=True)
    means = bench_data.means(unit, sc=sc)
    stddevs = bench_data.stddevs(unit, sc=sc)
    ylims = bench_data.ylims(unit, sc=sc)

    titleprefix = {
        "KB/s": "Bandwidth",
        "IOPS": "IOPS",
    }
    title = f"{titleprefix[unit]}, StorageClass {sc}"

    return plot_series(pdf, title, unit, labels, means, stddevs, ylims)


def plot_series(pdf, title, unit, labels, means, stddevs, ylims):
    # Expects dict with keys "read", "write" for labels, means, stddevs, ylims, and values as lists
    # for labels, means, stddevs, and numbers for ylims.

    types = [typ for typ in ["read", "write"] if len(means[typ]) > 0]
    if len(types) == 0:
        print(f"No data for plot '{title}', skipping")
        return

    iters = len(means[types[0]][0])
    xs = range(1, iters + 1)
    fmts = ["o-", "v-", "^-", "<-", ">-", "s-", "p-", "*-", "+-", "x-", "d-", "h-", "8-"]
    typ_colors = {t: gen_colors(len(l) + 1, drop_high=True)[1:] for t, l in labels.items()}

    for typ in types:
        colors = typ_colors[typ]
        plt.figure(figsize=FIGSIZE_LEGEND)
        plt.xticks(xs)
        for mean, stddev, label, fmt, color in zip(
            means[typ], stddevs[typ], labels[typ], fmts, colors
        ):
            plt.plot(xs, mean, fmt, label=label, color=color)
            plt.fill_between(xs, mean - stddev, mean + stddev, alpha=0.25, color=color)

        ax = plt.gca()
        ax.set_ylim(0, ylims[typ])
        ax.legend(bbox_to_anchor=(0.5, -0.12), loc="upper center")
        plt.xlabel("Iteration")
        plt.ylabel(unit)
        plt.tight_layout()
        plt.title(f"{typ} {title}")
        pdf.savefig()
        plt.close()


def render_results(results, filename="results.pdf"):
    bench_data = Benchmarks()
    for r in results:
        bd = BenchData(r)
        bench_data[bd.name] = bd

    plt.rcParams["image.cmap"] = "PuOr"

    with PdfPages(filename) as pdf:
        for d in bench_data.values():
            plt.figure(figsize=FIGSIZE)
            xs = range(1, d.iterations + 1)
            plt.xticks(xs)
            plt.errorbar(xs, d.means, yerr=d.stddevs)
            plt.fill_between(xs, d.means - d.stddevs, d.means + d.stddevs, alpha=0.5)
            plt.plot(xs, d.maxs, "b:")
            plt.plot(xs, d.mins, "b:")
            ax = plt.gca()
            ax.set_ylim(0, d.ylim)
            plt.xlabel("Iteration")
            plt.ylabel(d.unit)
            plt.tight_layout()
            title = f"{d.storageclass} / {d.op}"
            plt.title(title)
            pdf.savefig()
            plt.close()

        # plot IOPS comparison for all storageclasses
        plot_all_sc(pdf, "IOPS, no fsync", "IOPS", bench_data, fsync=0)
        plot_all_sc(pdf, "IOPS, fsync=1", "IOPS", bench_data, fsync=1)
        # plot bandwidth comparison for all storageclasses
        plot_all_sc(pdf, "Bandwidth, no fsync", "KB/s", bench_data, fsync=0)
        plot_all_sc(pdf, "Bandwidth, fsync=1", "KB/s", bench_data, fsync=1)

        for sc in bench_data.storageclasses:
            plot_sc(
                pdf,
                "IOPS",
                sc,
                bench_data,
            )
            plot_sc(
                pdf,
                "KB/s",
                sc,
                bench_data,
            )
