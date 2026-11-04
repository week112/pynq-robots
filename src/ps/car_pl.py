"""car_pl.py : PYNQ-Z2 避障小车，PL 电机控制 + PL IMU(yaw) + 视觉(TCP 到 PC 的 YOLO 服务)
用法(在 Jupyter 里):
    from car_pl import Car, Vision, run_avoid
    car = Car("pipeline.bit")           # 加载比特流，等待 IMU 就绪(车要静止)
    car.recalibrate()                   # 陀螺仪零偏校准(车要静止)
    car.pulse_turn(+90)                 # 向左(逆时针)转 90°，闭环
    vis = Vision("192.168.2.1")         # 摄像头 + 连接 PC 的 server.py
    run_avoid(car, vis, seconds=20)     # 避障主循环
    vis.close(); car.close()
约定: yaw 逆时针(左转)为正。电机 A=右轮, B=左轮; set(a,b) 范围 -1000..1000, 正=前进。
"""
import os, time, threading, struct, socket, csv
import numpy as np
from pynq import Overlay, MMIO

BAD = 0xFFFFFFFF


def _s32(x):
    x &= 0xFFFFFFFF
    return x - (1 << 32) if x & 0x80000000 else x


SMALL_CLS = {24, 25, 26, 28, 32, 39, 40, 41, 67, 73, 75, 77}   # 小物体类别(与 server_v2.py 的 SMALL 一致), 用 bottle_area_thr
_ACTIVE_CAR = None
_ACTIVE_VIS = None


def _load_overlay(bit):
    """已经加载过同一个比特流就不要重新下载: 在心跳线程还在访问 AXI 时重配 PL 会让整块板子死机"""
    try:
        from pynq import PL
        cur = PL.bitfile_name
        if cur and os.path.abspath(bit) == os.path.abspath(cur):
            return Overlay(bit, download=False)
    except Exception:
        pass
    return Overlay(bit)


