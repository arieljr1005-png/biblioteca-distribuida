"""Formato compartido: un objeto JSON UTF-8 por línea sobre TCP."""

import json

MAX_MENSAJE = 65536  # Incluye el salto de línea; evita lecturas sin límite.
TIMEOUT = 10.0


class ErrorProtocolo(Exception):
    """El mensaje recibido no respeta el contrato de transporte."""

    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo


def enviar(sock, objeto):
    datos = (json.dumps(objeto, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    if len(datos) > MAX_MENSAJE:
        raise ErrorProtocolo("MENSAJE_DEMASIADO_GRANDE", "El mensaje excede 65536 bytes.")
    sock.sendall(datos)


def recibir(archivo):
    """El lector persistente conserva bytes de mensajes TCP agrupados."""
    linea = archivo.readline(MAX_MENSAJE + 1)
    if not linea:
        return None
    if len(linea) > MAX_MENSAJE:
        raise ErrorProtocolo("MENSAJE_DEMASIADO_GRANDE", "El mensaje excede 65536 bytes.")
    if not linea.endswith(b"\n"):
        raise ErrorProtocolo("MENSAJE_INCOMPLETO", "Falta el salto de línea final.")
    try:
        objeto = json.loads(linea.decode("utf-8"), parse_constant=_rechazar_constante)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ErrorProtocolo("JSON_INVALIDO", "Se esperaba JSON válido codificado en UTF-8.") from exc
    if not isinstance(objeto, dict):
        raise ErrorProtocolo("SOLICITUD_INVALIDA", "El mensaje debe ser un objeto JSON.")
    return objeto


def _rechazar_constante(valor):
    raise ValueError(f"Constante JSON no válida: {valor}")
