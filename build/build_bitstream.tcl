# Rebuild the bitstream from text sources.   vivado -mode batch -source build/build_bitstream.tcl   (from repo root)
# PRE-CONDITIONS: build/vivado/motor_bd.tcl (made by export_from_vivado.tcl) and build/out/preproc_ip.zip (run_hls.tcl)
# STATUS: written to the standard Vivado flow; it has NOT been executed in the author's environment yet
#         (the author's project was built interactively). See build/README.md.
set root [pwd]
create_project -force car_build $root/build/vivado_proj -part xc7z020clg400-1
set_property ip_repo_paths $root/build/out [current_project]
add_files [glob $root/src/rtl/*.v]
if {[llength [glob -nocomplain $root/src/constraints/*.xdc]]} { add_files -fileset constrs_1 [glob $root/src/constraints/*.xdc] }
update_ip_catalog
source $root/build/vivado/motor_bd.tcl
make_wrapper -files [get_files motor_bd.bd] -top
add_files -norecurse [glob $root/build/vivado_proj/car_build.gen/sources_1/bd/motor_bd/hdl/motor_bd_wrapper.v]
set_property top motor_bd_wrapper [current_fileset]
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
open_run impl_1
report_utilization    -file $root/build/reports/rebuild_utilization.rpt
report_timing_summary -file $root/build/reports/rebuild_timing_summary.rpt
file mkdir $root/board/overlay
file copy -force $root/build/vivado_proj/car_build.runs/impl_1/motor_bd_wrapper.bit $root/board/overlay/pipeline.bit
puts "bitstream -> board/overlay/pipeline.bit"
