"""Off-board self test:  python3 selftest.py"""
import threading, time
from safe_overlay import load_overlay_once, replace_active


class FakeOverlay:
    calls = []
    def __init__(self, bit, download=True):
        FakeOverlay.calls.append((bit, download))


class App:
    def __init__(self):
        self.stop = threading.Event(); self.closed = False
        self.th = threading.Thread(target=lambda: self.stop.wait(), daemon=True); self.th.start()
    def close(self):
        self.closed = True; self.stop.set()


FakeOverlay.calls.clear()
load_overlay_once("a.bit", factory=FakeOverlay, loaded_name=None)          # first load -> download
load_overlay_once("a.bit", factory=FakeOverlay, loaded_name="a.bit")       # same bitstream -> no download
load_overlay_once("b.bit", factory=FakeOverlay, loaded_name="a.bit")       # different -> download
dl = [c[1] if len(c) > 1 else True for c in FakeOverlay.calls]
assert dl == [True, False, True], dl
a1 = replace_active("app", App()); a2 = replace_active("app", App())
time.sleep(0.05)
assert a1.closed and not a2.closed and not a1.th.is_alive()
a2.close()
print("safe_overlay selftest PASS")
