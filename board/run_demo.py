"""run_demo.py -- run on the PYNQ-Z2 (not in the notebook):   sudo python3 run_demo.py [seconds]
Same calls as the notebook flow.  Start the detection service on the PC first (src/ps/server_v2.py).
STATUS: thin wrapper around car_pl.py; the notebook flow is the one used for all reported measurements.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "ps"))
from car_pl import Car, Vision, run_avoid

PC_IP = "192.168.2.1"
secs = int(sys.argv[1]) if len(sys.argv) > 1 else 7
car = Car(os.path.join(os.path.dirname(os.path.abspath(__file__)), "overlay", "pipeline.bit"))
vis = Vision(PC_IP)
try:
    run_avoid(car, vis, seconds=secs)
finally:
    vis.close(); car.close()
