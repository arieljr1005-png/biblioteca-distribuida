"""Pruebas de integración con TCP real; ejecutar: python pruebas.py."""

import io
import json
import logging
import multiprocessing
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import time
import unittest
from datetime import datetime, timezone

from cliente import ClienteBiblioteca, ErrorComunicacion
from protocolo import MAX_MENSAJE, enviar, recibir
from servidor import ServidorBiblioteca


def proceso_cliente(puerto, barrera, salida, tarea):
    """Función de nivel superior para multiprocessing con spawn en Windows."""
    try:
        with ClienteBiblioteca(puerto=puerto) as cliente:
            # Una primera RPC confirma que el servidor ya aceptó este socket.
            if not cliente.estado_servidor()["ok"]:
                raise RuntimeError("El servidor no confirmó la conexión.")
            # Los tres procesos ya tienen conexiones abiertas antes de continuar.
            barrera.wait(timeout=15)
            if tarea == "catalogo":
                respuestas = [cliente.consultar_libros()]
            elif tarea == "reserva":
                respuestas = [cliente.reservar_libro(3)]
            elif tarea == "muchas_reservas":
                respuestas = [cliente.reservar_libro(3) for _ in range(10)]
            else:
                respuestas = [cliente.estado_servidor()]
            salida.put({"pid": os.getpid(), "tarea": tarea, "respuestas": respuestas})
    except Exception as exc:
        salida.put({"pid": os.getpid(), "error": repr(exc)})


