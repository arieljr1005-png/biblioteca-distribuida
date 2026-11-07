"""Cliente RPC e interfaz de consola de la biblioteca universitaria."""

import argparse
import socket
import threading

from protocolo import ErrorProtocolo, TIMEOUT, enviar, recibir


class ErrorComunicacion(Exception):
    """Fallo local de transporte o respuesta remota inválida."""


class ClienteBiblioteca:
    """Una conexión persistente. Las funciones devuelven el objeto de respuesta."""

    def __init__(self, host="127.0.0.1", puerto=5000, timeout=TIMEOUT):
        self.host, self.puerto, self.timeout = host, puerto, timeout
        self.socket = None
        self.lector = None
        self.lock = threading.Lock()  # Evita cruzar respuestas si se comparte esta instancia.

    def conectar(self):
        if self.socket is not None:
            return self
        try:
            self.socket = socket.create_connection((self.host, self.puerto), self.timeout)
            self.lector = self.socket.makefile("rb")
        except OSError as exc:
            self.cerrar()
            raise ErrorComunicacion(f"No se pudo conectar con {self.host}:{self.puerto}: {exc}") from exc
        return self

    def cerrar(self):
        if self.lector is not None:
            self.lector.close()
            self.lector = None
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def __enter__(self):
        return self.conectar()

    def __exit__(self, *args):
        self.cerrar()

    def _llamar(self, operacion, **parametros):
        with self.lock:
            if self.socket is None:
                raise ErrorComunicacion("El cliente no está conectado.")
            try:
                enviar(self.socket, {"operacion": operacion, **parametros})
                respuesta = recibir(self.lector)
                self._validar(respuesta, operacion)
                return respuesta
            except (OSError, ErrorProtocolo, ValueError, TypeError) as exc:
                self.cerrar()
                raise ErrorComunicacion(
                    f"La comunicación falló: {exc}. Si era una reserva, su resultado puede ser incierto; "
                    "no se reintenta automáticamente."
                ) from exc

    @staticmethod
    def _validar(respuesta, operacion):
        if not isinstance(respuesta, dict) or type(respuesta.get("ok")) is not bool:
            raise ValueError("Respuesta inválida: falta 'ok' booleano.")
        if not isinstance(respuesta.get("mensaje"), str):
            raise ValueError("Respuesta inválida: falta el mensaje.")
        if not respuesta["ok"]:
            if not isinstance(respuesta.get("codigo"), str):
                raise ValueError("Respuesta de error sin código.")
            return

        def libro_valido(libro):
            return (isinstance(libro, dict) and type(libro.get("id")) is int and libro["id"] > 0
                    and isinstance(libro.get("titulo"), str) and isinstance(libro.get("autor"), str)
                    and type(libro.get("disponibles")) is int and libro["disponibles"] >= 0)

        if operacion == "consultar_libros":
            libros = respuesta.get("libros")
            valido = isinstance(libros, list) and all(libro_valido(l) for l in libros)
        elif operacion in {"consultar_libro", "reservar_libro"}:
            valido = libro_valido(respuesta.get("libro"))
            if operacion == "reservar_libro":
                valido = (valido and type(respuesta.get("disponibles")) is int
                          and respuesta["disponibles"] == respuesta["libro"]["disponibles"])
        elif operacion == "estado_servidor":
            valido = (respuesta.get("estado") == "activo"
                      and type(respuesta.get("clientes_atendidos")) is int
                      and type(respuesta.get("clientes_activos")) is int
                      and 0 <= respuesta["clientes_activos"] <= respuesta["clientes_atendidos"])
        else:
            valido = True
        if not valido:
            raise ValueError("Los datos de la respuesta no cumplen el contrato de la operación.")

    def consultar_libros(self):
        return self._llamar("consultar_libros")

    def consultar_libro(self, id):
        return self._llamar("consultar_libro", id=id)

    def reservar_libro(self, id):
        return self._llamar("reservar_libro", id=id)

    def estado_servidor(self):
        return self._llamar("estado_servidor")


def mostrar(respuesta):
    if not respuesta["ok"]:
        print(f"Error [{respuesta['codigo']}]: {respuesta['mensaje']}")
        return
    print(respuesta["mensaje"])
    libros = respuesta.get("libros", [respuesta["libro"]] if "libro" in respuesta else [])
    for libro in libros:
        print(f"ID {libro['id']} | {libro['titulo']} | {libro['autor']} | Disponibles: {libro['disponibles']}")
    if "estado" in respuesta:
        print(f"Estado: {respuesta['estado']} | Conexiones atendidas: {respuesta['clientes_atendidos']}"
              f" | Clientes activos: {respuesta['clientes_activos']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--puerto", type=int, default=5000)
    args = parser.parse_args()
    if not 1 <= args.puerto <= 65535:
        parser.error("El puerto debe estar entre 1 y 65535.")
    try:
        with ClienteBiblioteca(args.host, args.puerto) as cliente:
            while True:
                print("\nSISTEMA DE BIBLIOTECA UNIVERSITARIA\n"
                      "1. Consultar todos los libros\n2. Consultar libro por ID\n"
                      "3. Reservar un libro\n4. Consultar estado del servidor\n5. Salir")
                opcion = input("Seleccione una opción: ").strip()
                if opcion == "5":
                    break
                if opcion not in {"1", "2", "3", "4"}:
                    print("Ingrese una opción del 1 al 5.")
                    continue
                if opcion in {"2", "3"}:
                    try:
                        id_libro = int(input("ID del libro: "))
                        if id_libro <= 0:
                            raise ValueError
                    except ValueError:
                        print("El ID debe ser un entero positivo.")
                        continue
                    respuesta = (cliente.consultar_libro(id_libro) if opcion == "2"
                                 else cliente.reservar_libro(id_libro))
                else:
                    respuesta = cliente.consultar_libros() if opcion == "1" else cliente.estado_servidor()
                mostrar(respuesta)
    except ErrorComunicacion as exc:
        print(f"Error: {exc}")
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nCliente cerrado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
