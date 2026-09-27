# Copyright © 2026 Roger B. Leuthner. All rights reserved.  This software is provided for informational and educational purposes. Use of this software does not imply endorsement by the author of any particular use or application. The author assumes no responsibility or liability for any damages or consequences arising from its use.

import _thread
import time

running = True

def burn_cpu():
    x = 1
    while running:
        # Integer-heavy workload
        x = (x * 1664525 + 1013904223) & 0xFFFFFFFF
        x ^= (x >> 13)
        x = (x * 0x5DEECE66D + 0xB) & 0xFFFFFFFF

def core1():
    burn_cpu()

# Start workload on the second core
_thread.start_new_thread(core1, ())

# Burn CPU on the main core
try:
    _thread.start_new_thread(burn_cpu, ())    
    _thread.start_new_thread(burn_cpu, ())    
    _thread.start_new_thread(burn_cpu, ())    
    _thread.start_new_thread(burn_cpu, ())    
except KeyboardInterrupt:
    running = False
    print("Stopped.")
