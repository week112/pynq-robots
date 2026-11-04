#!/usr/bin/env bash
# Self-check of this repository (no Vivado, no board needed).  bash build/check_repo.sh
set -e
cd "$(dirname "$0")/.."
echo "== 1. path names: only [a-z0-9_.-] and no spaces (rule 3.3.5.4) =="
bad=$(find . -mindepth 1 | sed 's|^\./||' | tr '/' '\n' | grep -v -E '^[a-z0-9_.-]+$' | grep -v -E '^(README\.md|LICENSE)$' || true)
if [ -n "$bad" ]; then echo "BAD NAMES:"; echo "$bad"; exit 1; else echo "ok"; fi
echo "== 2. simulations =="; bash sim/run_sim.sh >/dev/null && echo "ok (see sim/results)"
echo "== 3. recompute report numbers from raw data =="; python3 data/analyze.py > /dev/null && echo "ok (data/reference/summary.json)"
echo "== 4. skill self-tests =="
for d in pynq_safe_overlay seqlock_snapshot; do (cd skill/$d && python3 selftest.py | tail -1); done
python3 skill/golden_compare/golden_compare.py selftest | tail -1
python3 skill/latency_report/latency_report.py data/raw/pre_arm_baseline.csv --label arm_preproc | tail -1
echo "ALL CHECKS DONE"
