"""Idempotent build-time fix for Adafruit BNO08x 1.2.7 SH2 session leak."""
from pathlib import Path

def patch(path):
    source = path.read_text()
    marker = '/* Tracker: release the previous transport before reopening. */'
    if marker in source:
        return
    anchor = '    // Clear everything in sh2 structure.\n    memset(&_sh2, 0, sizeof(_sh2));'
    if source.count(anchor) != 1:
        raise RuntimeError('Unexpected SH2 source; review the reopen patch before building')
    source = source.replace(anchor, '    ' + marker + '\n    if (pSh2->pShtp != 0) {\n        sh2_close();\n    }\n\n' + anchor)
    path.write_text(source)
    print('Applied SH2 reopen fix')

try:
    Import('env')
except NameError:
    patch(Path(__file__).resolve().parents[1] / '.pio/libdeps/esp32doit-devkit-v1/Adafruit BNO08x/src/sh2.c')
else:
    patch(Path(env.subst('$PROJECT_LIBDEPS_DIR')) / env.subst('$PIOENV') / 'Adafruit BNO08x/src/sh2.c')
