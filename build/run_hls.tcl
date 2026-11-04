# Vitis HLS flow for the preproc core.   Run from the repository root:
#     vitis_hls -f build/run_hls.tcl
# Part xc7z020clg400-1, 100 MHz target. Reference run used Vitis HLS 2024.1 (see build/README.md).
set root [pwd]
open_project -reset build/hls_proj
set_top preproc
add_files    $root/src/hls/preproc.cpp
add_files    $root/src/hls/preproc.h
add_files -tb $root/sim/hls/tb_preproc.cpp -cflags "-I$root/src/hls"
open_solution -reset solution1 -flow_target vivado
set_part {xc7z020clg400-1}
create_clock -period 10 -name default
puts "===== C SIMULATION ====="
csim_design
puts "===== C SYNTHESIS ====="
csynth_design
puts "===== EXPORT IP ====="
file mkdir build/out
export_design -format ip_catalog -output $root/build/out/preproc_ip.zip
puts "===== ALL DONE ====="
exit
