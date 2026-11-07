# Parte D. Pruebas de concurrencia y errores

## Cómo reproducir

Ejecuta `python pruebas.py` desde la raíz del proyecto. No necesitas arrancar
manualmente el servidor ni elegir puertos. La suite crea un servidor real en
`127.0.0.1` con puerto efímero por caso. Al finalizar cierra conexiones, espera los
hilos y verifica que no queden activos.

Los casos 1, 2 y 6 utilizan `multiprocessing` con `spawn`: hay tres procesos cliente
distintos y un servidor con un hilo por conexión. Una primera RPC confirma que
cada conexión ya fue aceptada. Una barrera de tres participantes libera juntos a
los clientes. El sistema operativo decide el orden de ejecución posterior; no se
supone qué cliente gana la reserva. Los PID se guardan y se comprueba que sean distintos.

## Casos y verificaciones

| Prueba | Acción real | Aserción que debe cumplirse |
| --- | --- | --- |
| 01. Consultas simultáneas | Tres procesos consultan el catálogo tras una barrera | Tres respuestas exitosas con los mismos cinco libros |
| 02. Último ejemplar | Dos procesos reservan ID 3; un tercero consulta estado | Un éxito, un `SIN_EJEMPLARES`, tres conexiones atendidas y disponibilidad final 0 |
| 03. ID inexistente | Consultar y reservar ID 9999 | Ambas RPC devuelven `LIBRO_NO_ENCONTRADO` |
| 04. Desconexión antes de leer | Un socket envía una reserva y cierra sin llamar a recibir | Otro cliente observa disponibilidad 0 y puede consultar estado |
| 05. Operación desconocida | Enviar `borrar_catalogo`; luego consultar en la misma conexión | `OPERACION_DESCONOCIDA`; la conexión sigue utilizable |
| 06. Reservas repetidas | Tres procesos realizan 10 reservas cada uno sobre un único ejemplar | Un éxito, 29 errores `SIN_EJEMPLARES`, ningún libro con cantidad negativa |
| 07. Parámetros incorrectos | Diez solicitudes con campos faltantes, extra o ID inválido | Todas rechazadas con error de validación |
| 08. Tramas incorrectas | JSON inválido, UTF-8 inválido, lista, NaN, exceso de tamaño y mensaje incompleto | Códigos de protocolo correspondientes |
| 09. Flujo TCP | Enviar una solicitud fragmentada y otra agrupada en el mismo flujo | Dos respuestas completas y en orden |
| 10. Apagado | Detener el servidor conectado e intentar una RPC y una conexión nueva | Ambos fallos se exponen como `ErrorComunicacion` |
| 11. Respuestas defectuosas | Servidor TCP mínimo devuelve cinco respuestas defectuosas, incluido EOF | El cliente las rechaza como errores de comunicación |
| 12. Timeout | Un servidor TCP acepta y recibe pero no responde | El cliente agota la espera y no reintenta |
| 13. Menú | Ejecutar `cliente.py` como subproceso con entradas de consola | Valida opciones e ID, muestra catálogo, reserva, agotamiento, estado y sale con código 0 |

Los servidores mínimos de los casos 11 y 12 sirven solo para provocar fallos en
el cliente; utilizan sockets reales. Las operaciones del catálogo y las pruebas
concurrentes se ejecutan contra `ServidorBiblioteca`, sin sustituirlo por mocks.

## Resultados observados

Última ejecución verificada: **6 de noviembre de 2026, 20:51:16 (America/Guayaquil)**,
equivalente a `2026-11-07T01:51:16.959853+00:00` en el registro UTC.
Resultado: **13 pruebas aprobadas en 6.422 segundos**, resumen `OK` y código
de salida 0. La prueba 02 obtuvo un éxito y un rechazo; la prueba 06 obtuvo un
éxito y 29 rechazos. Se verificó disponibilidad final 0 para el libro 3 y ausencia
de cantidades negativas en todo el catálogo.

La evidencia de la última ejecución se encuentra en:

- [Registro de unittest](../evidencias/resultados_pruebas.txt).
- [Resultados, respuestas y PID](../evidencias/resultados_pruebas.json).

El campo `exitoso` del JSON y el resumen del TXT indican si pasó la ejecución.
Los detalles de las pruebas 02 y 06 registran el resultado de la disputa y los
30 intentos; no dependen solo de textos impresos: las aserciones comparan éxitos,
códigos y el catálogo consultado después de las reservas.

La ejecución se realizó en un equipo Windows con Python 3.12 y TCP loopback.
El primer intento aislado encontró `WinError 10013` al conectar; se repitió con
permiso para TCP local fuera del aislamiento. Los archivos de resultados se
actualizan con cada ejecución y deben conservarse juntos para la entrega.

## Qué demuestra el Lock

Sin exclusión mutua, comprobar `disponibles > 0` y luego restar son dos pasos que
podrían intercalarse con los de otro hilo. El bloque `with self.lock` de
`ServidorBiblioteca.procesar` incluye lectura, comprobación, decremento y copia de
la respuesta. El siguiente hilo observa el valor actualizado. Las lecturas usan
el mismo Lock y obtienen una instantánea coherente. La serialización y la espera
de red ocurren fuera de ese bloque para reducir la contención.

## Alcance de las evidencias

No se probó una red física entre equipos ni una caída real de un enlace. Sí se
probaron conexiones reales, cierre de sockets, falta de respuesta, apagado del
servicio y concurrencia de procesos. En la prueba 04 el cliente no lee la respuesta;
eso no implica que el servidor no pudiera enviarla al búfer TCP. Se verifica que
la solicitud fue procesada y que el servidor continúa disponible.

Las capturas deben tomarse en las terminales siguiendo
[evidencias/LEEME.md](../evidencias/LEEME.md). El JSON y TXT generados son registros
automáticos; no reemplazan las capturas que solicite el profesor.
