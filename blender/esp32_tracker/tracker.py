"""
ESP32 + BNO08x / BNO055 Real-Time 3D Tracker para Blender
Soporta USB Serial y Bluetooth SPP con montaje configurable.
"""

import bpy
import serial
import serial.tools.list_ports
import mathutils
import time
import sys
import math
from collections import deque

bl_info = {
    "name": "ESP32 IMU Tracker",
    "author": "nico-alvz",
    "version": (1, 5, 2),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar (N) > ESP32 Tab",
    "description": "Controla objetos 3D en tiempo real con ESP32 + BNO08x/055",
    "category": "3D View",
}

_serial_conn = None
_timer_active = False
_rx_buffer = ""
_last_sensor = None
_last_sample_time = 0.0
_reference = None
_config = None
_control_euler = None
_output_quat = None
_last_packet = ""
_last_device_message = ""
_packet_times = deque(maxlen=2000)
_valid_packets = 0
_invalid_packets = 0
_connected_at = 0.0

def invert_controls(q, settings):
    """Map relative rotation axes without Euler conversion or history.

    A signed permutation of the quaternion vector is an orthogonal mapping
    of its axis-angle vector. It preserves the rotation angle, identity and
    Q/-Q equivalence. Odd permutations are a control convention (not a
    change of right-handed coordinate basis).
    """
    source = (q.x, q.y, q.z)
    signs = (settings.invert_x, settings.invert_y, settings.invert_z)
    vector = [source['XYZ'.index(axis)] * (-1 if inverted else 1)
              for axis, inverted in zip(settings.axis_mapping, signs)]
    result = mathutils.Quaternion((q.w, *vector))
    result.normalize()
    return result

def target_for(settings):
    return settings.target_object or bpy.data.objects.get("Cube") or bpy.context.view_layer.objects.active

def mount_quaternion(settings, reference=None):
    axes = {"X": (1,0,0), "Y": (0,1,0), "Z": (0,0,1),
            "-X": (-1,0,0), "-Y": (0,-1,0), "-Z": (0,0,-1)}
    if settings.mount == 'PHONE':
        reference = reference if reference is not None else _reference
        if reference is None:
            raise ValueError("Coloca el sensor vertical y centra")
        # Gravity-aligned up, expressed in sensor coordinates at neutral.
        u = reference.inverted() @ mathutils.Vector((0, 0, 1))
        u.normalize()
        f = mathutils.Vector(axes[settings.phone_forward])
        if abs(f.dot(u)) > 0.85:
            raise ValueError("Coloca el BNO vertical y vuelve a centrar")
        f = (f - u * f.dot(u)).normalized()
        return mathutils.Matrix((f.cross(u), f, u)).to_quaternion()
    forward, up = "Y", "Z"
    if settings.mount == 'CUSTOM':
        forward, up = settings.sensor_forward, settings.sensor_up
    f, u = mathutils.Vector(axes[forward]), mathutils.Vector(axes[up])
    if abs(f.dot(u)) > 0.5:
        raise ValueError("Frente y arriba deben ser ejes perpendiculares")
    return mathutils.Matrix((f.cross(u), f, u)).to_quaternion()

def parse_packet(line):
    parts = line.strip().split(',')
    if len(parts) != 5 or parts[0] != 'Q':
        return None
    try:
        values = tuple(float(v) for v in parts[1:])
    except ValueError:
        return None
    if not all(math.isfinite(v) for v in values):
        return None
    norm = sum(v*v for v in values)
    if not 0.25 <= norm <= 2.25:
        return None
    q = mathutils.Quaternion(values)
    q.normalize()
    return q

def apply_mount_defaults(settings, context):
    # Apply once when selecting a preset; manual inversion remains editable.
    settings.invert_x = True
    if settings.mount == 'FLAT':
        settings.axis_mapping = 'XYZ'
    elif settings.mount == 'PHONE':
        settings.axis_mapping = 'YXZ'