class Car:
    G0, G1, G2, G3 = 0x41200000, 0x41210000, 0x41220000, 0x41230000

    def __init__(self, bit="pipeline.bit", min_duty=0):
        global _ACTIVE_CAR
        if _ACTIVE_CAR is not None:          # 重复运行本 cell: 先停掉上一个实例的心跳线程
            try:
                _ACTIVE_CAR.close()
                _ACTIVE_CAR.th.join(1.0)
            except Exception:
                pass
        self.ol = _load_overlay(bit)
        self.g0 = MMIO(self.G0, 0x10)   # 电机 duty / ctrl
        self.g1 = MMIO(self.G1, 0x10)   # ch1 写 cfg, ch2 读 ts
        self.g2 = MMIO(self.G2, 0x10)   # ch1 status, ch2 yaw
        self.g3 = MMIO(self.G3, 0x10)   # ch1 raw, ch2 now_us
        self.min_duty = min_duty
        self.k_ms_per_deg = 6.0         # 实测: 120 ms 满功率脉冲约转 20°
        self.t_first_cmd = None
        self.lock = threading.Lock()
        self.da = self.db = 0
        self.dira = self.dirb = 0
        self.hb = 0
        self.run = True
        self._push(0, 0)
        self.th = threading.Thread(target=self._loop, daemon=True)
        self.th.start()
        _ACTIVE_CAR = self
        t0 = time.time()
        while time.time() - t0 < 3.0:
            st = self.g2.read(0x00)
            if (st & 1) and ((st >> 1) & 1):
                break
            time.sleep(0.05)
        else:
            raise RuntimeError("IMU 未就绪(init_done/who_ok=0)，检查接线和比特流")

    # ------------------------------------------------ 电机 (PL)
    def _loop(self):
        while self.run:
            with self.lock:
                self.hb ^= 1
                duty = ((self.db & 0xFFFF) << 16) | (self.da & 0xFFFF)
                ctrl = (self.hb << 5) | (1 << 4) | (self.dirb << 2) | self.dira
            self.g0.write(0x00, duty)
            self.g0.write(0x08, ctrl)
            time.sleep(0.02)

    @staticmethod
    def _conv(x):
        x = max(-1000, min(1000, int(x)))
        return (0, 0) if x == 0 else ((1, x) if x > 0 else (2, -x))

    def set(self, a, b):
        da, xa = self._conv(a)
        db, xb = self._conv(b)
        with self.lock:
            self.dira, self.da = da, xa
            self.dirb, self.db = db, xb

    def stop(self, brake_s=0.12):
        with self.lock:
            self.dira = self.dirb = 3
            self.da = self.db = 1000
        time.sleep(brake_s)
        with self.lock:
            self.dira = self.dirb = 0
            self.da = self.db = 0

    def close(self):
        try:
            self.stop()
        finally:
            self.run = False        # 心跳停止 -> PL 看门狗自动刹车

    # ------------------------------------------------ IMU (PL)
    def _push(self, sel=0, calib=0):
        self.g1.write(0x00, (self.min_duty & 0x3FF) | ((sel & 7) << 12) | ((calib & 1) << 16))

    def now_us(self):
        return self.g3.read(0x08)

    def snap(self):
        """(seq, ts_us, yaw_deg)，seqlock 保证三项来自同一个样本"""
        while True:
            a = self.g2.read(0x00)
            ts = self.g1.read(0x08)
            yaw = _s32(self.g2.read(0x08))
            b = self.g2.read(0x00)
            if (a >> 16) == (b >> 16):
                return a >> 16, ts, yaw / 1000.0

    def recalibrate(self):
        self._push(0, 1)
        time.sleep(0.01)
        self._push(0, 0)
        t0 = time.time()
        while time.time() - t0 < 3.0:
            if (self.g2.read(0x00) >> 3) & 1:
                return True
            time.sleep(0.02)
        return False

    # ------------------------------------------------ 闭环转向 / 直行
    def burst(self, s, ms):
        """s=+1 左转(逆时针), -1 右转; 满功率脉冲 ms 毫秒, 然后刹车并等车停稳"""
        self.set(s * 1000, -s * 1000)
        if self.t_first_cmd is None:
            self.t_first_cmd = time.perf_counter()
        time.sleep(ms / 1000.0)
        self.stop(0.08)
        time.sleep(0.25)

    def pulse_turn(self, delta_deg, tol=3.0, maxn=25, tmax=8.0):
        """相对当前朝向转 delta_deg(左正右负)。返回 (最终误差deg, 脉冲数)"""
        target = self.snap()[2] + delta_deg
        t0 = time.time()
        boost = 1.0
        n = 0
        for _ in range(maxn):
            y = self.snap()[2]
            err = target - y
            if abs(err) < tol or time.time() - t0 > tmax:
                break
            s = 1 if err > 0 else -1
            ms = min(300.0, max(50.0, abs(err) * self.k_ms_per_deg * 0.8) * boost)
            self.burst(s, ms)
            n += 1
            moved = (self.snap()[2] - y) * s
            boost = min(2.0, boost * 1.5) if moved < 1.0 else 1.0
        time.sleep(0.3)
        return target - self.snap()[2], n

    def drive_hold(self, base, heading, kp=15.0, cmax=250):
        """前进并用 yaw 保持航向 heading(deg)"""
        yaw = self.snap()[2]
        c = max(-cmax, min(cmax, kp * (heading - yaw)))
        self.set(base + c, base - c)      # A=右轮: 偏左(yaw>heading)时 c<0, 右轮减速、左轮加速 -> 右修正


