# Partes C y E. API y operaciones RPC

## Transporte y contrato

- TCP IPv4; servidor predeterminado `127.0.0.1:5000`.
- Cada mensaje es **un objeto JSON UTF-8 seguido de `\n`**, hasta 65536 bytes.
- Las solicitudes pueden repetirse en una conexión; no se envían solicitudes
  simultáneas por el mismo cliente. Las respuestas conservan el orden.
- `operacion` es obligatorio y de tipo texto. `id` es entero positivo (no booleano).
  Los campos permitidos deben coincidir exactamente con los de la operación.
- Todo resultado incluye `ok` booleano y `mensaje` descriptivo. Un error incluye
  además `codigo` estable; el cliente toma decisiones por el código, no por el texto.
- El cliente valida el objeto de respuesta y los campos del resultado. Los fallos
  de red o protocolo levantan `ErrorComunicacion`; los errores de negocio se devuelven
  como diccionarios con `ok: false`.

Los siguientes JSON son **ejemplos del contrato**, no resultados de pruebas.

Solicitud:

```json
{"operacion":"reservar_libro","id":1}
```

Respuesta exitosa (si quedaban dos ejemplares):

```json
{
  "ok": true,
  "mensaje": "Reserva realizada correctamente.",
  "libro": {"id": 1, "titulo": "Sistemas distribuidos", "autor": "Andrew S. Tanenbaum", "disponibles": 1},
  "disponibles": 1
}
```

Respuesta de error:

```json
{"ok":false,"codigo":"SIN_EJEMPLARES","mensaje":"No quedan ejemplares disponibles."}
```

## Tabla de operaciones

En todas las filas se omiten `ok: true` y `mensaje` de la columna de éxito por brevedad.

| Operación / función cliente | Entrada JSON | Respuesta exitosa adicional | Posibles errores |
| --- | --- | --- | --- |
| `consultar_libros()` | `{"operacion":"consultar_libros"}` | `libros`: lista de los cinco libros con `id`, `titulo`, `autor`, `disponibles` | `PARAMETROS_INVALIDOS`, errores comunes |
| `consultar_libro(id)` | `{"operacion":"consultar_libro","id":3}` | `libro`: objeto con los cuatro campos | `LIBRO_NO_ENCONTRADO`, `PARAMETROS_INVALIDOS`, errores comunes |
| `reservar_libro(id)` | `{"operacion":"reservar_libro","id":3}` | `libro`: copia actualizada, `disponibles`: nuevo entero no negativo | `LIBRO_NO_ENCONTRADO`, `SIN_EJEMPLARES`, `PARAMETROS_INVALIDOS`, errores comunes |
| `estado_servidor()` | `{"operacion":"estado_servidor"}` | `estado: "activo"`, `clientes_atendidos`, `clientes_activos`, `segundos_activo` | `PARAMETROS_INVALIDOS`, errores comunes |

`clientes_atendidos` cuenta conexiones aceptadas desde el arranque, incluida la que
consulta. No cuenta personas distintas ni solicitudes RPC. Reconectar incrementa
el contador. `clientes_activos` es el número de conexiones registradas al tomar la
instantánea y puede incluir brevemente un cliente que acaba de cerrar mientras su
hilo termina. `segundos_activo` usa un reloj monotónico.

## Errores comunes y cierre de conexión

| Código o fallo | Causa | Comportamiento |
| --- | --- | --- |
| `JSON_INVALIDO` | JSON mal formado, UTF-8 inválido o constantes NaN/Infinity | Respuesta de error y cierre |
| `SOLICITUD_INVALIDA` | JSON que no es objeto o falta operación de texto | No objeto: cierre; operación inválida en objeto: permite siguiente RPC |
| `PARAMETROS_INVALIDOS` | ID ausente/incorrecto, campo faltante o campo extra | Respuesta de error; conexión utilizable |
| `OPERACION_DESCONOCIDA` | Nombre de operación no registrado | Respuesta de error; conexión utilizable |
| `MENSAJE_DEMASIADO_GRANDE` | Trama de más de 65536 bytes | Intenta responder y cierra; no consume trama sin límite |
| `MENSAJE_INCOMPLETO` | Fin de flujo antes del salto de línea | Intenta responder y cierra |
| `ERROR_INTERNO` | Excepción imprevista del servidor | Registra el detalle local, intenta responder y cierra |
| Timeout, EOF, conexión rechazada o reiniciada | Fallo de red, apagado o inactividad | Puede no existir respuesta JSON; cliente levanta `ErrorComunicacion` |

No se promete entregar un error si la red ya falló. Un `ok: false` recibido es una
respuesta remota; un timeout no permite concluir si el servidor ejecutó la reserva.

## Relación entre sockets, RPC y API

El **socket TCP** transporta los bytes entre procesos. El protocolo JSON define
las fronteras y la representación de los mensajes. La capa **RPC** traduce una
llamada Python como `cliente.reservar_libro(3)` a una solicitud y espera su respuesta.
La **API** es el contrato público: cuatro operaciones, parámetros, resultados y
errores. El usuario de la API no necesita conocer el diccionario interno ni los
Locks. Se trata de RPC sencillo propio, no de una implementación del estándar JSON-RPC.

## Comportamiento ante fallos

1. **Apagado:** caen las conexiones; no hay servicio hasta reiniciar. El catálogo
   y los contadores en memoria se pierden; el arranque restaura los valores iniciales.
2. **Pérdida de red:** puede detectarse por EOF, error de socket o timeout de 10 s.
   Una respuesta perdida deja el resultado de una reserva incierto. No hay reintento
   automático ni garantía de exactamente una vez.
3. **Reservas concurrentes:** los hilos se serializan al entrar en la sección
   crítica. Cada éxito reduce una unidad; cuando se llega a cero, se rechazan las
   restantes solicitudes. El orden de llegada o de adquisición del Lock no garantiza
   prioridad justa entre clientes.
4. **Información incorrecta:** se rechaza antes de modificar el catálogo. El cliente
   interactivo valida opciones e IDs, y el servidor vuelve a validar porque no
   puede confiar en que todos los clientes usen el menú oficial.
