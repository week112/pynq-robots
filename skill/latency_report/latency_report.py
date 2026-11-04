#!/usr/bin/env python3
"""latency_report.py -- turn a raw latency log into the numbers a competition report needs.

    python3 latency_report.py FILE.csv [--col 0] [--label NAME] [--unit ms] [--md out.md] [--png out.png] [--drop N] [--thr 100]

Reads a one-column (or chosen column) csv/txt of samples (lines starting with # are ignored) and prints
n, min, mean, P50, P95, P99, P99.9, max and how many samples exceed --thr (same unit).  Always keeps the raw
file: this tool never edits it.   Needs numpy;  --png needs matplotlib.
"""
import argparse, sys
import numpy as np


def stats(a, thr=None):
    a = np.asarray(a, float)
    d = dict(n=a.size, min=a.min(), mean=a.mean(), p50=np.percentile(a, 50), p95=np.percentile(a, 95),
             p99=np.percentile(a, 99), p999=np.percentile(a, 99.9), max=a.max())
    if thr is not None:
        d["over_thr"] = int((a > thr).sum())
    return d


def md_row(label, d, unit):
    return (f"| {label} | {d['n']} | {d['min']:.3f} | {d['mean']:.3f} | {d['p50']:.3f} | {d['p95']:.3f} | "
            f"{d['p99']:.3f} | {d['p999']:.3f} | {d['max']:.3f} |")


MD_HEAD = ("| 项目 | n | min | mean | P50 | P95 | P99 | P99.9 | max |\n|---|---|---|---|---|---|---|---|---|")


def load(path, col=0, drop=0):
    arr = np.loadtxt(path, delimiter=",", comments="#", ndmin=2)
    return arr[drop:, col]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("file"); ap.add_argument("--col", type=int, default=0); ap.add_argument("--label", default=None)
    ap.add_argument("--unit", default="ms"); ap.add_argument("--md"); ap.add_argument("--png")
    ap.add_argument("--drop", type=int, default=0, help="drop the first N warm-up samples")
    ap.add_argument("--thr", type=float, default=None)
    a = ap.parse_args(argv)
    x = load(a.file, a.col, a.drop); label = a.label or a.file
    d = stats(x, a.thr)
    line = md_row(f"{label} ({a.unit})", d, a.unit)
    print(MD_HEAD); print(line)
    if a.thr is not None:
        print(f"samples > {a.thr} {a.unit}: {d['over_thr']}")
    if a.md:
        open(a.md, "w").write(MD_HEAD + "\n" + line + "\n")
    if a.png:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(8, 2.8))
        ax[0].plot(x, lw=.6); ax[0].set_title("time series"); ax[0].set_ylabel(a.unit)
        ax[1].hist(x, bins=60); ax[1].set_yscale("log"); ax[1].set_title("histogram (log y)"); ax[1].set_xlabel(a.unit)
        fig.tight_layout(); fig.savefig(a.png, dpi=150)
    return d


if __name__ == "__main__":
    main()
