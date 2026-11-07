# Evidencias para entregar

`resultados_pruebas.txt` y `resultados_pruebas.json` los escribe `python pruebas.py`.
Son registros reales, no capturas. El JSON incluye fecha UTC, PID, respuestas y
resultados por prueba. No edites sus valores para preparar la entrega.

Toma estas capturas de tus terminales y guárdalas en esta carpeta:

1. `01_servidor_y_tres_clientes.png`: servidor escuchando y tres procesos cliente
   abiertos; consulta el estado con opción 4 para mostrar conexiones activas.
2. `02_consultas.png`: al menos dos clientes mostrando el mismo catálogo.
3. `03_ultimo_ejemplar.png`: libro 3 inicialmente con 1; una reserva exitosa,
   otra con `SIN_EJEMPLARES` y consulta final con 0. Reinicia antes si lo agotaste.
4. `04_id_inexistente.png`: consulta manual del ID 9999 y error recibido.
5. `05_pruebas_automaticas.png`: ejecución completa de `python pruebas.py`, los
   cinco primeros casos y el resumen final. Si no caben, usa más de una captura.
6. `06_desconexion_y_operacion.png`: abre el JSON de resultados y muestra los
   detalles de `test_04` y `test_05`: reserva sin leer respuesta, servicio posterior
   disponible y rechazo de operación desconocida.
7. `07_concurrencia.png`: muestra los PID y respuestas de `test_02` y el resumen
   de 30 intentos de `test_06` para acreditar procesos reales y ausencia de negativos.

Las capturas manuales prueban la interfaz; la sincronización exacta de la prueba
concurrente la acredita la barrera de tres procesos y sus aserciones automáticas.
No se han creado capturas ficticias. Conserva el código y el JSON junto con las
capturas para que el profesor pueda repetir la ejecución.
