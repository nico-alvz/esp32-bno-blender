"""Serial discovery/selection only. Scanning never opens a serial device."""
import re


def port_kind(port):
    description = ' '.join(str(getattr(port, field, '') or '') for field in
                           ('device', 'description', 'hwid', 'manufacturer')).casefold()
    if any(word in description for word in ('bluetooth', 'bthenum', 'bthmodem', 'rfcomm', 'estándar sobre bluetooth')):
        return 'BT'
    if getattr(port, 'vid', None) is not None or any(word in description for word in
            ('usb', 'cp210', 'ch340', 'ch341', 'ftdi')):
        return 'USB'
    return 'CUSTOM'


def resolve_port(mode, manual, ports, platform):
    """Select only an unambiguous transport match; never guess COM3."""
    manual = manual.strip()
    if manual:
        if platform == 'win32':
            if not re.fullmatch(r'COM[1-9][0-9]*', manual, re.IGNORECASE):
                raise ValueError('Windows usa puertos COM: elige uno de la lista o escribe COM5, por ejemplo.')
            return manual.upper()
        return manual
    if mode == 'CUSTOM':
        raise ValueError('Selecciona un puerto detectado o escribe el puerto manual.')
    candidates = [port.device for port in ports if port_kind(port) == mode]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise ValueError('Hay varios puertos posibles. Elige el de la ESP32 en Puertos detectados.')
    if mode == 'BT':
        raise ValueError('No se detecta un puerto Bluetooth SPP. Empareja ESP32_Tracker y selecciona su COM saliente.'
                         if platform == 'win32' else 'Enlaza Bluetooth SPP y actualiza la lista; puedes escribir /dev/rfcomm0.')
    raise ValueError('No se detecta un adaptador USB serie. Revisa cable de datos/controlador y actualiza la lista.')


def compare_ports(before, after):
    return sorted(set(after) - set(before)), sorted(set(before) - set(after))
