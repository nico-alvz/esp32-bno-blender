"""ESP32 Tracker: install this package directly from the release ZIP."""
bl_info = {
    "name": "ESP32 IMU Tracker",
    "author": "nico-alvz",
    "version": (1, 6, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar (N) > ESP32 Tab",
    "description": "Controla objetos 3D en tiempo real con ESP32 + BNO08x/055",
    "category": "3D View",
}

import sys
from pathlib import Path

# pyserial 3.5 is bundled unchanged under its original license.
_vendor = str(Path(__file__).resolve().parent / "vendor")
sys.path.insert(0, _vendor)
try:
    import serial
    import serial.tools.list_ports
finally:
    sys.path.remove(_vendor)

from .tracker import register, unregister
