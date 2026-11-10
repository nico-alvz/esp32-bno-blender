"""Run: blender --background --factory-startup --python test/test_tracker.py"""
import importlib.util
import math
import time
from pathlib import Path
from types import SimpleNamespace
import bpy
from mathutils import Quaternion, Vector

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from esp32_tracker import tracker as t
t.register()
s = bpy.context.scene.esp32_tracker
s.target_object = bpy.data.objects['Cube']
class Port:
    is_open = True
    data = b''
    @property
    def in_waiting(self): return len(self.data)
    def read(self, count):
        result, self.data = self.data[:count], self.data[count:]
        return result
    def close(self): self.is_open = False
port = Port()
t._serial_conn, t._timer_active = port, True

def feed(q):
    port.data = ('Q,' + ','.join(str(v) for v in q) + '\n').encode()
    t.update_tracker_timer()

def near(a, b):
    assert abs(a.normalized().dot(b.normalized())) > 0.99999, (a, b)
identity = Quaternion((1, 0, 0, 0))
q0 = Quaternion(Vector((1,2,3)).normalized(), 1.2)
for mount in ('FLAT', 'PHONE'):
    s.mount = mount
    t._reference = None
    feed(q0)
    near(s.target_object.rotation_quaternion, identity)
    delta = Quaternion((1,0,0), 0.5)
    feed(q0 @ delta)
    m = t.mount_quaternion(s)
    near(s.target_object.rotation_quaternion, m @ delta @ m.inverted())
    for _ in range(5):
        assert bpy.ops.esp32.tare_tracker() == {'FINISHED'}
        near(s.target_object.rotation_quaternion, identity)
        feed(q0 @ delta)
        near(s.target_object.rotation_quaternion, identity)
    feed(-(q0 @ delta))
    near(s.target_object.rotation_quaternion, identity)

s.mount = 'CUSTOM'
count = 0
for f in ('X','-X','Y','-Y','Z','-Z'):
    for u in ('X','-X','Y','-Y','Z','-Z'):
        s.sensor_forward, s.sensor_up = f, u
        try:
            m = t.mount_quaternion(s)
        except ValueError:
            assert f[-1] == u[-1]
            continue
        assert f[-1] != u[-1]
        axes = {'X':Vector((1,0,0)), 'Y':Vector((0,1,0)), 'Z':Vector((0,0,1))}
        fv = axes[f[-1]] * (-1 if f.startswith('-') else 1)
        uv = axes[u[-1]] * (-1 if u.startswith('-') else 1)
        assert (m @ fv - Vector((0,1,0))).length < 1e-5
        assert (m @ uv - Vector((0,0,1))).length < 1e-5
        count += 1
assert count == 24
for packet in ('Q,nan,0,0,0','Q,inf,0,0,0','Q,0,0,0,0','Q,x,0,0,0','boot','Q,1,0,0,0,1'):
    assert t.parse_packet(packet) is None
near(t.parse_packet('Q,0.99,0,0,0'), identity)
# Vertical phone: physical yaw must stay yaw for all in-plane board mountings.
s.mount = 'PHONE'
for front in ('-Z', 'Z'):
    s.phone_forward = front
    for spin in (0, math.pi/2, math.pi, -math.pi/2, 0.37):
        base = Quaternion((0,0,1), 0.6) @ Quaternion((1,0,0), math.pi/2) @ Quaternion((0,0,1), spin)
        t._reference = None
        feed(base)
        for angle in (0.3, -0.5, 1.7):
            feed(Quaternion((0,0,1), angle) @ base)
            near(s.target_object.rotation_quaternion, Quaternion((0,0,1), angle))
        assert bpy.ops.esp32.tare_tracker() == {'FINISHED'}
        near(s.target_object.rotation_quaternion, identity)
# Regression for measured neutral pose: up was -X, not +Y.
base = Quaternion((0.5040108,-0.4812103,0.4512097,0.5575120))
t._reference = None
feed(base)
feed(Quaternion((0,0,1), 0.4) @ base)
near(s.target_object.rotation_quaternion, Quaternion((0,0,1), 0.4))
try:
    t.mount_quaternion(s, identity)
    raise AssertionError('Flat sensor accepted as vertical')
except ValueError:
    pass
# Independent expected XYZ control angles, all inversion combinations.
from mathutils import Euler
from itertools import product
for signs in product((False, True), repeat=3):
    s.invert_x, s.invert_y, s.invert_z = signs
    t._control_euler = None
    q = Euler((0.35, -0.4, 0.7), 'XYZ').to_quaternion()
    expected = Euler(tuple(-v if inv else v for v, inv in zip((0.35,-0.4,0.7), signs)), 'XYZ').to_quaternion()
    near(t.invert_controls(q, s), expected)
    near(t.invert_controls(-q, s), expected)
    near(t.invert_controls(identity, s), identity)
s.mount = 'FLAT'
s.invert_x, s.invert_y, s.invert_z = True, False, True
t._reference = None
feed(q0)
feed(q0 @ Quaternion((1,0,0), 0.3))
near(s.target_object.rotation_quaternion, Quaternion((1,0,0), -0.3))
assert bpy.ops.esp32.tare_tracker() == {'FINISHED'}
feed(q0 @ Quaternion((1,0,0), 0.3))
near(s.target_object.rotation_quaternion, identity)
# Fragmented USB data, multiple packets and malformed packets in one read.
valid_before, bad_before = t._valid_packets, t._invalid_packets
port.data = b'Q,1,0,'
t.update_tracker_timer()
assert t._valid_packets == valid_before
port.data = b'0,0\nQ,nan,0,0,0\nboot message\nQ,1,0,0,0\n'
t.update_tracker_timer()
assert t._valid_packets == valid_before + 2
assert t._invalid_packets == bad_before + 1
assert t._last_packet == 'Q,1,0,0,0'
assert t._last_device_message == 'boot message'
t._last_sample_time = time.monotonic() - 2
assert bpy.ops.esp32.tare_tracker() == {'CANCELLED'}
t.unregister()
print('PASS: inversion combinations, telemetry and fragmented input; 24 mount orientations, repeated tare, arbitrary neutral, sign equivalence, invalid packets, stale tare, lifecycle')