class ESP32TrackerSettings(bpy.types.PropertyGroup):
    connection_type: bpy.props.EnumProperty(
        name="Tipo de Conexión",
        items=[
            ("USB", "Cable USB (automático)", "Conexión por cable"),
            ("BT", "Bluetooth (/dev/rfcomm0)", "Conexión inalámbrica Bluetooth SPP"),
            ("CUSTOM", "Personalizado", "Ingresar puerto manual")
        ],
        default="USB"
    )
    custom_port: bpy.props.StringProperty(
        name="Puerto Manual",
        default="/dev/ttyUSB0"
    )
    target_object: bpy.props.PointerProperty(
        name="Objeto 3D",
        type=bpy.types.Object
    )
    is_running: bpy.props.BoolProperty(
        name="Activo",
        default=False
    )
    last_reading: bpy.props.StringProperty(
        name="Lectura",
        default="Sin datos"
    )
    axis_mapping: bpy.props.EnumProperty(
        name="Asignación de ejes",
        description="Orden de los controles de entrada que se envían a X, Y y Z del objeto",
        items=[(order, order, 'Salida X ← ' + order[0] + ', Y ← ' + order[1] + ', Z ← ' + order[2])
               for order in ('XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX')],
        default='XYZ')
    invert_x: bpy.props.BoolProperty(name="Invertir X · Cabeceo", default=True)
    invert_y: bpy.props.BoolProperty(name="Invertir Y · Inclinación lateral", default=False)
    invert_z: bpy.props.BoolProperty(name="Invertir Z · Giro", default=False)
    show_live: bpy.props.BoolProperty(name="Datos en vivo", default=True)
    mount: bpy.props.EnumProperty(name="Montaje", items=[
        ('FLAT', 'Horizontal', 'Frente del dispositivo: +Y del BNO; arriba: +Z'),
        ('PHONE', 'Vertical sobre celular', 'Detecta arriba al centrar; selecciona la cara del BNO hacia afuera'),
        ('CUSTOM', 'Personalizado', 'Seleccionar los ejes físicos del sensor')], default='FLAT', update=apply_mount_defaults)
    phone_forward: bpy.props.EnumProperty(name="Cara hacia afuera", items=[
        ('-Z', '-Z del BNO', 'Normal negativa del sensor hacia el frente del celular'),
        ('Z', '+Z del BNO', 'Normal positiva del sensor hacia el frente del celular')], default='-Z')
    sensor_forward: bpy.props.EnumProperty(name="Frente del BNO", items=[(a,a,a) for a in ('X','-X','Y','-Y','Z','-Z')], default='-Z')
    sensor_up: bpy.props.EnumProperty(name="Arriba del BNO", items=[(a,a,a) for a in ('X','-X','Y','-Y','Z','-Z')], default='Y')

def get_active_port(settings):
    if settings.connection_type == "USB":
        ports = list(serial.tools.list_ports.comports())
        usb_ports = [p.device for p in ports if p.vid is not None]
        return usb_ports[0] if usb_ports else ("COM3" if sys.platform == "win32" else "/dev/ttyUSB0")
    elif settings.connection_type == "BT":
        return "/dev/rfcomm0"
    else:
        return settings.custom_port.strip()

def update_tracker_timer():
    global _last_sensor, _last_sample_time, _reference, _rx_buffer, _config
    global _control_euler, _output_quat, _last_packet, _last_device_message, _valid_packets, _invalid_packets
    scene = bpy.context.scene
    settings = scene.esp32_tracker
    if not _timer_active or not _serial_conn or not _serial_conn.is_open:
        settings.is_running = False
        return None
    try:
        chunk = _serial_conn.read(min(_serial_conn.in_waiting, 65536)).decode('ascii', errors='ignore')
        _rx_buffer += chunk
        lines = _rx_buffer.split('\n')
        _rx_buffer = lines.pop()[-256:]
        newest = None
        now = time.monotonic()
        for line in lines:
            q = parse_packet(line)
            if q is None:
                if line.startswith('Q,'):
                    _invalid_packets += 1
                elif line.strip():
                    _last_device_message = line.strip()[:160]
                continue
            _valid_packets += 1
            _packet_times.append(now)
            _last_packet = line.strip()[:160]
            newest = q
        while _packet_times and now - _packet_times[0] > 1.0:
            _packet_times.popleft()
        if newest is not None:
            q = newest
            _last_sensor = q
            _last_sample_time = time.monotonic()
            config = (settings.mount, settings.phone_forward, settings.sensor_forward, settings.sensor_up,
                      settings.target_object.as_pointer() if settings.target_object else 0)
            new_reference = _reference is None or config != _config
            mount = mount_quaternion(settings, q if new_reference else _reference)
            if new_reference:
                _reference = q.copy()
                _config = config
                _control_euler = None
            result = mount @ (_reference.inverted() @ q) @ mount.inverted()
            result = invert_controls(result, settings)
            _output_quat = result.copy()
            target = target_for(settings)
            if target:
                target.rotation_mode = 'QUATERNION'
                target.rotation_quaternion = result
            settings.last_reading = "Recibiendo orientación"
        if time.monotonic() - _last_sample_time > 1.0:
            settings.last_reading = "Sin datos recientes del sensor"
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except (serial.SerialException, OSError) as exc:
        bpy.ops.esp32.stop_tracker()
        settings.last_reading = f"Conexión perdida: {exc}"
        return None
    except ValueError as exc:
        settings.last_reading = str(exc)
    return 0.01

