# Biblioteca distribuida

Sistema de biblioteca universitaria cliente-servidor en Python. Permite consultar
y reservar libros mediante sockets TCP, mensajes JSON y operaciones RPC, con
atención concurrente y sincronización de reservas.

## Requisitos

- Python 3.10 o superior. Solo utiliza la biblioteca estándar; no requiere instalar paquetes.
- Una terminal para el servidor y una terminal independiente por cliente.
- Visual Studio Code es opcional para editar y ejecutar el proyecto.

Ejecuta los comandos desde la carpeta del proyecto y comprueba el intérprete:

```bat
cd /d C:\Users\Ariel\Documents\biblioteca_distribuida
python --version
```

El comando `cd /d` corresponde a CMD. En PowerShell usa
`cd C:\Users\Ariel\Documents\biblioteca_distribuida`.

Si el alias `python` de Windows no funciona, puedes utilizar un intérprete real
instalado. En este equipo también está disponible el siguiente; en **cada ventana
de CMD**, define la variable y reemplaza `python` en los comandos posteriores por
`"%PYTHON_BIBLIOTECA%"`:

```bat
set "PYTHON_BIBLIOTECA=C:\Program Files\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1105-1297-0_26.1105.1297.0_x64__3k8sg7r9htsxt\dependencies\python\python.exe"
"%PYTHON_BIBLIOTECA%" --version
```

Esta ruta puede cambiar al actualizar el runtime; también puedes usar tu propia
instalación de Python 3.10 o superior.

## Iniciar el servidor

```bat
python servidor.py
```

Escucha por defecto en `127.0.0.1:5000`. Mantén abierta la terminal.
Para cambiar el puerto: `python servidor.py --puerto 5001`.
Detén el servidor con `Ctrl+C`. Al iniciarlo de nuevo se restaura el catálogo inicial.

## Ejecutar los clientes

En otra terminal, desde la misma carpeta:

```bat
python cliente.py
```

Para ejecutar tres clientes, repite el comando en tres terminales independientes.
El menú permite consultar libros, reservar y consultar el estado del servidor.
Selecciona `5` para salir. Tras 120 segundos de inactividad, vuelve a iniciar el cliente.

Si cambiaste el puerto: `python cliente.py --puerto 5001`.
Para conectar desde otra máquina, inicia el servidor con
`python servidor.py --host 0.0.0.0` y los clientes con
`python cliente.py --host IP_DEL_SERVIDOR`; la red debe permitir el puerto TCP elegido.

## Ejecutar las pruebas

```bat
python pruebas.py
```

Ejecuta 13 pruebas de comunicación, concurrencia y errores. Crea sus propios
servidores en puertos libres; no necesita un servidor iniciado manualmente.
Guarda los resultados en `evidencias/resultados_pruebas.txt` y
`evidencias/resultados_pruebas.json`, reemplazando los resultados anteriores.

Para ejecutar las mismas pruebas sin sobrescribir las evidencias:

```bat
python -m unittest pruebas -v
```
