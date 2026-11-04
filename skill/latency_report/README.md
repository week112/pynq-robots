# latency_report

- **适用场景**:任何需要在报告里给出 P50/P95/P99/P99.9/max 与超阈值次数的延迟、耗时测量(PS→PL 写、DMA、推理、端到端),与题目无关。
- **使用方法**:`python3 latency_report.py data.csv --label name --unit ms --thr 14 --md out.md --png out.png`;`--drop N` 丢弃预热样本。输出 markdown 表格,可直接贴进报告。原始文件只读不改。
- **已验证效果**:用它复算了本队 `data/raw/pre_arm_baseline.csv`(ARM 预处理,n=1000)得到 P50 13.013 / P95 13.163 / P99 13.712 / max 15.146 ms,与报告一致;`data/analyze.py` 对全部数据做同样的复算。
- **失效条件**:只做描述性统计,不判断样本是否独立或平稳;样本太少(<100)时 P99 没有意义。
- **提炼来源**:竞赛要求报告给出尾延迟而非平均值;本队 PS→PL 写延迟 P50 为 23.7 µs,但 P99.9 达 233 µs、最大 702 µs,只看平均会完全掩盖这个尾部。
