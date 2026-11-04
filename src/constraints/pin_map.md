# Pin map (PYNQ-Z2, LVCMOS33)

The real `.xdc` is exported from the Vivado project by `build/export_from_vivado.tcl` into this directory.
Until then this table (verified on the board) is the reference.

| Signal | Pin | Header | Function |
|---|---|---|---|
| IN1 | Y17 | PMODA | L298N direction, motor A |
| IN2 | Y16 | PMODA | L298N direction, motor A |
| IN3 | Y19 | PMODA | L298N direction, motor B |
| IN4 | Y18 | PMODA | L298N direction, motor B |
| ENA | W19 | PMODA | PWM, motor A |
| ENB | W18 | PMODA | PWM, motor B |
| SCL | V12 | PMODB | MPU6050 (GY-521) I2C clock |
| SDA | W13 | PMODB | MPU6050 (GY-521) I2C data (bidirectional, needs IOBUF) |
| LD0 | - | on-board | lit when the motor watchdog has tripped |

AXI GPIO map: 0x41200000 (duty@0x0, ctrl@0x8), 0x41210000 (cfg@0x0, ts@0x8), 0x41220000 (status@0x0, yaw milli-deg@0x8), 0x41230000 (raw@0x0, now_us@0x8); AXI DMA 0x41E00000.
