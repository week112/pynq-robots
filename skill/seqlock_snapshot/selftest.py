import threading, time
from seqlock import read_snapshot

# a fake PL block that updates {seq, a, b} atomically every 50 us, read by a slow reader that can be interrupted
state = dict(seq=0, a=0, b=0); lock = threading.Lock(); stop = False
def pl():
    n = 0
    while not stop:
        n += 1
        with lock:
            state.update(seq=n, a=n, b=2 * n)
        time.sleep(0.00005)
t = threading.Thread(target=pl, daemon=True); t.start()

torn = 0; ok = 0
def slow(key):
    def f():
        time.sleep(0.0002)                      # reader preempted between register reads
        with lock: return state[key]
    return f
def seq():
    with lock: return state["seq"]
for _ in range(300):
    try:
        s, (a, b) = read_snapshot(seq, [slow("a"), slow("b")], retries=200)
    except RuntimeError:
        continue
    ok += 1
    torn += (b != 2 * a)                           # a & b come from the same commit only if b == 2a
naive_torn = 0
for _ in range(300):                                # same slow reads WITHOUT the seq check
    a = slow("a")(); b = slow("b")()
    naive_torn += (b != 2 * a)
stop = True
# NOTE: this fake updates faster than the reader can read, so most snapshots are rejected; accepted ones must be consistent
print(f"naive reads torn: {naive_torn}/300 ; seqlock accepted {ok}, torn among accepted {torn}")
assert torn == 0
print("seqlock selftest PASS")
