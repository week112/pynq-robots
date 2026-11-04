"""safe_overlay.py -- load a PYNQ Overlay once, and never re-program the PL under a running AXI user.

Why: in a Jupyter notebook people re-run the cell that creates `Overlay("x.bit")`.  If an older object still has
a thread (heartbeat / polling) reading or writing AXI registers, re-downloading the bitstream makes those bus
transactions hang and the whole Zynq PS freezes (board stops answering ping; only a power cycle helps).

Usage (board):
    from safe_overlay import load_overlay_once, replace_active
    ol  = load_overlay_once("design.bit")          # no download if this bitstream is already loaded
    app = replace_active("app", MyApp(ol))         # closes the previous "app" instance first (its .close())

Works off-board too: pass your own `factory`/`loaded_name` (used by selftest.py).
"""
import os

_ACTIVE = {}


def _current_bitfile():
    try:
        from pynq import PL
        return PL.bitfile_name
    except Exception:
        return None


def load_overlay_once(bit, factory=None, loaded_name=None):
    """Return an Overlay for `bit`.  If the same bitstream is already in the PL, build the Overlay with
    download=False so the PL is NOT reconfigured."""
    if factory is None:
        from pynq import Overlay
        factory = Overlay
    cur = loaded_name if loaded_name is not None else _current_bitfile()
    if cur and os.path.abspath(bit) == os.path.abspath(cur):
        return factory(bit, download=False)
    return factory(bit)


def replace_active(key, new_obj, join_timeout=1.0):
    """Register `new_obj` as the single active object under `key`; close the previous one first.
    Objects should expose close() (stop threads, release camera/GPIO); an optional `.th` thread is joined."""
    old = _ACTIVE.get(key)
    if old is not None:
        for fn in ("close",):
            try:
                getattr(old, fn)()
            except Exception:
                pass
        th = getattr(old, "th", None)
        if th is not None:
            try:
                th.join(join_timeout)
            except Exception:
                pass
    _ACTIVE[key] = new_obj
    return new_obj
