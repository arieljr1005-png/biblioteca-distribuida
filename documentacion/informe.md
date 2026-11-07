# Informe: Práctica 5. Comunicación en Sistemas Distribuidos

## 1. Introducción

Un sistema distribuido coordina procesos independientes mediante mensajes. En
esta práctica se construyó una biblioteca universitaria con un servidor central
y varios clientes capaces de consultar y reservar libros por TCP. La ejecución
en localhost permite estudiar concurrencia y fallos sin requerir varias máquinas;
los clientes siguen siendo procesos independientes y el transporte es de red.

## 2. Objetivos

- Implementar comunicación cliente-servidor con sockets TCP y mensajes JSON.
- Exponer cuatro operaciones como funciones remotas con un contrato de API claro.
- Atender múltiples conexiones mediante hilos y proteger el catálogo compartido.
- Verificar concurrencia, errores de entrada y fallos de comunicación con pruebas reales.
- Explicar las limitaciones del servicio y proponer mejoras de forma fundamentada.

## 3. Diseño de la arquitectura

El [diagrama de arquitectura y flujo](diseno.md) muestra tres procesos cliente,
un socket de escucha, un hilo por conexión y el catálogo compartido. El servidor
es la única autoridad sobre la disponibilidad. Cada cliente conserva su propio
socket y realiza una RPC a la vez. La recepción usa un lector persistente porque
TCP no conserva los límites de las solicitudes.

Un `threading.Lock` protege todas las consultas y modificaciones del catálogo.
La reserva busca el libro, comprueba la disponibilidad y decrementa una unidad
dentro de la misma sección crítica. La respuesta contiene una copia del libro,
así que su serialización y el envío de red no retienen ese Lock. Otro Lock protege
los contadores y las conexiones activas.

## 4. Tecnologías utilizadas

Python 3 y su biblioteca estándar: `socket` para TCP, `threading` para concurrencia
y sincronización, `json` para mensajes, `argparse` para configuración y `logging`
para diagnósticos. Las pruebas usan `unittest`, `multiprocessing`, `subprocess`
y primitivas de sincronización. VS Code permite abrir terminales independientes
y depurar con las configuraciones opcionales incluidas.

No hay frameworks ni dependencias externas para ejecutar el proyecto. El entorno
de verificación utilizó Python 3.12 del runtime disponible en Codex.

## 5. Explicación del funcionamiento

El servidor inicializa cinco libros en memoria y escucha en un host y puerto
configurables, por defecto `127.0.0.1:5000`. Por cada conexión aceptada crea un hilo.
El hilo recibe un objeto JSON terminado en salto de línea, valida operación y
parámetros, ejecuta la función correspondiente y devuelve un objeto de respuesta.
Puede atender varias solicitudes hasta que el cliente cierre o falle la conexión.

El cliente presenta el menú solicitado y valida las entradas antes de invocar
funciones RPC. El servidor realiza validación propia para admitir también clientes
que no utilicen ese menú. Los errores de negocio se comunican mediante códigos;
los fallos de transporte se convierten en `ErrorComunicacion`.

El cliente limita a 10 segundos la espera de conexión/respuesta y el servidor
libera conexiones con 120 segundos de inactividad. Las tramas están limitadas a
65536 bytes. Al apagar el servidor se interrumpen conexiones y se espera la salida
de los hilos. El catálogo desaparece al terminar el proceso.

## 6. Operaciones RPC y API

Se implementaron `consultar_libros()`, `consultar_libro(id)`,
`reservar_libro(id)` y `estado_servidor()`. Su contrato completo está en
[la tabla de API](api.md). Las respuestas incluyen `ok` y `mensaje`; los errores
añaden `codigo`. El estado distingue conexiones atendidas acumuladas de conexiones
actualmente activas.

Los sockets son el transporte; RPC convierte llamadas Python en intercambios de
mensajes; la API define qué operaciones pueden solicitarse y cómo interpretar
resultados. Esta separación permite cambiar la estructura interna del catálogo
sin modificar los parámetros públicos del cliente.

## 7. Pruebas realizadas y resultados

Se ejecutaron pruebas de integración contra sockets TCP reales en localhost.
En los casos de concurrencia se iniciaron tres procesos cliente distintos usando
`spawn`. Cada proceso confirmó su conexión mediante una RPC y esperó una barrera
antes de comenzar la operación evaluada. Cada prueba utiliza un servidor y un
catálogo nuevos para evitar dependencias entre casos.

Los [resultados detallados](pruebas.md) se apoyan en los archivos generados por
la ejecución, [salida de unittest](../evidencias/resultados_pruebas.txt) y
[respuestas JSON](../evidencias/resultados_pruebas.json). La ejecución final del
6 de noviembre de 2026 a las 20:51 (America/Guayaquil) aprobó **13 pruebas en
6.422 segundos**, con código de salida 0 y resumen `OK`. La disputa entre dos
clientes produjo una única reserva y un error `SIN_EJEMPLARES`, con disponibilidad
final 0. Una prueba adicional realizó 30 intentos desde tres procesos: un éxito y
29 rechazos, sin cantidades negativas. Los otros casos verifican ID inexistente,
desconexión sin leer la respuesta, operación desconocida y errores de protocolo.

La prueba de desconexión confirmó un detalle relevante: el servidor puede completar
una reserva aunque el cliente cierre antes de leer su respuesta. Después de ese
cierre otro cliente pudo consultar el libro y el estado del servidor.

No se atribuyen capturas ni pruebas entre máquinas a esta ejecución. Las evidencias
automáticas incluyen PID, respuestas y aserciones; las capturas de las terminales
deben obtenerse siguiendo [la guía de evidencias](../evidencias/LEEME.md).

