"""seqlock.py -- consistent multi-register snapshot from a free-running PL block (no handshake needed).

PL side contract (see snippet.v): all result registers AND a sequence counter are updated in the SAME clock cycle.
PS side: read seq, read the data registers, read seq again; accept only if both seq values are equal.

    from seqlock import read_snapshot
    seq, (yaw, ts) = read_snapshot(
        seq_fn=lambda: mmio.read(0x00) >> 16,                      # sequence number lives in the status word
        data_fns=[lambda: mmio.read(0x08), lambda: other.read(0x08)])
"""


def read_snapshot(seq_fn, data_fns, retries=16):
    """seq_fn() -> int sequence number; data_fns -> list of zero-arg callables returning the values."""
    for _ in range(retries):
        a = seq_fn()
        vals = [f() for f in data_fns]
        b = seq_fn()
        if a == b:
            return a, vals
    raise RuntimeError("seqlock: PL kept updating during %d reads" % retries)
