#!/usr/bin/env bash
# Run every simulation that can run without Vivado.   Usage: bash sim/run_sim.sh
# 1) HLS C-simulation of the pre-processing core (g++ + mock ap_* headers, bit-exact check vs a reference)
# 2) Cycle-level python mirror of imu_reader.v against a behavioural MPU6050
# 3) If iverilog is installed, also run the two Verilog testbenches
set -e
cd "$(dirname "$0")"
mkdir -p results
echo "== [1/3] HLS csim (preproc) =="
g++ -O2 -I hls/mock -I ../src/hls hls/tb_preproc.cpp ../src/hls/preproc.cpp -o results/tb_preproc.bin
./results/tb_preproc.bin | tee results/hls_csim.log
echo "== [2/3] python mirror of imu_reader =="
python3 rtl/mirror.py | tee results/imu_mirror.log
echo "== [3/3] Verilog testbenches (needs iverilog) =="
if command -v iverilog >/dev/null 2>&1; then
  iverilog -g2012 -o results/tb_motor.vvp rtl/tb_motor_ctrl.v ../src/rtl/motor_ctrl.v && vvp results/tb_motor.vvp | tee results/tb_motor_ctrl.log
  iverilog -g2012 -o results/tb_imu.vvp  rtl/tb_imu_reader.v  ../src/rtl/imu_reader.v  && vvp results/tb_imu.vvp  | tee results/tb_imu_reader.log
else
  echo "iverilog not found: run tb_motor_ctrl.v / tb_imu_reader.v in Vivado xsim instead (see sim/README.md)"
fi
