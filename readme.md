# Práctica 2: Sistema IoT Domótico con Protocolo MQTT

Este proyecto implementa un sistema IoT para la gestión inteligente de una habitación mediante el protocolo **MQTT** y el broker público **HiveMQ** (`broker.hivemq.com`).

El sistema simula sensores virtuales, actuadores y un motor de reglas domóticas que automatiza el funcionamiento de una bombilla y una persiana. Además, incorpora un controlador central que monitoriza la actividad del sistema y almacena localmente los datos de telemetría y los eventos recibidos.

También incluye varios scripts avanzados para demostrar el funcionamiento de las principales características de MQTT: mensajes retenidos (*Retained Messages*), testamento (*Last Will and Testament*), Keepalive, niveles de calidad de servicio (QoS), sesiones persistentes y caducidad de mensajes en MQTT 5.

---

## 1.- Estructura del Proyecto

La estructura de carpetas y archivos del proyecto es la siguiente:

```text
Practica_2_IoT/
├── config.py                  # Configuración del broker, tópicos y umbrales
├── sensor.py                  # Emulador de sensores virtuales
├── actuador.py                # Simulador de actuadores (bombilla y persiana)
├── reglas.py                  # Motor de reglas domóticas (R1-R5)
├── controlador.py              # Monitor central y registro de datos CSV
├── ejecutar_todo.py            # Lanzador automatizado de los procesos
│
├── avanzado_retained.py        # Demostración de mensajes retenidos
├── avanzado_lwt.py             # Demostración de LWT y Keepalive
├── avanzado_qos_latencia.py    # Comparación de latencia entre QoS 0, 1 y 2
├── avanzado_sesion_per.py      # Demostración de sesiones persistentes y expiración
│
├── data/                       # Datos de entrada de los sensores
│   ├── datos_luz.csv
│   ├── datos_humedad.csv
│   ├── datos_temperatura.csv
│   ├── datos_presencia.csv
│   └── datos_sensores.csv      # Fichero unificado opcional
│
└── output/                     # Datos generados durante la ejecución
    ├── registro_sensores.csv
    └── events/
        ├── presencia.csv
        ├── temperatura.csv
        ├── humedad.csv
        └── luz.csv
```

Los directorios y archivos de salida se generan automáticamente cuando se ejecuta el controlador.

---

## 2.- Requisitos Previos e Instalación

### Requisitos

- Python 3.8 o superior.
- Conexión activa a Internet para comunicarse con el broker público HiveMQ.
- Archivos CSV con los datos de entrada de los sensores.

### Instalación de dependencias

El proyecto utiliza la biblioteca Paho MQTT para establecer las conexiones y realizar las comunicaciones mediante MQTT.

Instala la dependencia con el siguiente comando:

```bash
pip install paho-mqtt
```

---

## 3.- Guía de Ejecución

Existen dos modalidades principales para ejecutar y probar el sistema. Se recomienda utilizar la primera, ya que permite visualizar por separado la actividad de los sensores, el motor de reglas y el controlador.

### Opción A: Modo Recomendado (Ejecución Separada)

Para facilitar la visualización de los mensajes MQTT y las trazas generadas por cada componente, se recomienda utilizar tres terminales independientes.

**Terminal 1: Sensores virtuales**

El lanzador inicia automáticamente los cuatro sensores, sin arrancar el resto de servicios:

```bash
python ejecutar_todo.py --solo-sensores
```

También se puede especificar el grupo y el periodo de muestreo:

```bash
python ejecutar_todo.py g99 --solo-sensores --periodo 2.0
```

**Terminal 2: Motor de reglas domóticas (`reglas.py`)**

Recibe las lecturas de los sensores, evalúa las reglas domóticas y publica las órdenes correspondientes a los actuadores:

```bash
python reglas.py g99
```

**Terminal 3: Monitor y registro CSV (`controlador.py`)**

Escucha la actividad del grupo, muestra la información de la habitación y almacena los datos recibidos en archivos CSV:

```bash
python controlador.py g99
```

**Terminales adicionales: Actuadores**

Si se desea visualizar también la actividad individual de los actuadores o interactuar manualmente con ellos, se pueden abrir dos terminales adicionales.

**Actuador de bombilla:**

```bash
python actuador.py --tipo bombilla --grupo g99
```

Órdenes disponibles desde la consola:

- `ON`: encender la bombilla.
- `OFF`: apagar la bombilla.
- `q`: finalizar el programa.

**Actuador de persiana:**

```bash
python actuador.py --tipo persiana --grupo g99
```

Órdenes disponibles desde la consola:

- `ABIERTA`: abrir la persiana.
- `CERRADA`: cerrar la persiana.
- `q`: finalizar el programa.

Esta distribución permite observar por separado las publicaciones de los sensores, las decisiones del motor de reglas, las actualizaciones del controlador y las respuestas de los actuadores.

### Opción B: Modo Automatizado Completo

También es posible iniciar todos los componentes desde una única terminal mediante el lanzador:

```bash
python ejecutar_todo.py
```

El lanzador inicia automáticamente:

- El controlador central.
- El motor de reglas domóticas.
- El actuador de la bombilla.
- El actuador de la persiana.
- Los cuatro sensores virtuales.

### Parámetros adicionales del lanzador

**Modificar el periodo de muestreo:**

Permite establecer el intervalo entre las publicaciones de los sensores. Por ejemplo, para publicar cada segundo:

```bash
python ejecutar_todo.py g99 --periodo 1.0
```

**Ejecutar únicamente los servicios:**

Inicia el controlador, el motor de reglas y los dos actuadores, sin arrancar los sensores:

```bash
python ejecutar_todo.py g99 --solo-servicios
```

**Ejecutar únicamente los sensores:**

```bash
python ejecutar_todo.py g99 --solo-sensores
```

**Ejecutar sin el monitor:**

Permite iniciar el resto de componentes sin arrancar el controlador central:

```bash
python ejecutar_todo.py g99 --sin-monitor
```

### Detener el sistema

Pulsa `Ctrl + C` en cada terminal donde se esté ejecutando un componente. En el caso del lanzador, este se encarga de