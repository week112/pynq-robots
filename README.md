# FPGA Vision-Inertial Cooperative Obstacle-Avoidance Car
# 基于 FPGA 视觉—惯性协同的自主避障机器人

全国大学生嵌入式芯片与系统设计竞赛 2026 · AMD 赛道 · 3.3 自主选题(按具身智能标准实现)
队伍:[待补:队名 / 学校 / 队员 / 指导教师]　组别:[待补:初级组或高级组]

## 1 这是什么
在 PYNQ-Z2 上做的一台自主避障小车。PL 里自研两个 Verilog 核(PL 电机控制核:双路 PWM + 200 ms 硬件看门狗;PL IMU 读取核:I²C 采样 + µs 时间戳 + 偏航角积分),并用 Vitis HLS 做了图像预处理核;PS 用 Python 做避障控制;YOLOv8n 目标检测运行在 PC 上(可换成 AMD Ryzen AI PC)。

**器件声明**:AMD Zynq-7000 XC7Z020-1CLG400C(PYNQ-Z2),PYNQ 镜像 3.1.1。
**工具版本**:Vivado / Vitis HLS **2024.1**(选题指南推荐 2026.1 / 2025.2,本作品未用推荐版本构建,见 `build/README.md`)。
**开源协议**:MIT(`LICENSE`)。

## 2 关键实测结果(原始数据在 `data/raw/`,`python3 data/analyze.py` 可复算)
| 指标 | 结果 |
|---|---|
| PL 采样时间戳间隔 | 1497/1497 个样本均为 2000 µs |
| PS→PL 控制写延迟(n=5000) | P50 23.74 / P95 24.86 / P99 33.64 / P99.9 233.2 / max 702.3 µs |
| 画面到手 → 电机指令写出(n=253 直行帧) | P50 14.13 / P95 18.93 / P99 23.48 / max 27.32 ms |
| 图像预处理 ARM vs PL 核 | 13.013 ms vs 3.235 ms(4.0×),与 INTER_AREA 逐字节一致 |
| 闭环转向误差(23 次) | 中位数 1.77°,21/23 次 ≤3° |
| 资源(100 MHz) | LUT 8.32% / FF 6.33% / BRAM 2.14% / DSP 2.27%;WNS +1.024 ns |
| 功耗 | 1.432 W(Vivado 估算,置信度 Low;PL 用户逻辑约 0.038 W) |
| 链路 | 297 帧,1 帧坏帧被跳过(≈0.3%),0 次超时 |

## 3 诚实的边界
- **检测在 PC 上**:YOLO 经网线在电脑上运行,小车本体(PS+PL)负责控制。若比赛要求完全脱离电脑运行,需要把检测搬到板子或随车算力上,本版本**尚未做到**。
- 图像预处理核已验证但**没有接入当前主控制环**(摄像头输出 JPEG,PC 端直接解码)。
- 10 次试验里 23 次转向,**只有 2 次由水瓶触发**,其余由盆栽/椅子/人等触发;水瓶避障正式成功率**待补**。
- 吞吐(≈3.4 Mbit/s)是推算值,**未实测**;丢包只统计了帧级(1/297 坏帧)。
- 功耗是 Vivado 估算,不是实测。
- 本仓库中标"待补"的文件/数据:`board/overlay/pipeline.bit|hwh`、Verilog 测试平台的 xsim 日志、文本化块设计、时序报告原文、大模型对话的完整原始导出。

## 4 目录
```
README.md                 本文件
LICENSE                   MIT
src/                      设计源码:rtl/(Verilog) hls/(Vitis HLS) ps/(Python) constraints/
sim/                      仿真与验证:run_sim.sh、测试平台、仿真结果
build/                    构建脚本(HLS、Vivado)、综合/实现/功耗报告、check_repo.sh
board/                    上板:overlay/(bit+hwh,待放入)、run_demo.py、notebooks/
data/                     raw/ 原始实测数据;analyze.py 复算;reference/summary.json
skill/                    技能包(README.md + 4 个通用工具 + 提示词工作流 + 踩坑清单)
report/                   design_report.docx/.pdf、user_guide.docx(小白操作教程)、llm_log/(大模型协作记录)
```

## 5 复现
**不需要 Vivado 和板子**(约 1 分钟):
```
bash build/check_repo.sh
```
它检查文件名规则、运行 HLS C 仿真和 IMU 镜像仿真、从原始数据复算报告数字、运行技能包自测。

**上板复现**(需要 PYNQ-Z2、L298N、TT 电机、MPU6050、USB 摄像头、一台装有 `ultralytics` 的电脑):按 `board/README.md` 或 `report/user_guide.docx`(面向零基础,逐步图文)。
**从源码重建比特流**:`vitis_hls -f build/run_hls.tcl`,然后按 `build/README.md` 导出/重建块设计(脚本尚未在作者环境执行过)。

## 6 文档
- 设计报告:`report/design_report.docx`(含 PDF 版)
- 使用教程:`report/user_guide.docx`
- 大模型协作记录:`report/llm_log/`
- 技能包说明:`skill/README.md`
