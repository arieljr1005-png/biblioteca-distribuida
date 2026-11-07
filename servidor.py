"""Servidor concurrente de biblioteca. Ejecutar: python servidor.py --puerto 5000."""

import argparse
import logging
import socket
import threading
import time

from protocolo import ErrorProtocolo, TIMEOUT, enviar, recibir

LOG = logging.getLogger("biblioteca")
TIMEOUT_INACTIVIDAD = 120.0  # Permite usar el menú sin dejar hilos inactivos para siempre.
CATALOGO_INICIAL = [
    {"id": 1, "titulo": "Sistemas distribuidos", "autor": "Andrew S. Tanenbaum", "disponibles": 2},
    {"id": 2, "titulo": "Redes de computadoras", "autor": "Andrew S. Tanenbaum", "disponibles": 3},
    {"id": 3, "titulo": "El tutorial de Python", "autor": "Guido van Rossum", "disponibles": 1},
    {"id": 4, "titulo": "Sistemas operativos modernos", "autor": "Andrew S. Tanenbaum", "disponibles": 2},
    {"id": 5, "titulo": "Introducción a los algoritmos", "autor": "Thomas H. Cormen", "disponibles": 4},
]


def error(codigo, mensaje):
    return {"ok": False, "codigo": codigo, "mensaje": mensaje}


class ServidorBiblioteca:
    def __init__(self, host="127.0.0.1", puerto=5000):
        self.host = host
        self.puerto = puerto
        self.catalogo = {libro["id"]: libro.copy() for libro in CATALOGO_INICIAL}
        self.lock = threading.Lock()
        self.lock_clientes = threading.Lock()
        self.clientes_atendidos = 0  # Conexiones aceptadas acumuladas, incluida la actual.
        self.conexiones = set()
        self.hilos = set()
        self.detener = threading.Event()
        self.listo = threading.Event()
        self.socket = None
        self.inicio = time.monotonic()

    def ejecutar(self):
        """Acepta conexiones; cada hilo atiende varias RPC en una conexión."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as escucha:
                self.socket = escucha
                escucha.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                escucha.bind((self.host, self.puerto))
                self.puerto = escucha.getsockname()[1]  # Puerto 0 útil para pruebas aisladas.
                escucha.listen(32)
                escucha.settimeout(0.2)
                self.inicio = time.monotonic()
                self.listo.set()
                LOG.info("Servidor escuchando en %s:%s", self.host, self.puerto)
                while not self.detener.is_set():
                    try:
                        conexion, direccion = escucha.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        if self.detener.is_set():
                            break
                        raise
                    conexion.settimeout(TIMEOUT_INACTIVIDAD)
                    hilo = threading.Thread(target=self._atender, args=(conexion, direccion),
                                            name=f"cliente-{direccion[1]}", daemon=True)
                    with self.lock_clientes:
                        self.clientes_atendidos += 1
                        self.conexiones.add(conexion)
                        self.hilos.add(hilo)
                    hilo.start()
        finally:
            self.cerrar()
            with self.lock_clientes:
                hilos = list(self.hilos)
            for hilo in hilos:
                if hilo is not threading.current_thread():
                    hilo.join(timeout=TIMEOUT + 1)

    def cerrar(self):
        self.detener.set()
        with self.lock_clientes:
            conexiones = list(self.conexiones)
        for conexion in conexiones:
            try:
                conexion.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        # accept usa timeout: no depende de otra conexión para finalizar.

    def _atender(self, conexion, direccion):
        LOG.info("Cliente conectado: %s:%s", *direccion)
        try:
            with conexion, conexion.makefile("rb") as lector:
                while not self.detener.is_set():
                    try:
                        solicitud = recibir(lector)
                        if solicitud is None:
                            break
                        respuesta = self.procesar(solicitud)
                    except ErrorProtocolo as exc:
                        enviar(conexion, error(exc.codigo, str(exc)))
                        # Se cierra: una trama excesiva puede dejar bytes sin consumir.
                        break
                    enviar(conexion, respuesta)
        except (OSError, TimeoutError) as exc:
            LOG.info("Comunicación finalizada con %s: %s", direccion, exc)
        except Exception:
            LOG.exception("Error inesperado atendiendo a %s", direccion)
            try:
                enviar(conexion, error("ERROR_INTERNO", "Error interno del servidor."))
            except (OSError, ErrorProtocolo):
                pass
        finally:
            with self.lock_clientes:
                self.conexiones.discard(conexion)
                self.hilos.discard(threading.current_thread())
            LOG.info("Cliente desconectado: %s:%s", *direccion)

    def procesar(self, solicitud):
        operacion = solicitud.get("operacion")
        if not isinstance(operacion, str):
            return error("SOLICITUD_INVALIDA", "Se requiere 'operacion' de tipo texto.")
        operaciones = {"consultar_libros", "consultar_libro", "reservar_libro", "estado_servidor"}
        if operacion not in operaciones:
            return error("OPERACION_DESCONOCIDA", "La operación solicitada no existe.")
        campos = {"operacion", "id"} if operacion in {"consultar_libro", "reservar_libro"} else {"operacion"}
        if set(solicitud) != campos:
            return error("PARAMETROS_INVALIDOS", "Faltan parámetros o hay campos no permitidos.")
        if "id" in campos and (type(solicitud["id"]) is not int or solicitud["id"] <= 0):
            return error("PARAMETROS_INVALIDOS", "El id debe ser un entero positivo; no se admite booleano.")
        if operacion == "estado_servidor":
            with self.lock_clientes:
                return {"ok": True, "mensaje": "Servidor en funcionamiento.", "estado": "activo",
                        "clientes_atendidos": self.clientes_atendidos,
                        "clientes_activos": len(self.conexiones),
                        "segundos_activo": round(time.monotonic() - self.inicio, 2)}
        # La lectura también toma el Lock para producir copias coherentes.
        with self.lock:
            if operacion == "consultar_libros":
                return {"ok": True, "mensaje": "Catálogo consultado.",
                        "libros": [libro.copy() for libro in self.catalogo.values()]}
            libro = self.catalogo.get(solicitud["id"])
            if libro is None:
                return error("LIBRO_NO_ENCONTRADO", "No existe un libro con ese id.")
            if operacion == "consultar_libro":
                return {"ok": True, "mensaje": "Libro consultado.", "libro": libro.copy()}
            # Sección crítica indivisible: comprobar y decrementar bajo el mismo Lock.
            if libro["disponibles"] <= 0:
                return error("SIN_EJEMPLARES", "No quedan ejemplares disponibles.")
            libro["disponibles"] -= 1
            return {"ok": True, "mensaje": "Reserva realizada correctamente.",
                    "libro": libro.copy(), "disponibles": libro["disponibles"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Interfaz local de escucha")
    parser.add_argument("--puerto", type=int, default=5000)
    args = parser.parse_args()
    if not 1 <= args.puerto <= 65535:
        parser.error("El puerto debe estar entre 1 y 65535.")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(threadName)s] %(message)s")
    servidor = ServidorBiblioteca(args.host, args.puerto)
    try:
        servidor.ejecutar()
    except KeyboardInterrupt:
        LOG.info("Apagado solicitado con Ctrl+C.")
    except OSError as exc:
        parser.exit(1, f"No se pudo iniciar el servidor: {exc}\n")
    finally:
        servidor.cerrar()


if __name__ == "__main__":
    main()
