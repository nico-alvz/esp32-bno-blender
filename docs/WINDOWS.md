# ESP32 IMU Tracker · Windows · 1.6.0 beta 1

## Instalar sin terminal

1. Descarga **ESP32-Tracker-Windows-1.6.0-beta.1.zip** de la release específica de Windows. No lo descomprimas.
2. En Blender 4 o superior: **Editar → Preferencias → Complementos → Instalar desde disco**. Instala el ZIP y activa **ESP32 IMU Tracker**. Si tenías una versión anterior, desactívala y elimínala antes; reinicia Blender después de actualizar.
3. Abre la vista 3D, pulsa **N → ESP32** y selecciona el objeto que quieres mover.

El ZIP incluye pyserial y su licencia. No necesitas pip ni instalar Python. Usa el firmware que ya tiene la ESP32; esta actualización del complemento no requiere volver a grabarlo.

## Por cable USB

1. En el panel selecciona **Cable USB (automático)** y deja **Puerto** vacío.
2. Pulsa **Actualizar puertos**. Si solo hay un adaptador USB serie, puedes pulsar **Conectar / Iniciar**.
3. Si hay varios, el complemento te pide elegir: pulsa el botón del COM de tu ESP32 y luego **Conectar / Iniciar**.

Para reconocer el COM, actualiza con la placa desconectada, conéctala y vuelve a actualizar. El puerto que apareció llevará **Nuevo**; el que desaparezca al desconectar llevará **Retirado**. El escaneo enumera puertos, no los abre. Puedes escribir el nombre manualmente: `COM5`, `COM12`, etc.

Si no aparece ningún COM, revisa un cable USB que transmita datos y **Administrador de dispositivos → Puertos (COM y LPT)**. Si Windows muestra un dispositivo sin controlador, instala el controlador del chip USB serie que usa tu placa (por ejemplo, CP210x o CH340) desde su fabricante. El complemento no instala controladores.

## Por Bluetooth

1. Alimenta la ESP32 y empareja **ESP32_Tracker** en la configuración Bluetooth de Windows.
2. Abre **Más opciones/configuración de Bluetooth → Puertos COM**. Identifica el puerto **Saliente** asociado a ESP32_Tracker. Los nombres de los menús varían entre versiones de Windows. Si no hay puerto saliente, añádelo para el servicio serie del dispositivo.
3. En Blender selecciona **Bluetooth SPP**, pulsa **Actualizar puertos**, elige ese COM y pulsa **Conectar / Iniciar**. También puedes escribir el COM en **Puerto**.

Bluetooth aquí es **SPP clásico**, no BLE. No se usa `/dev/rfcomm0` en Windows. Un dispositivo emparejado puede tener COM entrante y saliente: la enumeración no permite distinguirlos siempre. Si hay varios candidatos, el complemento exige elegir; no abre todos para probarlos. Si Windows no proporciona información Bluetooth, el COM aparece como **Serie**, y sigue siendo seleccionable. Se omite el pulso de reinicio USB cuando el modo o la descripción identifican Bluetooth.

Un COM existente no demuestra que haya lecturas. Comprueba **Recibiendo orientación**, paquetes/s mayores de cero y la antigüedad de la última lectura. Si pasan cinco segundos sin recibir datos en modo Bluetooth, el panel recuerda comprobar el COM saliente.

## Puertos ocupados y errores

La lista muestra puertos presentes en Windows, no garantiza que estén libres ni que pertenezcan a la ESP32. La clasificación USB/Bluetooth depende de los datos que entregue el controlador.

- **Ocupado / acceso denegado:** cierra Arduino Serial Monitor, terminales, otras instancias de Blender o aplicaciones que usen el COM. Comprueba también que elegiste el COM saliente.
- **Varios puertos posibles:** pulsa el COM correcto en la lista; no se selecciona el primero arbitrariamente.
- **Windows usa puertos COM:** elimina una ruta Linux heredada y elige un COM detectado.
- **No aparece al actualizar:** revisa emparejamiento SPP o cable/controlador según el transporte.
- **Conectado pero sin orientación:** revisa los datos en vivo y el último mensaje del firmware. El complemento puede abrir un puerto aunque el BNO no esté transmitiendo.

Para cambiar de puerto, primero pulsa **Desconectar / Detener**. El botón **Usar automático** borra la elección manual; conserva el modo USB o Bluetooth elegido.

## Montaje

Horizontal aplica **XYZ** y vertical aplica **YXZ**. **Invertir X** viene activado por defecto; puedes cambiarlo. Sostén el dispositivo en la postura neutra y pulsa **Calibrar Posición Neutra**. Las seis asignaciones e inversiones siguen disponibles.

## Alcance de esta beta

Se comprobaron la selección y comparación de COM con pruebas de Python que simulan la enumeración de Windows. No se ejecutaron pruebas automatizadas de Blender, ni se validó una conexión física en Windows en el entorno de desarrollo. Confirmar manualmente USB y Bluetooth con el equipo del usuario. Las releases anteriores de Linux permanecen separadas.

Referencias: [enumeración de puertos de pyserial](https://pyserial.readthedocs.io/en/latest/tools.html) y [localización del COM saliente SPP en Windows](https://www.junipersys.com/support/article/14876).
