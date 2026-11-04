# data/ —— 测试数据与参考结果

## 原始数据 `raw/`(未经修改的板上输出)
| 文件 | 内容 | 样本数 |
|---|---|---|
| `pl_imu_ts_step.csv` | PL 时间戳相邻样本间隔(µs) | 1497,全部 2000 |
| `ps_pl_write_latency.csv` | PS→PL 寄存器写延迟(µs) | 5000 |
| `pre_arm_baseline.csv` | ARM(OpenCV)预处理耗时(ms) | 1000 |
| `pl_preproc_core.csv` | PL 预处理核耗时(ms) | 500 |
| `closed_loop_bursts.csv` | 脉冲式闭环转向过程:`t,i,dir,ms,yaw_before,yaw_after` | 75 行 |
| `trials.csv` | 10 次试验汇总:`result` 1=成功 2=擦碰 3=没触发 4=作废 | 10 |
| `trial_bottle_1..10.csv` | 逐帧日志:帧号、PL 时间戳、偏航、目标数、cx、面积、推理耗时、动作、端到端延迟、转向误差、ybot、类别 | 297 帧 |
| `avoid_log.csv` | 最近一次 `run_avoid` 的日志 | 1 |

注意:试验文件名里的 `bottle` 是计划测试的对象;实际触发转向的物体见 `trials.csv` 的 `trigger_cls`(COCO 编号:58 盆栽、0 人、56 椅子、39 水瓶…)。**23 次转向中只有 2 次由水瓶触发**,因此这批数据不能作为"水瓶避障成功率"使用,水瓶正式统计待补。

## 复算 `analyze.py`
`python3 data/analyze.py` → 打印并写入 `reference/summary.json`。统计口径:每次试验丢弃前 3 帧(预热);端到端延迟只用直行帧(n=253),推理耗时用预热后全部帧(n=271),转向误差用全部 23 次转向。

## 参考结果 `reference/summary.json`
端到端延迟 P50 14.13 / P95 18.93 / P99 23.48 / max 27.32 ms;推理 P50 12.47 / P95 16.56 / P99 18.49 ms;转向误差中位数 1.77°,21/23 次 ≤3°(最大 28.11°);PS→PL 写 P50 23.74 µs、P99.9 233 µs、最大 702 µs(11 次 >100 µs);PL 时间戳步长 1497/1497 为 2000 µs;预处理 ARM 13.013 ms vs PL 核 3.235 ms(4.0×)。

## 没有的数据(待补)
- 水瓶避障正式成功率(≥10 次,干净场景);
- PL 预处理端到端 P95/P99/max;
- 吞吐与丢包实测(当前吞吐 ≈3.4 Mbit/s 是由 ≈25 fps × ≈17 KB/帧推算的);
- 功耗实测(目前只有 Vivado 估算)。
