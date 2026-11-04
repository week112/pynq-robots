# skill/ —— 技能包

本目录是在"视觉—惯性协同避障小车"开发和与大模型协作过程中沉淀的可复用经验。**除 `pitfalls.md` 和 `prompts/` 中少数条目外,工具与题目无关**:换题目、换板卡仍可使用(`pynq_safe_overlay`、`latency_report`、`golden_compare`、`seqlock_snapshot` 面向 PYNQ/Zynq 通用场景)。

每一项都写明:适用场景、使用方法、已验证效果、失效条件、提炼来源(从哪些失败或观察中总结)。

| 条目 | 类型 | 一句话 | 自测 |
|---|---|---|---|
| `pynq_safe_overlay/` | 校验脚本 / 踩坑 | 同一比特流只加载一次、先停旧线程,避免重复运行单元导致整板死机 | `python3 pynq_safe_overlay/selftest.py` |
| `latency_report/` | 校验脚本 | 原始耗时 csv → P50/P95/P99/P99.9/max 与超阈值次数,输出 markdown/图 | `python3 latency_report/latency_report.py data/raw/pre_arm_baseline.csv` |
| `golden_compare/` | 校验脚本 | PL/HLS 输出与软件黄金参考逐字节比对(含 2×2 均值参考) | `python3 golden_compare/golden_compare.py selftest` |
| `seqlock_snapshot/` | 案例模板 | PL 同周期提交数据+序号,PS 读-数-读得到一致快照(含 Verilog 片段) | `python3 seqlock_snapshot/selftest.py` |
| `prompts/` | 提示词工作流 | 划分、先镜像后上板、日志诊断、报告只用数据 4 个模板 | — |
| `pitfalls.md` | 踩坑清单 | 8 条触发条件与排查步骤 | — |

## 诚实的边界

- 离板自测只证明逻辑正确;"已验证效果"中涉及实板的结论来自本队一台 PYNQ-Z2 的使用反馈,没有做大样本统计。
- 本队尚未在第二块板卡或第二个题目上复用过这些工具,"通用"是按其不依赖题目代码来判断的,不是复用结果。
- 我们没有在 `pynq_safe_overlay` 之外提供 DMA 封装、寄存器映射生成器等更大的 Skill,时间不够,也没有可验证的素材。