class ESP32_OT_StartTracker(bpy.types.Operator):
    bl_idname = "esp32.start_tracker"
    bl_label = "Conectar / Iniciar"

    def execute(self, context):
        global _serial_conn, _timer_active, _rx_buffer, _last_sensor, _reference, _config, _last_sample_time
        global _control_euler, _output_quat, _last_packet, _last_device_message
        global _valid_packets, _invalid_packets, _connected_at
        settings = context.scene.esp32_tracker

        if _timer_active:
            return {'FINISHED'}

        port = get_active_port(settings)

        try:
            _rx_buffer = ""
            _last_sensor = _reference = _config = None
            _last_sample_time = 0.0
            _connected_at = time.monotonic()
            _control_euler = _output_quat = None
            _last_packet = _last_device_message = ""
            _packet_times.clear()
            _valid_packets = _invalid_packets = 0
            _serial_conn = serial.Serial()
            _serial_conn.port = port
            _serial_conn.baudrate = 115200
            _serial_conn.timeout = 0
            _serial_conn.open()

            # Si es por cable USB, dar pulso RTS para reiniciar limpiamente
            if settings.connection_type == "USB" or "usb" in port.lower() or "acm" in port.lower():
                _serial_conn.setDTR(False)
                _serial_conn.setRTS(True)
                time.sleep(0.1)
                _serial_conn.setRTS(False)
                time.sleep(0.1)

            _serial_conn.reset_input_buffer()
            _timer_active = True
            settings.is_running = True
            settings.last_reading = f"Conectado a {port}"

            bpy.app.timers.register(update_tracker_timer)
            self.report({'INFO'}, f"Conectado a {port}")
            print(f"[ESP32 Tracker] Conectado exitosamente a {port}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error abriendo {port}: {e}")
            return {'CANCELLED'}

class ESP32_OT_StopTracker(bpy.types.Operator):
    bl_idname = "esp32.stop_tracker"
    bl_label = "Desconectar / Detener"

    def execute(self, context):
        global _serial_conn, _timer_active
        _timer_active = False
        if bpy.app.timers.is_registered(update_tracker_timer):
            bpy.app.timers.unregister(update_tracker_timer)
        settings = context.scene.esp32_tracker
        settings.is_running = False
        settings.last_reading = "Detenido"

        if _serial_conn and _serial_conn.is_open:
            _serial_conn.close()
        _serial_conn = None

        self.report({'INFO'}, "Tracker detenido.")
        return {'FINISHED'}

class ESP32_OT_TareTracker(bpy.types.Operator):
    bl_idname = "esp32.tare_tracker"
    bl_label = "Calibrar Cero (Tare)"

    def execute(self, context):
        global _reference, _control_euler, _output_quat
        settings = context.scene.esp32_tracker
        if _last_sensor is None or time.monotonic() - _last_sample_time > 1.0:
            self.report({'WARNING'}, "Espera una lectura reciente del sensor")
            return {'CANCELLED'}
        try:
            mount_quaternion(settings, _last_sensor)
        except ValueError as exc:
            self.report({'WARNING'}, str(exc))
            return {'CANCELLED'}
        _reference = _last_sensor.copy()
        _control_euler = None
        _output_quat = mathutils.Quaternion((1, 0, 0, 0))
        target = target_for(settings)
        if target:
            target.rotation_mode = 'QUATERNION'
            target.rotation_quaternion = mathutils.Quaternion((1, 0, 0, 0))
        self.report({'INFO'}, "Posición actual establecida como neutra")
        return {'FINISHED'}

