"""Build the installable Windows addon ZIP without Blender or firmware changes."""
from pathlib import Path
import hashlib
import zipfile

root = Path(__file__).resolve().parents[1]
output = root / 'dist/windows-1.6.0-beta.1'
output.mkdir(parents=True, exist_ok=True)
archive = output / 'ESP32-Tracker-Windows-1.6.0-beta.1.zip'
package = root / 'blender/esp32_tracker'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
    for source in sorted(package.rglob('*')):
        if source.is_file() and '__pycache__' not in source.parts and source.suffix not in ('.pyc', '.pyo'):
            data = source.read_bytes()
            if source.suffix == '.py':
                compile(data, source.name, 'exec')
            bundle.writestr(source.relative_to(package.parent).as_posix(), data)
    bundle.writestr('LEEME-Windows.md', (root/'docs/WINDOWS.md').read_bytes())
with zipfile.ZipFile(archive) as bundle:
    if bundle.testzip() is not None:
        raise RuntimeError('Damaged ZIP')
    for name in ('esp32_tracker/__init__.py','esp32_tracker/tracker.py',
                 'esp32_tracker/ports.py','esp32_tracker/vendor/serial/serialwin32.py',
                 'esp32_tracker/vendor/PYSERIAL-LICENSE.txt'):
        assert name in bundle.namelist(), name
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
(output/'SHA256SUMS').write_text(f'{checksum}  {archive.name}\n')
(output/'LEEME-Windows.md').write_bytes((root/'docs/WINDOWS.md').read_bytes())
print(archive.name)
print(checksum)
