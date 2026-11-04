# board/ —— 上板工程、运行脚本

## 内容
| 路径 | 说明 | 状态 |
|---|---|---|
| `overlay/pipeline.bit`、`overlay/pipeline.hwh` | 小车的比特流与硬件描述 | **待放入**:运行 `build/export_from_vivado.tcl`,或手动复制 `motor_bd_wrapper.bit` 并重命名为 `pipeline.bit`(`.hwh` 在工程的 `*.gen/sources_1/bd/motor_bd/hw_handoff/` 下,重命名为 `pipeline.hwh`) |
| `run_demo.py` | 板上命令行运行入口(`sudo python3 run_demo.py 7`) | 薄封装,调用 `src/ps/car_pl.py` |
| `notebooks/bringup_and_baseline.ipynb` | 早期点亮与基线实验:GPIO 驱动电机、Pmod IIC 读 MPU6050、UDP 往返、图像流吞吐、PC 推理流水线基线 | 已清除输出 |

## 板上运行(Jupyter 流程,所有实测数据均来自此流程)
1. 电脑与板子网线直连:电脑 192.168.2.1,板子 192.168.2.99。
2. 电脑:`python server_v2.py`(需要 `ultralytics`、`opencv-python`、`yolov8n.pt`),看到"等待连接..."。
3. 浏览器打开 `http://192.168.2.99:9090`(密码 `xilinx`),把 `car_pl.py`、`pipeline.bit`、`pipeline.hwh` 传到同一目录。
4. 笔记本里(**每次运行前先 Kernel → Restart**,见 `skill/pitfalls.md` 第 1 条):
```python
from car_pl import *
car = Car("pipeline.bit")      # 保持小车静止 3 秒,完成 IMU 零偏校准
vis = Vision("192.168.2.1")
probe(vis)                      # 检查 AI 能否识别物体
run_avoid(car, vis, seconds=7)  # 避障
run_trials(car, vis, "bottle", n=10)  # 正式统计(生成 trials.csv 与 trial_*.csv)
```
更详细的小白版步骤见 `report/user_guide.docx`。

## 实测输出
全部在 `data/raw/`(见 `data/README.md`),复算脚本 `data/analyze.py`。
