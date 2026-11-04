#!/usr/bin/env python3
"""golden_compare.py -- bit-exact comparison of a hardware (PL / HLS) result against a software golden model.

Library:
    from golden_compare import compare, box2x2_rgb
    ref = box2x2_rgb(frame_bgr)          # 2x2 box average, (sum+2)>>2, BGR->RGB  (== cv2.INTER_AREA for exact 2x)
    rep = compare(hw_out, ref, "preproc")  # dict: n, mismatches, first_idx, max_abs_diff, ok
CLI:
    python3 golden_compare.py selftest     # checks the reference against OpenCV INTER_AREA if cv2 is installed
Rule of thumb it encodes: report the MISMATCH COUNT and the first few positions, not just "looks right".
"""
import sys
import numpy as np


def box2x2_rgb(bgr):
    a = bgr.astype(np.uint16)
    s = a[0::2, 0::2] + a[0::2, 1::2] + a[1::2, 0::2] + a[1::2, 1::2]
    return ((s + 2) >> 2).astype(np.uint8)[..., ::-1]


def compare(out, ref, name="result", show=5):
    out = np.asarray(out); ref = np.asarray(ref)
    if out.shape != ref.shape:
        rep = dict(name=name, ok=False, error=f"shape {out.shape} != {ref.shape}")
    else:
        bad = np.flatnonzero(out.reshape(-1) != ref.reshape(-1))
        diff = np.abs(out.astype(int) - ref.astype(int))
        rep = dict(name=name, n=int(out.size), mismatches=int(bad.size), first_idx=bad[:show].tolist(),
                   max_abs_diff=int(diff.max()), ok=bool(bad.size == 0))
    print(f"[golden] {name}: " + ("PASS bit-exact" if rep["ok"] else f"FAIL {rep}"))
    return rep


def selftest():
    rng = np.random.default_rng(1)
    img = rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)
    ref = box2x2_rgb(img)
    assert ref.shape == (240, 320, 3)
    try:
        import cv2
        cv = cv2.resize(img, (320, 240), interpolation=cv2.INTER_AREA)[..., ::-1]
        assert compare(cv, ref, "box2x2 vs cv2.INTER_AREA")["ok"]
    except ImportError:
        print("cv2 not installed: skipped the OpenCV cross-check")
    bad = ref.copy(); bad[3, 4, 1] ^= 1
    assert not compare(bad, ref, "deliberate 1-LSB error")["ok"]
    print("golden_compare selftest PASS")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest()
    else:
        print(__doc__)
