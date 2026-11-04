#!/usr/bin/env python3
"""Recompute every number quoted in the design report from the raw logs in data/raw/.
Usage:  python3 data/analyze.py            (prints a summary and writes data/reference/summary.json)
Only needs numpy.  No hidden state: raw csv in, numbers out.
"""
import csv, glob, json, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
OUT = os.path.join(HERE, "reference", "summary.json")


def pct(a, qs=(50, 95, 99)):
    a = np.asarray(a, float)
    d = {f"p{q}": float(np.percentile(a, q)) for q in qs}
    d.update(n=int(a.size), min=float(a.min()), max=float(a.max()), mean=float(a.mean()))
    return d


def one_col(name):
    return np.loadtxt(os.path.join(RAW, name), comments="#")


def trial_rows():
    rows = []
    for f in sorted(glob.glob(os.path.join(RAW, "trial_bottle_*.csv")), key=lambda p: int(p.split("_")[-1][:-4])):
        with open(f) as fh:
            rows.append(list(csv.DictReader(fh)))
    return rows


def main():
    S = {}
    # --- first 3 frames of each trial are dropped (camera / TCP warm-up)
    lat, inf, n_all, turns, trig = [], [], 0, [], {}
    for tr in trial_rows():
        n_all += len(tr)
        for i, r in enumerate(tr):
            if i >= 3:
                inf.append(float(r["infer_ms"]))              # inference time: every frame after warm-up (n=271)
                if r["action"] == "forward":
                    lat.append(float(r["latency_ms"]))        # latency: forward frames only (n=253)
            if r["action"].startswith("turn"):
                turns.append(abs(float(r["turn_err_deg"])))
                trig[r["cls"]] = trig.get(r["cls"], 0) + 1
    S["e2e_latency_ms"] = pct(lat, (50, 95, 99))
    S["infer_ms"] = pct(inf, (50, 95, 99))
    S["frames_total"] = n_all
    # --- turning accuracy of the pulse-based closed loop (all turn events in the trials)
    t = np.array(turns)
    S["turn_events"] = int(t.size)
    S["turn_abs_err_median_deg"] = float(np.median(t))
    S["turn_abs_err_le3deg"] = int((t <= 3).sum())
    S["turn_abs_err_max_deg"] = float(t.max())
    S["trigger_class_counts_coco_id"] = trig
    # --- PL vs ARM pre-processing (640x480 -> 320x240)
    arm = one_col("pre_arm_baseline.csv"); pl = one_col("pl_preproc_core.csv")
    S["preproc_arm_ms"] = pct(arm, (50, 95, 99))
    S["preproc_pl_core_ms"] = pct(pl, (50, 95, 99))
    S["preproc_core_speedup_p50"] = S["preproc_arm_ms"]["p50"] / S["preproc_pl_core_ms"]["p50"]
    # --- PS -> PL register write latency (us) and PL timestamp step
    w = one_col("ps_pl_write_latency.csv")
    S["ps_pl_write_us"] = pct(w, (50, 95, 99, 99.9))
    S["ps_pl_write_over_100us"] = int((w > 100).sum())
    ts = one_col("pl_imu_ts_step.csv")
    S["pl_ts_step_us"] = dict(n=int(ts.size), min=float(ts.min()), max=float(ts.max()), all_equal_2000=bool((ts == 2000).all()))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(S, open(OUT, "w"), indent=2, ensure_ascii=False)
    print(json.dumps(S, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