class Vision:
    """摄像头(MJPG 原始帧) + 与 PC 上 server.py 的 TCP 协议(!II 帧头, 回复 !IIfff)"""

    def __init__(self, pc_ip, port=9001, cam=0, timeout=1.0):
        import cv2
        global _ACTIVE_VIS
        if _ACTIVE_VIS is not None:          # 重复运行本 cell: 先释放上一个实例占用的摄像头和连接
            try:
                _ACTIVE_VIS.close()
            except Exception:
                pass
        _ACTIVE_VIS = self
        self.cap = cv2.VideoCapture(cam)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
        for _ in range(30):
            self.cap.read()
        self.s = socket.socket()
        self.s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.s.settimeout(timeout)
        self.s.connect((pc_ip, port))

    def flush(self, n=5):
        for _ in range(n):
            self.cap.read()

    def grab(self):
        ok, f = self.cap.read()
        data = f.tobytes() if ok else b""
        return data if data[:2] == b"\xff\xd8" else None

    def _recvn(self, n):
        buf = b""
        while len(buf) < n:
            c = self.s.recv(n - len(buf))
            if not c:
                raise ConnectionError
            buf += c
        return buf

    def ask(self, fid, data):
        self.s.sendall(struct.pack("!II", fid, len(data)) + data)
        return struct.unpack("!IIfffff", self._recvn(28))   # fid, cnt, cx, area, infer_ms, ybot, cls

    def close(self):
        try:
            self.s.close()
        finally:
            self.cap.release()


def run_avoid(car, vis, seconds=20, base=800, turn_deg=60, area_thr=0.10, bottle_area_thr=0.06, y_thr=None, kp=15.0,
              log="avoid_log.csv"):
    """避障主循环: 无障碍 -> 用 PL yaw 保持航向直行; 有障碍(最大框面积占比>=area_thr)
    -> 向远离障碍的一侧转 turn_deg (障碍判据: 框面积占比>=area_thr, 或 框底边位置ybot>=y_thr), 转完把当前朝向作为新航向继续直行。"""
    rows, timeouts, consec = [], 0, 0
    heading = car.snap()[2]
    t_end = time.time() + seconds
    fid = 0
    try:
        while time.time() < t_end:
            data = vis.grab()
            if data is None:
                continue
            t_cap = time.perf_counter()
            ts_cap = car.now_us()                  # 帧到手瞬间的 PL 微秒时间戳
            yaw_cap = car.snap()[2]                # 同一时刻 PL 的 yaw
            fid += 1
            try:
                f, cnt, cx, area, inf, ybot, cls = vis.ask(fid, data)
            except socket.timeout:
                timeouts += 1
                car.stop()                         # 链路卡住 -> 先停车
                continue
            if cnt == BAD:
                continue
            car.t_first_cmd = None
            turn_err = float("nan")
            if cnt > 0 and area >= (bottle_area_thr if int(cls) in SMALL_CLS else area_thr):   # 水瓶(小)阈值0.06, 人/椅子0.10; 面积随距离平方反比变化, 比 ybot 稳定
                delta = -turn_deg if cx < 0.5 else turn_deg     # 障碍在左 -> 右转(负)
                action = "turn_right" if delta < 0 else "turn_left"
                consec += 1
                if consec >= 4:
                    print("连续转向 4 次仍有障碍，停车退出")
                    break
                turn_err, _ = car.pulse_turn(delta)
                heading = car.snap()[2]
                vis.flush(5)
                t_act = car.t_first_cmd or time.perf_counter()
            else:
                consec = 0
                action = "forward"
                car.drive_hold(base, heading, kp)
                t_act = time.perf_counter()
            rows.append((fid, ts_cap, round(yaw_cap, 3), cnt, round(cx, 3), round(area, 3),
                         round(inf, 2), action, round((t_act - t_cap) * 1000, 2), round(turn_err, 2),
                         round(ybot, 3), int(cls)))
    finally:
        car.stop()
        with open(log, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["frame", "pl_ts_us", "yaw_deg", "count", "cx", "area", "infer_ms",
                        "action", "latency_ms", "turn_err_deg", "ybot", "cls"])
            w.writerows(rows)
    lat = np.array([r[8] for r in rows if r[7] == "forward"])
    if len(lat):
        print("画面到手 -> 电机指令写出(直行帧) ms: P50=%.1f P95=%.1f P99=%.1f max=%.1f"
              % (*np.percentile(lat, [50, 95, 99]), lat.max()))
    from collections import Counter
    print("帧数 %d  动作统计 %s  链路超时 %d" % (len(rows), dict(Counter(r[7] for r in rows)), timeouts))
    te = [r[9] for r in rows if r[7] != "forward"]
    if te:
        print("转向最终误差 deg: 平均绝对 %.2f  最大绝对 %.2f" % (np.mean(np.abs(te)), np.max(np.abs(te))))
    return rows


