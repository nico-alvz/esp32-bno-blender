# ESP32 + BNO → Blender

Control de orientación de objetos en Blender con ESP32 clásico y BNO055/BNO08x por USB o Bluetooth SPP. Interfaz en español.

## Estructura

- `firmware/`: PlatformIO/Arduino, recuperación I²C y pruebas SH2.
- `blender/`: complemento instalable Blender 4.0+, dependencia incluida y pruebas.
- Releases: ZIP único del complemento para Linux/Windows y firmware separado con SHA256SUMS.

## Hardware

ESP32 DevKit V1 clásico (S2/S3/C3 no soportan el SPP requerido). Conectar GND común, SDA a GPIO21 y SCL a GPIO22. Alimentar según la especificación del módulo; las señales I²C deben ser de 3,3 V. Usar cables cortos y revisar pull-ups. El firmware detecta BNO055/BNO08x y transmite `Q,w,x,y,z\n` a 115200 baudios. Bluetooth se anuncia como `ESP32_Tracker`. El reporte BNO08x solicitado es 50 Hz; ver frecuencia efectiva en el panel.

## Instalar en Blender · Linux y Windows

**Windows:** usa la release dedicada **v1.6.0-windows-beta.1** y el archivo **ESP32-Tracker-Windows-1.6.0-beta.1.zip**. [Guía Windows paso a paso](docs/WINDOWS.md): detección y selección de COM, comparación de puertos nuevos/retirados y Bluetooth SPP con COM saliente.

**Linux:** conserva su release separada **v1.5.1-beta.1** y su ZIP **ESP32-Tracker-Blender-1.5.1-beta.1.zip**. USB usa `/dev/ttyUSB0` o `/dev/ttyACM0`; Bluetooth necesita el puerto RFCOMM previamente enlazado.

En ambos casos instala el ZIP sin descomprimir desde **Blender → Editar → Preferencias → Complementos → Instalar desde disco**, actívalo y abre **N → ESP32**. Incluye pyserial y su licencia: no requiere pip, terminal ni instalar Python. El firmware es una descarga separada.

La nueva enumeración usa los puertos que informa el sistema. Detecta automáticamente cuando hay un solo candidato del transporte elegido; con varios exige seleccionar. **Actualizar puertos** compara con el escaneo anterior y muestra altas/bajas. No abre todos los COM ni garantiza que estén libres. El intento de conexión al puerto elegido informa si está ocupado o hay acceso denegado. Para reconstruir el ZIP de Windows: `python tools/package_windows.py`.

## Montaje y calibración

La primera muestra establece la postura neutral; **Calibrar Cero (Tare)** vuelve a centrar. Mantener quieto el dispositivo al centrar.

- Horizontal: frente +Y del sensor, arriba +Z.
- Vertical sobre celular: colocar el celular vertical, seleccionar cara hacia afuera (+Z o -Z del BNO) y centrar. Arriba se deriva de la orientación medida; no se supone +Y. Se rechaza una postura casi horizontal.
- Personalizado: seleccionar frente y arriba perpendiculares; admite 24 orientaciones.

Después de cambiar montaje/cara volver a centrar. Conversión: `M @ (Q0.inverted() @ Q) @ M.inverted()`. La asignación y las inversiones trabajan directamente sobre el eje de rotación del cuaternión relativo, sin conversión a Euler ni acumulación de movimientos. Los ángulos Euler del panel son solo de visualización. El panel muestra datos crudos, cuaternión normalizado, salida XYZ, frecuencia, paquetes válidos/inválidos y último mensaje del firmware.

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


### Intercambio de controles

En **Asignación e inversión → Orden** puedes elegir XYZ, XZY, YXZ, YZX, ZXY o ZYX. Cada letra indica la entrada que controla las salidas X, Y y Z, en ese orden. Por ejemplo, ZYX intercambia pitch y yaw (X/Z). Las inversiones se aplican después, a cada eje de salida. XYZ conserva el comportamiento original. El intercambio permuta las componentes del eje de rotación del cuaternión relativo y las inversiones cambian sus sentidos. Conserva el ángulo total, la rotación identidad y la equivalencia Q/-Q; no depende de la trayectoria anterior. Las permutaciones impares son una convención de control, no un cambio físico de base de coordenadas. Los ángulos Euler solo se usan para mostrar datos. Prueba manualmente las combinaciones con tu montaje y centra cuando lo necesites.

Si al volver a la postura inicial el objeto no coincide, compara **Sensor respecto del cero** y **Salida respecto del cero**. Si el primero no vuelve cerca de 0°, la lectura del BNO ha cambiado respecto de la referencia. Si ambos vuelven cerca de 0° pero la apariencia difiere, revisa padres, restricciones u otras animaciones del objeto. No se ha validado físicamente esta actualización.

**Invertir X** está activado por defecto en todos los montajes y puede desactivarse manualmente. Seleccionar **Horizontal** aplica orden **XYZ**; seleccionar **Vertical sobre celular** aplica orden **YXZ**. Al cambiar de montaje se restablece Invertir X al valor activado.

Validación manual: el usuario confirmó retorno correcto al centro con el control directo por cuaterniones en montaje vertical y orden YXZ.
