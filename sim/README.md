# sim/ —— 仿真与验证

一条命令:`bash sim/run_sim.sh`(结果写入 `sim/results/`)。

| 被测对象 | 方法 | 判据 | 本仓库已有结果 |
|---|---|---|---|
| `preproc`(HLS) | `sim/hls/tb_preproc.cpp`:随机 640×480 帧,与逐像素参考(2×2 均值、通道交换)比对;用 `mock/` 里的 ap_* 头文件在 g++ 下运行 | 输出字数、不一致字节数、TLAST 位置 | `results/hls_csim.log`:57600/57600 字,**0 字节不一致**,TLAST 位置正确 → PASS |
| `imu_reader`(RTL) | `rtl/mirror.py`:周期级 Python 镜像 + 行为级 MPU6050 从机 | 初始化寄存器序列、提交次数、时间戳步长 | `results/imu_mirror.log`:寄存器 6B/1A/19/1B/1C 写入正确;时间戳每次 +2000 µs |
| `imu_reader`(RTL) | `rtl/tb_imu_reader.v`(Verilog) | WHO_AM_I、初始化写入、静止偏航≈0、10 毫度/样本积分、时间戳间隔、重新校准、miss 计数 | **待补**:本环境没有 Verilog 仿真器,请在 Vivado xsim 里运行并把日志放到 `results/tb_imu_reader.log` |
| `motor_ctrl`(RTL) | `rtl/tb_motor_ctrl.v` | 占空比 25%/75%、死区补偿 775/925 ‰、请求 0 保持 0、无心跳时看门狗刹车 | **待补**:同上,`results/tb_motor_ctrl.log` |

**在 Vivado xsim 里运行**(示例,在 `sim/` 下):
```
xvlog ../src/rtl/motor_ctrl.v rtl/tb_motor_ctrl.v && xelab tb_motor_ctrl -s m && xsim m -runall
xvlog ../src/rtl/imu_reader.v rtl/tb_imu_reader.v && xelab tb_imu_reader -s i && xsim i -runall
```
有 iverilog 时 `run_sim.sh` 会自动运行这两个测试平台。

**板上验证**:PL 时间戳步长、PS→PL 写延迟、PL 预处理字节一致性、闭环转向精度等实测数据见 `data/`,汇总见设计报告第 7 章。

`rtl/gen_rom.py`、`rtl/rom_cases.txt`:生成 `imu_reader.v` 里 I²C 指令 ROM 的 case 表的脚本和输出。`rtl/mirror1k.py` 没有收录(与 `mirror.py` 仅采样周期不同)。
