# Práctica 5: Comunicación en Sistemas Distribuidos

Biblioteca universitaria cliente-servidor con Python 3, sockets TCP, JSON por línea,
RPC, un hilo por conexión y `threading.Lock`. Solo utiliza la biblioteca estándar.

## Archivos

```text
biblioteca_distribuida/
  servidor.py                  Servidor TCP, catálogo, sincronización y despacho RPC
  cliente.py                   Cliente RPC reutilizable y menú interactivo
  protocolo.py                 Codificación, delimitación y validación del transporte
  pruebas.py                   Pruebas automáticas con conexiones y procesos reales
  README.md                    Guía de ejecución
  documentacion/
    diseno.md                  Arquitectura, flujo y preguntas de la parte A
    api.md                     Contrato de mensajes y tabla de operaciones
    informe.md                 Informe y cinco respuestas de reflexión
    pruebas.md                 Método de pruebas y resultados registrados
  evidencias/
    LEEME.md                   Capturas que debes obtener para la entrega
    resultados_pruebas.txt     Salida de la última ejecución automática
    resultados_pruebas.json    Respuestas, PID, aserciones y resultados reales
  .vscode/launch.json          Configuraciones opcionales para depurar en VS Code
```

La carpeta abierta ya es `biblioteca_distribuida`; no hace falta crear otra dentro.

## 1. Preparar Python y VS Code

Requiere Python **3.10 o superior**. Abre esta carpeta en VS Code, instala su extensión
Python de Microsoft y selecciona el intérprete con **Python: Select Interpreter**.
No se necesita `pip install` ni un archivo de dependencias.

En cada terminal PowerShell sitúate en la carpeta:

```powershell
cd C:\Users\Ariel\Documents\biblioteca_distribuida
python --version
```

Los ejemplos siguientes suponen que `python` apunta al intérprete instalado.
Si utilizas el lanzador de Windows, puedes reemplazar `python` por `py -3`.
Si Windows abre Microsoft Store o rechaza `python`, selecciona un intérprete real
en VS Code y usa su ruta completa: `& 'C:\ruta\python.exe' servidor.py`.
Cambiar el intérprete de VS Code no siempre cambia el comando `python` del PATH.

En este equipo el alias `python` no pudo ejecutarse. Para las pruebas se usó este
intérprete real, que también puedes seleccionar en VS Code. Como alternativa,
define esta variable **en cada terminal** y usa los comandos que siguen:

```powershell
$pythonBiblioteca = 'C:\Program Files\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1105-1297-0_26.1105.1297.0_x64__3k8sg7r9htsxt\dependencies\python\python.exe'
& $pythonBiblioteca --version
# En la terminal del servidor:
& $pythonBiblioteca servidor.py
# En cada una de las tres terminales cliente:
& $pythonBiblioteca cliente.py
# En otra terminal para las pruebas:
& $pythonBiblioteca pruebas.py
```

La ruta pertenece al runtime instalado actualmente y puede cambiar al actualizar
Codex. Un Python 3.10+ instalado por separado funciona sin depender de esa ruta.

## 2. Iniciar el servidor (terminal 1)

```powershell
python servidor.py
```

Debe indicar que escucha en `127.0.0.1:5000`. Deja esta terminal abierta.
Para otro puerto: `python servidor.py --puerto 5001`; pasa también `--puerto 5001`
a cada cliente. Si el puerto está ocupado, cierra el servidor previo o elige otro.

## 3. Abrir tres clientes (terminales 2, 3 y 4)

En VS Code usa **Terminal > New Terminal** tres veces. Ejecuta en cada una:

```powershell
python cliente.py
```

Son tres procesos distintos conectados al mismo servidor. Cada uno muestra:

```text
SISTEMA DE BIBLIOTECA UNIVERSITARIA
1. Consultar todos los libros
2. Consultar libro por ID
3. Reservar un libro
4. Consultar estado del servidor
5. Salir
```

