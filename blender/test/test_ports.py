"""Serial selection regressions, using plain Python; no Blender or device I/O."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
spec = importlib.util.spec_from_file_location('ports', Path(__file__).resolve().parents[1]/'esp32_tracker/ports.py')
ports = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ports)

def port(device, description='', hwid='', vid=None):
    return SimpleNamespace(device=device, description=description, hwid=hwid, vid=vid)

class PortSelection(unittest.TestCase):
    def test_windows_usb(self):
        self.assertEqual(ports.resolve_port('USB', '', [port('COM11','CP210x',vid=0x10c4)],'win32'),'COM11')
    def test_windows_bt(self):
        self.assertEqual(ports.resolve_port('BT','',[port('COM7',hwid='BTHENUM\\DEV_A'),port('COM4',vid=123)],'win32'),'COM7')
    def test_bluetooth_has_priority_over_usb_metadata(self):
        self.assertEqual(ports.port_kind(port('COM7','Bluetooth USB adapter',vid=1)),'BT')
    def test_manual_high_com(self):
        self.assertEqual(ports.resolve_port('BT',' com123 ',[],'win32'),'COM123')
    def test_saved_linux_path_on_windows(self):
        with self.assertRaisesRegex(ValueError,'Windows usa puertos COM'):
            ports.resolve_port('BT','/dev/rfcomm0',[],'win32')
    def test_windows_never_guesses_linux_or_com3(self):
        for mode in ('USB','BT','CUSTOM'):
            with self.assertRaises(ValueError): ports.resolve_port(mode,'',[],'win32')
    def test_ambiguous_bluetooth(self):
        with self.assertRaisesRegex(ValueError,'varios'):
            ports.resolve_port('BT','',[port('COM6','Bluetooth'),port('COM7','Bluetooth')],'win32')
    def test_ambiguous_usb(self):
        with self.assertRaisesRegex(ValueError,'varios'):
            ports.resolve_port('USB','',[port('COM4',vid=1),port('COM5',vid=2)],'win32')
    def test_unknown_ports_stay_selectable_manually(self):
        p=port('COM9','Puerto serie')
        self.assertEqual(ports.port_kind(p),'CUSTOM')
        self.assertEqual(ports.resolve_port('CUSTOM',p.device,[p],'win32'),'COM9')
    def test_linux_rfcomm_and_usb(self):
        self.assertEqual(ports.resolve_port('BT','',[port('/dev/rfcomm0')],'linux'),'/dev/rfcomm0')
        self.assertEqual(ports.resolve_port('USB','',[port('/dev/ttyUSB0')],'linux'),'/dev/ttyUSB0')
    def test_compare_add_remove_reconnect(self):
        self.assertEqual(ports.compare_ports(['COM1'],['COM1','COM12']),(['COM12'],[]))
        self.assertEqual(ports.compare_ports(['COM1','COM12'],['COM1']),([],['COM12']))
        self.assertEqual(ports.compare_ports(['COM12'],['COM12']),([],[]))
if __name__=='__main__': unittest.main()