def probe(vis, n=20):
    """标定: 把障碍物放在你希望车开始避让的距离, 运行 probe(vis); 输出该距离下的 ybot/area, 据此设 y_thr"""
    ys, ar, cl = [], [], []
    fid = 100000
    for _ in range(n):
        data = vis.grab()
        if data is None:
            continue
        fid += 1
        f, cnt, cx, area, inf, ybot, cls = vis.ask(fid, data)
        if cnt not in (0, BAD):
            ys.append(ybot); ar.append(area); cl.append(int(cls))
    if not ys:
        print("没有检测到目标(检查物体是否在画面里、是否是 person/bottle/chair)")
        return None
    print("检测到 %d/%d 帧; 类别 %s; ybot 中位数 %.3f (范围 %.3f~%.3f); area 中位数 %.3f"
          % (len(ys), n, sorted(set(cl)), np.median(ys), min(ys), max(ys), np.median(ar)))
    return float(np.median(ys))


def run_trials(car, vis, label, n=10, seconds=7, expect_cls=39, **kw):
    """正式避障统计: 每次试验手动摆好障碍物 -> 回车 -> 车自动运行 -> 你输入结果。
    结果追加写入 trials.csv; 每次试验的逐帧日志存为 trial_<label>_<序号>.csv (原始日志要留着给评委)。
    结果编号: 1=成功避开(转向且没碰到) 2=擦碰/碰到 3=没有触发 4=误触发/其他(本次不计入)"""
    import os
    new = not os.path.exists("trials.csv")
    for i in range(1, n + 1):
        input("[%s %d/%d] 摆好障碍物、挡好桌沿、你离开画面, 回车开始: " % (label, i, n))
        rows = run_avoid(car, vis, seconds=seconds, log="trial_%s_%d.csv" % (label, i), **kw)
        trig = [r for r in rows if str(r[7]).startswith("turn")]
        lat = sorted(r[8] for r in rows[3:] if r[7] == "forward")
        p50 = lat[len(lat) // 2] if lat else float("nan")
        p99 = lat[min(len(lat) - 1, int(len(lat) * 0.99))] if lat else float("nan")
        t_area = trig[0][5] if trig else float("nan")
        t_cls = trig[0][11] if trig else -1
        t_err = trig[0][9] if trig else float("nan")
        print("触发类别:", t_cls, " 面积:", t_area, "  (期望类别 %s)" % expect_cls)
        if trig and int(t_cls) != int(expect_cls):
            print("⚠ 触发转向的不是目标物体(可能是背景里的椅子/盆栽等), 这次建议输入 4 作废")
        res = input("结果? 1=成功避开 2=擦碰 3=没触发 4=误触发/作废: ").strip()
        with open("trials.csv", "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["label", "trial", "result", "frames", "trigger_area", "trigger_cls", "turn_err_deg", "lat_p50_ms", "lat_p99_ms"])
                new = False
            w.writerow([label, i, res, len(rows), t_area, t_cls, t_err, round(p50, 2), round(p99, 2)])
        print("已记录 ->", label, i, "结果", res)
    print("完成。trials.csv 与 trial_%s_*.csv 请下载保存。" % label)
