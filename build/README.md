# build/ —— 构建脚本与综合实现报告

## 工具版本声明
参考设计使用 **Vivado 2024.1 / Vitis HLS 2024.1**(Windows),器件 `xc7z020clg400-1`。选题指南推荐 2026.1 或 2025.2:**本作品没有用推荐版本构建**,更换版本需要重新生成 IP、重新运行 `build_bitstream.tcl`,我们没有验证过新版本。

## 脚本
| 脚本 | 作用 | 状态 |
|---|---|---|
| `run_hls.tcl` | 从仓库根目录运行 `vitis_hls -f build/run_hls.tcl`:C 仿真 → C 综合 → 导出 IP 到 `build/out/preproc_ip.zip` | 由作者实际使用的脚本改为相对路径;C 综合报告见 `reports/preproc_csynth.rpt` |
| `export_from_vivado.tcl` | 在作者的 Vivado 工程里运行一次:导出块设计 `build/vivado/motor_bd.tcl`、约束、`pipeline.bit/.hwh`、利用率/时序/功耗报告 | **待作者运行**(作者的工程是图形界面交互建立的,仓库里还没有文本化的块设计) |
| `build_bitstream.tcl` | 用导出的块设计从零建工程并出比特流 | 按标准流程编写,**尚未在作者环境执行过** |
| `check_repo.sh` | 不依赖 Vivado/板子的自检:文件名规则、仿真、数据复算、技能包自测 | 已运行通过 |

## 综合与实现结果(`reports/`)
| 报告 | 关键数字 |
|---|---|
| `vivado_utilization.rpt`(100 MHz,`motor_bd_wrapper`) | Slice LUT 4,428(8.32%)、FF 6,740(6.33%)、Slice 2,216(16.66%)、BRAM 3 个 RAMB36 等效(2.14%)、DSP 5(2.27%)、IO 9、BUFG 1 |
| `vivado_power.rpt` | 总功耗估算 1.432 W(PS7 1.256 W;器件静态 0.138 W;PL 用户逻辑约 0.038 W);结温 41.5 °C;**置信度 Low**(Vivado 估算,不是实测) |
| `preproc_csynth.rpt` | HLS 估算时钟 7.183 ns(目标 10 ns);延迟 232,562 周期 = 2.326 ms(未含 DMA 传输开销) |
| 时序 | 作者在 Vivado 中读到 WNS +1.024 ns、WHS +0.031 ns、TNS/THS 0、失败布线 0(估计 Fmax ≈ 111 MHz)。**时序报告原文件尚未收录**,运行 `export_from_vivado.tcl` 会生成 `vivado_timing_summary.rpt`。 |

HLS 预处理核:LUT 1,124、FF 353、BRAM 2、DSP 0。

## 优化前后对比(图像预处理 640×480 → 320×240)
| 指标 | ARM 软件(OpenCV) | PL 核(HLS + DMA) | 变化 |
|---|---|---|---|
| 核心耗时 P50(n=1000 / 500) | 13.013 ms | 3.235 ms | **4.0× 加速** |
| P95 / P99 / max | 13.163 / 13.712 / 15.146 ms | 3.324 / 3.381 / 3.547 ms | 尾部更紧 |
| PL 端到端(含 PS 侧准备)P50 | — | 6.91 ms | 相对 ARM 1.88×;**P95/P99/max 尚未测,待补** |
| 资源代价 | — | LUT 1,124(2.1%)、FF 353、BRAM 2、DSP 0 | 占整体设计 LUT 约 25% |
| 正确性 | — | 与 `INTER_AREA` 逐字节一致 | — |
数据来源:`data/raw/pre_arm_baseline.csv`、`data/raw/pl_preproc_core.csv`;复算:`python3 data/analyze.py`。

诚实说明:该核没有进入当前主控制环(摄像头输出 JPEG,PC 端直接解码)。
