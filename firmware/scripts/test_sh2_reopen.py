"""Run after pio run; compiles the actual dependency with a mock transport."""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
lib = root / '.pio/libdeps/esp32doit-devkit-v1/Adafruit BNO08x/src'
with tempfile.TemporaryDirectory() as work:
    binary = str(Path(work) / 'test_sh2')
    subprocess.run(['cc', '-I', str(lib), str(root/'test/test_sh2_reopen.c'),
                    *(str(lib/f) for f in ('sh2.c','shtp.c','sh2_util.c')), '-o', binary], check=True)
    subprocess.run([binary], check=True)
