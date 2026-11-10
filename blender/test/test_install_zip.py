import bpy,sys,pathlib
# Test actual ZIP install with clean Blender preferences and no external serial.
assert 'serial' not in sys.modules
archive=str(pathlib.Path(__file__).resolve().parents[2] / 'dist/ESP32-Tracker-Blender-1.5.1-beta.1.zip')
assert bpy.ops.preferences.addon_install(filepath=archive)=={'FINISHED'}
assert bpy.ops.preferences.addon_enable(module='esp32_tracker')=={'FINISHED'}
import esp32_tracker, serial
assert '/esp32_tracker/vendor/serial/' in serial.__file__, serial.__file__
assert hasattr(bpy.context.scene,'esp32_tracker')
assert esp32_tracker.bl_info['version']==(1,5,1)
print('PASS ZIP installation, bundled pyserial, activation and panel registration',flush=True)
bpy.ops.preferences.addon_disable(module='esp32_tracker')