class ESP32_PT_MainPanel(bpy.types.Panel):
    bl_label = "ESP32 IMU Tracker"
    bl_idname = "ESP32_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ESP32'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.esp32_tracker

        col = layout.column(align=True)
        col.prop(settings, "connection_type", text="Modo")
        if settings.connection_type == "CUSTOM":
            col.prop(settings, "custom_port", text="Puerto")
        col.prop(settings, "target_object", text="Objeto 3D")

        box = layout.box()
        box.label(text=f"Estado: {settings.last_reading}", icon='INFO')

        layout.separator()

        row = layout.row(align=True)
        if not settings.is_running:
            row.operator("esp32.start_tracker", text="Conectar / Iniciar", icon='PLAY')
        else:
            row.operator("esp32.stop_tracker", text="Desconectar / Detener", icon='CANCEL')
            layout.operator("esp32.tare_tracker", text="Calibrar Posición Neutra", icon='ORIENTATION_LOCAL')

        layout.separator()
        box_axes = layout.box()
        box_axes.label(text="Orientación física del BNO")
        box_axes.prop(settings, "mount")
        if settings.mount == 'PHONE':
            box_axes.prop(settings, "phone_forward")
            box_axes.label(text="Arriba se detecta al centrar")
            if _reference is not None:
                up = _reference.inverted() @ mathutils.Vector((0, 0, 1))
                axis = max(range(3), key=lambda i: abs(up[i]))
                box_axes.label(text=f"Arriba BNO ≈ {'+' if up[axis] >= 0 else '-'}{'XYZ'[axis]}")
        if settings.mount == 'CUSTOM':
            box_axes.prop(settings, "sensor_forward")
            box_axes.prop(settings, "sensor_up")
        box_axes.label(text="Al cambiar montaje se toma un nuevo cero.")

        controls = layout.box()
        controls.label(text="Asignación e inversión")
        controls.prop(settings, "axis_mapping", text="Orden")
        for output, source in zip('XYZ', settings.axis_mapping):
            controls.label(text=f"Salida {output} ← Entrada {source}")
        controls.prop(settings, "invert_x")
        controls.prop(settings, "invert_y")
        controls.prop(settings, "invert_z")

        live = layout.box()
        live.prop(settings, "show_live", icon='DISCLOSURE_TRI_DOWN' if settings.show_live else 'DISCLOSURE_TRI_RIGHT', emboss=False)
        if settings.show_live:
            now = time.monotonic()
            recent = sum(now - stamp <= 1.0 for stamp in _packet_times)
            hz = recent / min(1.0, max(0.01, now - _connected_at)) if settings.is_running else 0.0
            live.label(text=f"Recepción: {hz:.0f} paquetes/s")
            live.label(text=f"Válidos: {_valid_packets} · Inválidos: {_invalid_packets}")
            if _last_sensor is None:
                live.label(text="Esperando primer cuaternión")
            else:
                live.label(text=f"Última lectura: {now - _last_sample_time:.2f} s")
                if _reference is not None:
                    delta = _reference.inverted() @ _last_sensor
                    delta.normalize()
                    angle = math.degrees(2 * math.acos(min(1.0, abs(delta.w))))
                    live.label(text=f"Sensor respecto del cero: {angle:.2f}°")
                live.label(text="Entrada BNO · cuaternión normalizado")
                for axis, value in zip('WXYZ', _last_sensor):
                    live.label(text=f"{axis}: {value:+.5f}")
            if _output_quat is not None:
                live.separator()
                angle = math.degrees(2 * math.acos(min(1.0, abs(_output_quat.normalized().w))))
                live.label(text=f"Salida respecto del cero: {angle:.2f}°")
                live.label(text="Salida al objeto · grados XYZ")
                for axis, value in zip('XYZ', _output_quat.to_euler('XYZ')):
                    live.label(text=f"{axis}: {math.degrees(value):+.1f}°")
            if _last_packet:
                live.label(text="Último paquete USB / BT:")
                # Split values so narrow sidebar panels remain readable.
                for index, value in enumerate(_last_packet.split(',')[1:]):
                    live.label(text=f"{'WXYZ'[index]} = {value}")
            if _last_device_message:
                live.label(text="Último mensaje del dispositivo:")
                for offset in range(0, len(_last_device_message), 30):
                    live.label(text=_last_device_message[offset:offset + 30])

classes = (
    ESP32TrackerSettings,
    ESP32_OT_StartTracker,
    ESP32_OT_StopTracker,
    ESP32_OT_TareTracker,
    ESP32_PT_MainPanel,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.esp32_tracker = bpy.props.PointerProperty(type=ESP32TrackerSettings)

def unregister():
    global _timer_active, _serial_conn
    _timer_active = False
    if bpy.app.timers.is_registered(update_tracker_timer):
        bpy.app.timers.unregister(update_tracker_timer)
    if _serial_conn:
        _serial_conn.close()
        _serial_conn = None
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    if hasattr(bpy.types.Scene, "esp32_tracker"):
        del bpy.types.Scene.esp32_tracker

if __name__ == "__main__":
    register()
    try:
        bpy.ops.esp32.start_tracker()
    except Exception as e:
        print(e)