class PruebasBiblioteca(unittest.TestCase):
    def setUp(self):
        self.detalles = {}
        self.servidor = ServidorBiblioteca(puerto=0)
        self.hilo = threading.Thread(target=self.servidor.ejecutar, daemon=True)
        self.hilo.start()
        self.assertTrue(self.servidor.listo.wait(5), "El servidor no inició.")
        self.puerto = self.servidor.puerto

    def tearDown(self):
        self.servidor.cerrar()
        self.hilo.join(12)
        self.assertFalse(self.hilo.is_alive(), "El servidor no terminó.")
        self.assertFalse(self.servidor.hilos, "Quedaron hilos cliente activos.")

    def paralelo(self, tareas):
        contexto = multiprocessing.get_context("spawn")
        barrera = contexto.Barrier(len(tareas))
        salida = contexto.Queue()
        procesos = [contexto.Process(target=proceso_cliente,
                     args=(self.puerto, barrera, salida, tarea)) for tarea in tareas]
        try:
            for proceso in procesos:
                proceso.start()
            resultados = []
            for _ in procesos:
                try:
                    resultados.append(salida.get(timeout=25))
                except queue.Empty:
                    self.fail("Un proceso cliente no entregó resultado.")
            for proceso in procesos:
                proceso.join(5)
                self.assertEqual(proceso.exitcode, 0)
            self.detalles["procesos"] = resultados
            self.assertEqual(len({r["pid"] for r in resultados}), len(tareas))
            self.assertTrue(all("error" not in r for r in resultados), resultados)
            return resultados
        finally:
            for proceso in procesos:
                if proceso.is_alive():
                    proceso.terminate()
                    proceso.join(5)
            salida.close()
            salida.join_thread()

    def test_01_consultas_simultaneas(self):
        """Caso 1: tres procesos consultan simultáneamente el catálogo."""
        resultados = self.paralelo(["catalogo"] * 3)
        respuestas = [r["respuestas"][0] for r in resultados]
        self.assertTrue(all(r["ok"] and len(r["libros"]) == 5 for r in respuestas))
        self.assertEqual(respuestas[0]["libros"], respuestas[1]["libros"])
        self.assertEqual(respuestas[1]["libros"], respuestas[2]["libros"])

    def test_02_ultimo_ejemplar(self):
        """Caso 2: dos reservan el último ejemplar y un tercer proceso consulta estado."""
        resultados = self.paralelo(["reserva", "reserva", "estado"])
        reservas = [r["respuestas"][0] for r in resultados if r["tarea"] == "reserva"]
        self.assertEqual(sum(r["ok"] for r in reservas), 1)
        self.assertEqual([r["codigo"] for r in reservas if not r["ok"]], ["SIN_EJEMPLARES"])
        estado = next(r["respuestas"][0] for r in resultados if r["tarea"] == "estado")
        self.assertEqual(estado["clientes_atendidos"], 3)
        with ClienteBiblioteca(puerto=self.puerto) as cliente:
            final = cliente.consultar_libro(3)
        self.assertEqual(final["libro"]["disponibles"], 0)
        self.detalles["disponibilidad_final"] = 0

    def test_03_id_inexistente(self):
        """Caso 3: consultar y reservar un ID inexistente."""
        with ClienteBiblioteca(puerto=self.puerto) as cliente:
            respuestas = [cliente.consultar_libro(9999), cliente.reservar_libro(9999)]
        for respuesta in respuestas:
            self.assertFalse(respuesta["ok"])
            self.assertEqual(respuesta["codigo"], "LIBRO_NO_ENCONTRADO")
        self.detalles["respuestas"] = respuestas

    def test_04_desconexion_antes_de_leer(self):
        """Caso 4: envía reserva y cierra sin leer; el servicio sigue disponible."""
        with socket.create_connection(("127.0.0.1", self.puerto), timeout=3) as conexion:
            enviar(conexion, {"operacion": "reservar_libro", "id": 3})
            conexion.shutdown(socket.SHUT_RDWR)
        # La reserva puede ejecutarse aunque el cliente no llegue a leer la respuesta.
        limite = time.monotonic() + 3
        with ClienteBiblioteca(puerto=self.puerto) as cliente:
            while True:
                libro = cliente.consultar_libro(3)
                if libro["libro"]["disponibles"] == 0 or time.monotonic() >= limite:
                    break
                time.sleep(0.01)
            estado = cliente.estado_servidor()
        self.assertEqual(libro["libro"]["disponibles"], 0)
        self.assertTrue(estado["ok"])
        self.detalles.update(reserva_sin_leer=libro, estado_posterior=estado)

    def test_05_operacion_desconocida(self):
        """Caso 5: operación no registrada y siguiente RPC en la misma conexión."""
        with ClienteBiblioteca(puerto=self.puerto) as cliente:
            respuesta = cliente._llamar("borrar_catalogo")
            self.assertFalse(respuesta["ok"])
            self.assertEqual(respuesta["codigo"], "OPERACION_DESCONOCIDA")
            self.assertTrue(cliente.consultar_libros()["ok"])
        self.detalles["respuesta"] = respuesta

    def test_06_reservas_repetidas_no_negativas(self):
        resultados = self.paralelo(["muchas_reservas"] * 3)
        respuestas = [r for p in resultados for r in p["respuestas"]]
        self.assertEqual(sum(r["ok"] for r in respuestas), 1)
        self.assertEqual(sum(r.get("codigo") == "SIN_EJEMPLARES" for r in respuestas), 29)
        with ClienteBiblioteca(puerto=self.puerto) as cliente:
            libros = cliente.consultar_libros()["libros"]
        self.assertTrue(all(l["disponibles"] >= 0 for l in libros))
        self.detalles.update(intentos=30, exitos=1, sin_ejemplares=29, catalogo_final=libros)

    def test_07_parametros_invalidos(self):
        solicitudes = [
            {}, {"operacion": 5}, {"operacion": "consultar_libro"},
            *({"operacion": "reservar_libro", "id": valor} for valor in [True, -1, 0, "3", 1.5, None]),
            {"operacion": "estado_servidor", "extra": 1},
        ]
        with socket.create_connection(("127.0.0.1", self.puerto), timeout=3) as conexion:
            with conexion.makefile("rb") as lector:
                for solicitud in solicitudes:
                    enviar(conexion, solicitud)
                    respuesta = recibir(lector)
                    self.assertFalse(respuesta["ok"])
                    self.assertIn(respuesta["codigo"], {"SOLICITUD_INVALIDA", "PARAMETROS_INVALIDOS"})
        self.detalles["solicitudes_rechazadas"] = len(solicitudes)

    def test_08_tramas_invalidas(self):
        casos = [(b"{mal}\n", "JSON_INVALIDO"), (b"\xff\n", "JSON_INVALIDO"),
                 (b"[]\n", "SOLICITUD_INVALIDA"), (b'{"id": NaN}\n', "JSON_INVALIDO"),
                 (b"x" * (MAX_MENSAJE + 1) + b"\n", "MENSAJE_DEMASIADO_GRANDE"),
                 (b'{"operacion":"estado_servidor"}', "MENSAJE_INCOMPLETO")]
        for trama, codigo in casos:
            with self.subTest(codigo=codigo):
                with socket.create_connection(("127.0.0.1", self.puerto), timeout=3) as conexion:
                    conexion.sendall(trama)
                    conexion.shutdown(socket.SHUT_WR)
                    with conexion.makefile("rb") as lector:
                        respuesta = recibir(lector)
                    self.assertFalse(respuesta["ok"])
                    self.assertEqual(respuesta["codigo"], codigo)
        self.detalles["tramas_rechazadas"] = len(casos)

    def test_09_fragmentacion_y_agrupacion_tcp(self):
        with socket.create_connection(("127.0.0.1", self.puerto), timeout=3) as conexion:
            with conexion.makefile("rb") as lector:
                conexion.sendall(b'{"operacion":"consul')
                conexion.sendall(b'tar_libro","id":3}\n{"operacion":"estado_servidor"}\n')
                self.assertEqual(recibir(lector)["libro"]["id"], 3)
                self.assertEqual(recibir(lector)["estado"], "activo")
        self.detalles["respuestas_recibidas_en_orden"] = 2

    def test_10_servidor_apagado(self):
        with ClienteBiblioteca(puerto=self.puerto) as cliente:
            self.servidor.cerrar()
            self.hilo.join(12)
            with self.assertRaises(ErrorComunicacion):
                cliente.consultar_libros()
        with self.assertRaises(ErrorComunicacion):
            ClienteBiblioteca(puerto=self.puerto, timeout=0.3).conectar()
        self.detalles["resultado"] = "RPC interrumpida y conexión nueva rechazada"

    def test_11_cliente_rechaza_respuestas_invalidas(self):
        # Servidor TCP mínimo defectuoso: prueba al cliente sin sustituir sockets.
        for trama in [b"no-json\n", b'{"ok":true}\n',
                      b'{"ok":true,"mensaje":"x","libros":[{}]}\n',
                      b'{"ok":false,"mensaje":"x"}\n', b""]:
            with self.subTest(trama=trama), socket.socket() as escucha:
                escucha.bind(("127.0.0.1", 0))
                escucha.listen(1)
                escucha.settimeout(3)

                def responder():
                    with escucha.accept()[0] as conexion:
                        conexion.recv(1024)
                        if trama:
                            conexion.sendall(trama)

                hilo = threading.Thread(target=responder)
                hilo.start()
                try:
                    with ClienteBiblioteca(puerto=escucha.getsockname()[1]) as cliente:
                        with self.assertRaises(ErrorComunicacion):
                            cliente.consultar_libros()
                finally:
                    hilo.join(4)
                    self.assertFalse(hilo.is_alive())
        self.detalles["respuestas_invalidas_rechazadas"] = 5

    def test_12_timeout_cliente(self):
        with socket.socket() as escucha:
            escucha.bind(("127.0.0.1", 0))
            escucha.listen(1)
            escucha.settimeout(3)
            terminar = threading.Event()

            def no_responder():
                with escucha.accept()[0] as conexion:
                    conexion.recv(1024)
                    terminar.wait(3)

            hilo = threading.Thread(target=no_responder)
            hilo.start()
            try:
                with ClienteBiblioteca(puerto=escucha.getsockname()[1], timeout=0.2) as cliente:
                    with self.assertRaises(ErrorComunicacion):
                        cliente.consultar_libros()
            finally:
                terminar.set()
                hilo.join(4)
                self.assertFalse(hilo.is_alive())
        self.detalles["resultado"] = "El cliente detectó el timeout sin reintentar"

    def test_13_menu_interactivo(self):
        """Ejecuta cliente.py como proceso y recorre el menú con entradas reales."""
        ruta = Path(__file__).resolve().parent
        proceso = subprocess.run(
            [sys.executable, str(ruta / "cliente.py"), "--puerto", str(self.puerto)],
            input="9\n1\n2\ntexto\n2\n9999\n3\n3\n3\n3\n4\n5\n",
            text=True, capture_output=True, encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=15, cwd=ruta)
        self.assertEqual(proceso.returncode, 0, proceso.stderr)
        for texto in ["Ingrese una opción del 1 al 5", "El ID debe ser un entero positivo",
                      "LIBRO_NO_ENCONTRADO", "Reserva realizada correctamente",
                      "SIN_EJEMPLARES", "Estado: activo"]:
            self.assertIn(texto, proceso.stdout)
        self.detalles.update(codigo_salida=proceso.returncode, salida=proceso.stdout,
                             errores=proceso.stderr)


