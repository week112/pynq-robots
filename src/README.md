# src/ —— 设计源码

| 路径 | 实现方式 | 说明 |
|---|---|---|
| `rtl/motor_ctrl.v` | RTL | 双路 PWM(10 kHz,0~1000)、四路方向、死区补偿 `min_duty`、200 ms 心跳看门狗(超时刹车并点亮 LD0) |
| `rtl/imu_reader.v` | RTL | MPU6050 的 I²C 主机(400 kHz)、2000 µs 定时采样、µs 时间戳、陀螺仪 Z 轴零偏校准与偏航积分(毫度)、单周期提交 + 序号(seqlock) |
| `hls/preproc.cpp, preproc.h` | Vitis HLS | 640×480 BGR888 → 320×240 RGB888,2×2 均值 `(sum+2)>>2`,AXI-Stream 32 位;与 OpenCV `INTER_AREA` 逐字节一致 |
| `ps/car_pl.py` | PS 软件(PYNQ/Python) | Overlay 加载、电机/IMU 驱动、脉冲式闭环转向、航向保持、避障主循环 `run_avoid`、试验记录 `run_trials` |
| `ps/server_v2.py` | PC 软件(Python) | YOLOv8n 检测服务(TCP 9001),返回目标数、中心、面积占比、推理耗时、类别 |
| `constraints/pin_map.md` | 约束 | 引脚表;真正的 `.xdc` 由 `build/export_from_vivado.tcl` 导出到此处 |

**器件声明**:AMD Zynq-7000 **XC7Z020-1CLG400C**(PYNQ-Z2),PYNQ 镜像 3.1.1。

**软硬件划分**:PL 负责需要确定性的部分——电机 PWM 与看门狗、IMU 采样/时间戳/偏航积分、图像预处理核(基准评测用);PS 负责控制逻辑与通信;PC(可替换为 AMD Ryzen AI PC)负责 YOLO 推理。
