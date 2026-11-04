# server_v2.py : PC 端 YOLO 服务 (替换原 server.py)。协议: 收 !II(帧号,长度)+JPEG; 回 !IIfffff
#   fid, cnt, cx, area, infer_ms, ybot, cls
#   cnt   = 检测到的目标数(仅统计 CLASSES 里的类别)
#   cx    = 最近目标(底边最靠下的框)的中心 x / 图像宽, 0~1
#   area  = 该框面积 / 图像面积
#   ybot  = 该框底边 y / 图像高 (越大 = 离车越近)
#   cls   = 该框的类别编号 (COCO: 0=person 39=bottle 56=chair)
import socket, struct, time, cv2, numpy as np
from ultralytics import YOLO

# 答辩现场障碍物不确定 -> 放宽到 COCO 里常见的可移动物体; 故意不含沙发/餐桌/电视/床等大件背景
SMALL = [24, 25, 26, 28, 32, 39, 40, 41, 67, 73, 75, 77]   # 背包 伞 手提包 行李箱 球 水瓶 酒杯 杯子 手机 书 花瓶 玩具熊 (小物体, 触发面积阈值 0.06)
LARGE = [0, 1, 2, 3, 13, 15, 16, 56, 58]                    # 人 自行车 汽车 摩托 长椅 猫 狗 椅子 盆栽 (触发面积阈值 0.10)
CLASSES = SMALL + LARGE
CONF = 0.15

model = YOLO("yolov8n.pt")
model(np.zeros((480, 640, 3), np.uint8), verbose=False)   # 预热

srv = socket.socket()
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("0.0.0.0", 9001)); srv.listen(1)
BAD = 0xFFFFFFFF
bad = 0
nframe = 0

while True:
    print("等待连接...")
    conn, addr = srv.accept(); print("已连接", addr)
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def recvn(n):
        buf = b""
        while len(buf) < n:
            c = conn.recv(n - len(buf))
            if not c: raise ConnectionError
            buf += c
        return buf

    try:
        while True:
            fid, ln = struct.unpack("!II", recvn(8))
            jpg = recvn(ln)
            t0 = time.perf_counter()
            img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                bad += 1
                print(f"第 {fid} 帧解码失败(累计 {bad}),长度 {ln}")
                conn.sendall(struct.pack("!IIfffff", fid, BAD, -1.0, 0.0, 0.0, 0.0, -1.0))
                continue
            res = model(img, verbose=False, classes=CLASSES, conf=CONF)[0]
            inf_ms = (time.perf_counter() - t0) * 1000
            boxes = res.boxes
            H, W = img.shape[:2]
            if len(boxes) == 0:
                cnt, cx, area, ybot, cls = 0, -1.0, 0.0, 0.0, -1.0
            else:
                xyxy = boxes.xyxy.cpu().numpy()
                clss = boxes.cls.cpu().numpy()
                # 选"威胁最大"的框: 面积 / 该类别触发阈值 最大者 (水瓶阈值0.06, 人/椅子0.10; 要与 car_pl.py 里一致)
                areas = (xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1]) / (W * H)
                score = areas / np.where(np.isin(clss, SMALL), 0.06, 0.10)
                k = int(np.argmax(score))
                b = xyxy[k]
                cnt = len(boxes)
                cx = float((b[0] + b[2]) / 2 / W)
                area = float((b[2] - b[0]) * (b[3] - b[1]) / (W * H))
                ybot = float(b[3] / H)
                cls = float(clss[k])
            conn.sendall(struct.pack("!IIfffff", fid, cnt, cx, area, inf_ms, ybot, cls))
            nframe += 1
            if nframe % 5 == 0:   # 每5帧覆盖保存一张带框图 latest.jpg, 并打印检测明细
                cv2.imwrite("latest.jpg", res.plot())
                names = model.names
                print("检测:", [(names.get(int(c), int(c)), round(float(p), 2), round(float(y) / H, 2))
                              for c, p, y in zip(boxes.cls, boxes.conf, boxes.xyxy[:, 3])])
    except ConnectionError:
        print("连接已关闭")
        conn.close()