El servidor cierra conexiones tras 120 segundos sin datos: realiza las acciones
seguidas o vuelve a iniciar el cliente cuando termine la conexión. El cliente
detecta el cierre al enviar la siguiente RPC y sale con un mensaje descriptivo.
Este límite evita mantener indefinidamente hilos de clientes inactivos.

## 4. Demostración manual de consultas y reservas

1. En los clientes A y B elige `1`: ambos deben mostrar el mismo catálogo.
2. En C elige `4`: en una sesión nueva, con los tres conectados y sin inactividad,
   debe mostrar tres clientes activos y al menos tres conexiones atendidas.
3. En A elige `2` e ID `3`. Su disponibilidad inicial es **1**.
4. En A y B elige `3` e ID `3`. Solo la primera solicitud que adquiera el Lock
   tendrá éxito; la otra responderá `SIN_EJEMPLARES`.
5. En C consulta el ID `3`: la disponibilidad debe ser **0**. Más reservas fallan
   y nunca producen cantidades negativas.
6. Consulta el ID `9999`: debe responder `LIBRO_NO_ENCONTRADO`.
7. Escribe una opción fuera de 1–5 o un ID no numérico: el menú debe explicar el error.
8. Elige `5` para salir de cada cliente. Detén el servidor con `Ctrl+C`.

Las acciones manuales no garantizan simultaneidad exacta. La suite automática
coordina tres procesos con una barrera para probar la concurrencia de forma reproducible.
Reiniciar el servidor restaura los cinco libros y todas sus disponibilidades iniciales.

## 5. Ejecutar las pruebas

En una terminal adicional:

```powershell
python pruebas.py
```

No necesita un servidor iniciado: crea servidores aislados en puertos libres
asignados por el sistema operativo. No consume el catálogo de tu demostración.
Ejecuta 13 pruebas de integración, incluidos los cinco casos de la práctica,
tres procesos paralelos y 30 intentos de reserva sobre el último ejemplar.
Un fallo produce un código de salida 1 y un informe con su error.

Los resultados verificables se escriben en `evidencias/resultados_pruebas.txt` y
`evidencias/resultados_pruebas.json`. Cada nueva ejecución reemplaza estos dos
archivos. El JSON contiene respuestas reales y PID de los clientes.
También puedes usar `python -m unittest pruebas -v`, aunque esa vía no genera los informes.

## 6. Uso como funciones RPC

Con el servidor activo, este código puede ejecutarse desde otro archivo Python:

```python
from cliente import ClienteBiblioteca, ErrorComunicacion

try:
    with ClienteBiblioteca("127.0.0.1", 5000) as cliente:
        print(cliente.consultar_libros())
        print(cliente.consultar_libro(3))
        print(cliente.reservar_libro(3))
        print(cliente.estado_servidor())
except ErrorComunicacion as error:
    print(error)
```

Un error de negocio devuelve `ok: false`; un fallo de transporte levanta
`ErrorComunicacion`. No se reintentan reservas automáticamente: una respuesta
perdida no demuestra que la reserva haya fallado.

## 7. Dos o más máquinas

En la máquina servidor: `python servidor.py --host 0.0.0.0 --puerto 5000`.
En cada cliente: `python cliente.py --host DIRECCION_IP_DEL_SERVIDOR --puerto 5000`.
Usa la IP real de la interfaz del servidor, no `0.0.0.0` como destino.
Las máquinas deben tener conectividad IP y el firewall debe permitir TCP entrante
al puerto elegido en el servidor. Esta práctica no incluye autenticación ni TLS;
su alcance es una demostración en una red de laboratorio.

## Documentación y entrega

Consulta [diseño](documentacion/diseno.md), [API](documentacion/api.md),
[informe académico](documentacion/informe.md) y [pruebas](documentacion/pruebas.md).
Las capturas que debes tomar están enumeradas en [evidencias/LEEME.md](evidencias/LEEME.md).
Los informes automáticos son evidencias reales de ejecución; las capturas deben
corresponder a tus propias terminales y no se han generado imágenes simuladas.