class ResultadoRegistrado(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.registros = []

    def startTest(self, test):
        test._inicio_prueba = time.monotonic()
        super().startTest(test)

    def stopTest(self, test):
        errores = [texto for caso, texto in self.failures + self.errors if caso is test]
        errores += [texto for caso, texto in self.failures + self.errors
                    if getattr(caso, "test_case", None) is test]
        self.registros.append({"prueba": test.id(), "ok": not errores,
                               "duracion_segundos": round(time.monotonic() - test._inicio_prueba, 3),
                               "detalles": test.detalles, "errores": errores})
        super().stopTest(test)


def main():
    logging.basicConfig(level=logging.WARNING)
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PruebasBiblioteca)
    resultado = unittest.TextTestRunner(stream=stream, verbosity=2,
                                       resultclass=ResultadoRegistrado).run(suite)
    texto = stream.getvalue()
    print(texto)
    carpeta = Path(__file__).resolve().parent / "evidencias"
    carpeta.mkdir(exist_ok=True)
    reporte = {"fecha_utc": datetime.now(timezone.utc).isoformat(),
               "transporte": "Sockets TCP reales en 127.0.0.1, puertos efímeros",
               "concurrencia": "Tres procesos cliente con spawn y barrera de sincronización",
               "pruebas_ejecutadas": resultado.testsRun, "exitoso": resultado.wasSuccessful(),
               "resultados": resultado.registros}
    (carpeta / "resultados_pruebas.json").write_text(
        json.dumps(reporte, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (carpeta / "resultados_pruebas.txt").write_text(texto, encoding="utf-8")
    return 0 if resultado.wasSuccessful() else 1


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