## 8. Problemas encontrados y soluciones

- **Conexiones bloqueadas por el entorno de ejecución:** la primera ejecución
  dentro del aislamiento produjo `WinError 10013`. Se repitió la suite con permiso
  para usar TCP local fuera del aislamiento; las pruebas pudieron comunicarse.
  Este bloqueo era del entorno y no se resolvió sustituyendo las conexiones por simulaciones.
- **Comando Python de Windows:** `python` apuntaba a un alias de Microsoft Store
  que no era ejecutable. Se utilizó un intérprete Python 3.12 real del runtime
  disponible y se documentó cómo elegir un intérprete en VS Code.
- **Límites de mensajes en TCP:** un `recv` aislado podría contener una parte de
  un JSON o varios JSON. Se utilizó delimitación por línea y un lector persistente.
  La suite verifica fragmentación y agrupación de solicitudes.
- **Carrera sobre la disponibilidad:** comprobar y decrementar por separado
  permitiría reservar dos veces el último ejemplar. Ambas acciones se protegen
  juntas mediante `with self.lock`.
- **Orden de las pruebas concurrentes:** una barrera y una RPC inicial por proceso
  aseguran que los tres sockets estén aceptados antes de iniciar el caso evaluado.
- **Tiempo para operar el menú:** se separó el timeout de respuesta del cliente
  del límite de inactividad del servidor para permitir una demostración manual.

## 9. Limitaciones del sistema

El servidor central es un punto único de fallo. No hay persistencia, replicación,
autenticación, cifrado, cuentas de usuario ni historial de reservas. Un hilo por
cliente consume recursos y no existe un límite global de conexiones activas.
El timeout libera conexiones inactivas, pero no convierte el diseño en un servicio
de producción. El Lock protege hilos de este proceso; no coordinaría varios
servidores con catálogos separados.

La reserva no es idempotente y no se reintenta automáticamente. Consultar la
disponibilidad después de una respuesta perdida no identifica quién reservó un
ejemplar. Las pruebas de concurrencia verifican las ejecuciones observadas; la
garantía del invariante también depende del diseño de la sección crítica.

## 10. Conclusiones

La práctica demuestra comunicación entre procesos, una API remota y sincronización
de estado compartido con herramientas estándar. La delimitación explícita de JSON
resuelve la ausencia de fronteras de mensajes en TCP. El Lock impide aprobar una
reserva cuando ya no hay ejemplares y las pruebas reales permiten verificar tanto
resultados de negocio como fallos de comunicación. La pérdida de una respuesta
evidencia por qué un transporte confiable no equivale a una transacción remota
con garantía de exactamente una vez.

## Preguntas de reflexión

### 1. ¿Por qué usar un hilo por cliente y qué costos introduce?

Simplifica el código bloqueante: cada hilo espera y responde de forma independiente,
sin impedir que otros clientes sean atendidos durante una espera de red. Es adecuado
para esta práctica pequeña y con bastante E/S. Introduce memoria para las pilas,
cambios de contexto, sockets abiertos, coordinación y contención de Locks. Para
miles de conexiones convendría limitar concurrencia o estudiar E/S asíncrona. Los
hilos no garantizan paralelismo de CPU en una implementación habitual de CPython
con GIL, aunque sí permiten concurrencia durante las esperas de E/S.

### 2. ¿Qué pasa al reenviar una reserva sin respuesta? ¿Cómo evitar duplicados?

El servidor puede haber reservado y perdido la conexión antes de entregar la
confirmación. Un reenvío se trata como una nueva reserva y puede consumir otro
ejemplar. Este proyecto no reintenta automáticamente y avisa del resultado incierto.
Una mejora sería agregar un identificador único de solicitud o clave de idempotencia:
el cliente reutiliza la misma clave al reintentar y el servidor devuelve el resultado
guardado sin repetir el descuento. La comprobación de la clave, la reserva y el
registro de su resultado deben ser atómicos. Para sobrevivir a reinicios se necesita
persistir esa información en una transacción, con asociación al cliente, comprobación
de parámetros y una política de conservación. Esta mejora se propone, no está implementada.

### 3. ¿Qué ventajas ofrece una API frente a exponer detalles internos?

Define un contrato pequeño y estable, centraliza validaciones y permite rechazar
operaciones no autorizadas por el contrato. Evita que un cliente cambie directamente
el diccionario o salte la comprobación de disponibilidad. Facilita pruebas,
documentación y futuras implementaciones internas sin acoplar todos los clientes
a la representación del servidor.

### 4. ¿Qué mecanismos agregarías para autenticar y proteger la comunicación?

TLS con verificación del certificado del servidor para cifrado e integridad; para
identificar clientes, certificados mutuos o credenciales/tokens transmitidos dentro
de TLS. Agregaría autorización por operación, gestión segura de secretos, expiración
de sesiones, límites de intentos y registros de auditoría. No se deberían enviar
contraseñas por el TCP en texto plano actual. Son mejoras propuestas fuera del alcance
de esta implementación académica.

### 5. ¿Qué cambiarías para funcionar en varias máquinas?

Para un servidor y clientes remotos basta escuchar en una interfaz accesible,
configurar la IP o DNS del servidor en cada cliente y permitir el puerto TCP en
la red y el firewall. El código ya admite `--host` y `--puerto`; `127.0.0.1` solo
alcanza a la propia máquina. Para varias instancias servidor habría que compartir
un almacenamiento persistente y transaccional: un Lock local no protege otro
proceso ni otra máquina. También estudiaría TLS, autenticación, idempotencia,
descubrimiento del servicio y recuperación ante fallos.
