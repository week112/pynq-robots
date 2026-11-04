# Run this ONCE inside the author's Vivado GUI (Tcl console) to dump the block design and constraints
# into the repository, so that others can rebuild from text instead of a binary project.
#   cd <repo>/build ;  source export_from_vivado.tcl
# Adjust $proj if your project lives elsewhere. Reference project: H:/vivado_proj/pwm_demo/pwm_demo.xpr
set proj  "H:/vivado_proj/pwm_demo/pwm_demo.xpr"
set repo  [file normalize [file join [pwd] ".."]]
open_project $proj
file mkdir $repo/build/vivado
open_bd_design [get_files motor_bd.bd]
write_bd_tcl -force -no_ip_version $repo/build/vivado/motor_bd.tcl
foreach x [get_files -of_objects [get_filesets constrs_1] *.xdc] { file copy -force $x $repo/src/constraints/ }
# bitstream + hwh -> board/overlay (renamed to what car_pl.py expects)
set impl [get_property DIRECTORY [get_runs impl_1]]
file mkdir $repo/board/overlay
file copy -force $impl/motor_bd_wrapper.bit $repo/board/overlay/pipeline.bit
set hwh [glob -nocomplain [file dirname $proj]/*.gen/sources_1/bd/motor_bd/hw_handoff/motor_bd.hwh]
if {[llength $hwh]} { file copy -force [lindex $hwh 0] $repo/board/overlay/pipeline.hwh }
report_utilization -file $repo/build/reports/vivado_utilization.rpt
report_timing_summary -file $repo/build/reports/vivado_timing_summary.rpt
report_power -file $repo/build/reports/vivado_power.rpt
puts "exported to $repo"
