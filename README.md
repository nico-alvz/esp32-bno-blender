# ESP32 + BNO → Blender · 1.5.0 beta

Control de orientación de objetos en Blender con ESP32 clásico y BNO055/BNO08x por USB o Bluetooth SPP. Interfaz en español.

## Estructura

- `firmware/`: PlatformIO/Arduino, recuperación I²C y pruebas SH2.
- `blender/`: complemento Blender 4.0+, pruebas y lanzadores Linux/Windows.
- Releases: ZIP del complemento, paquetes Linux/Windows y binarios ESP32 con SHA256SUMS.

## Hardware

ESP32 DevKit V1 clásico (S2/S3/C3 no soportan el SPP requerido). Conectar GND común, SDA a GPIO21 y SCL a GPIO22. Alimentar según la especificación del módulo; las señales I²C deben ser de 3,3 V. Usar cables cortos y revisar pull-ups. El firmware detecta BNO055/BNO08x y transmite `Q,w,x,y,z\n` a 115200 baudios. Bluetooth se anuncia como `ESP32_Tracker`. El reporte BNO08x solicitado es 50 Hz; ver frecuencia efectiva en el panel.

## Instalar en Blender (Linux y Windows)

1. Instalar Blender 4.0+ y descargar/descomprimir el complemento.
2. Instalar pyserial en el Python de Blender. En su consola Python (Shift+F4):

```python
import bpy, pathlib, subprocess, sys
target = str(pathlib.Path(bpy.utils.user_resource('SCRIPTS', create=True)) / 'modules')
subprocess.check_call([sys.executable, '-m', 'ensurepip', '--user'])
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--target', target, 'pyserial==3.5'])
```

Reiniciar Blender. Si la distribución no incluye ensurepip, usar Blender oficial con Python incorporado.

3. Preferencias → Complementos → instalar desde disco (menú desplegable en versiones recientes): seleccionar `blender_tracker.py` y activar. Alternativamente abrir el archivo en el editor de texto y ejecutar para esa sesión.
4. Vista 3D → N → ESP32: seleccionar objeto, puerto y Conectar.

USB automático elige el primer dispositivo USB serie; con varios dispositivos usar **Personalizado**. Linux: `/dev/ttyUSB0` o `/dev/ttyACM0`; se requieren permisos sobre el puerto (habitualmente grupo dialout, cerrar sesión tras modificar grupos). Windows: consultar Administrador de dispositivos e introducir `COM3`, por ejemplo. Instalar controlador CP210x/CH340 según la placa.

Bluetooth: emparejar `ESP32_Tracker` y configurar un puerto serie SPP; Linux usa RFCOMM (habitualmente `/dev/rfcomm0`), Windows el COM saliente. BLE no funciona. Los lanzadores `open_blender.sh`/`.bat` requieren `blender` en PATH. También se puede usar la ruta completa a Blender con `--python blender_tracker.py`.

## Montaje y calibración

La primera muestra establece la postura neutral; **Calibrar Cero (Tare)** vuelve a centrar. Mantener quieto el dispositivo al centrar.

- Horizontal: frente +Y del sensor, arriba +Z.
- Vertical sobre celular: colocar el celular vertical, seleccionar cara hacia afuera (+Z o -Z del BNO) y centrar. Arriba se deriva de la orientación medida; no se supone +Y. Se rechaza una postura casi horizontal.
- Personalizado: seleccionar frente y arriba perpendiculares; admite 24 orientaciones.

Después de cambiar montaje/cara volver a centrar. Conversión: `M @ (Q0.inverted() @ Q) @ M.inverted()`. Sin inversiones conserva cuaterniones. Las inversiones X/Y/Z usan Euler XYZ relativos y tienen singularidad cerca de Y = ±90°. El panel muestra datos crudos, cuaternión normalizado, salida XYZ, frecuencia, paquetes válidos/inválidos y último mensaje del firmware.

## Compilar y grabar firmware

Instalar Python y PlatformIO: `python -m pip install platformio`. Desde `firmware/`:

```sh
pio run
pio run -t upload --upload-port /dev/ttyUSB0
pio device monitor -p /dev/ttyUSB0 -b 115200
```

Windows: reemplazar puerto por `COM3`. Cerrar Blender/monitores antes de grabar. La placa objetivo es `esp32doit-devkit-v1` con particiones huge_app.

Para binarios de release, verificar SHA256SUMS e instalar `python -m pip install esptool`. Desde la carpeta de binarios:

```sh
python -m esptool --chip esp32 --port /dev/ttyUSB0 --baud 460800 write-flash 0x1000 bootloader.bin 0x8000 partitions.bin 0xe000 boot_app0.bin 0x10000 firmware.bin
```

En Windows usar `--port COM3`. Grabar modifica la flash; conservar copia del firmware anterior si se necesita.

## Recuperación y limitaciones de esta beta

Recuperación del bus mediante señales open-drain y watchdog tras dos segundos sin enviar cuaterniones válidos. El hook `scripts/patch_sh2.py` libera la sesión SH2 anterior al reabrir Adafruit BNO08x **1.2.7**, fijado en PlatformIO. El parche es idempotente y falla si cambia el código esperado; revisar antes de actualizar la biblioteca.

La prueba de host cubre 100 reaperturas SH2. **La recuperación física y el nuevo montaje vertical todavía requieren confirmación con el dispositivo.** No se garantiza estabilidad continua. Adafruit advierte particularidades I²C del BNO08x con ESP32: https://learn.adafruit.com/adafruit-9-dof-orientation-imu-fusion-breakout-bno085/python-circuitpython . Revisar alimentación, cableado y pull-ups si hay cortes. GAME_ROTATION_VECTOR puede presentar deriva de rumbo.

Los paquetes Linux/Windows contienen fuentes portables y firmware ESP32; no incluyen Blender, Python ni controladores. Windows no ha sido probado físicamente.

## Pruebas

Desde la raíz:

```sh
blender --background --factory-startup --python-exit-code 1 --python blender/test/test_tracker.py
python firmware/scripts/test_sh2_reopen.py
```

La segunda requiere firmware compilado y compilador C (`cc`). Se prueban 24 orientaciones, postura neutral observada, modo vertical, inversiones, parser fragmentado, muestras inválidas y ciclo de conexión. Un error de la extensión interna de Blender por `cattrs` puede ser ajeno al complemento; comprobar las aserciones y salida final.

## Diagnóstico

- Puerto ocupado: cerrar monitores y otras sesiones; revisar permisos o controlador USB.
- Sin datos: verificar 115200, GND/SDA/SCL y mensajes de escaneo del sensor.
- Orientación incorrecta: revisar montaje/cara, desactivar inversiones y volver a centrar.
- Bluetooth: verificar SPP clásico y puerto saliente COM/RFCOMM.
- Cortes: conservar mensajes del watchdog y revisar bus/alimentación.
