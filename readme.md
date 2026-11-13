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

**Alternativa: Ejecución individual de los sensores (`sensor.py`)**

También es posible ejecutar cada sensor de forma independiente, sin utilizar el lanzador. Para ello, se utiliza `sensor.py`, indicando el tipo de sensor y, opcionalmente, el periodo de muestreo.

El periodo por defecto es de **2 segundos**, por lo que no es necesario especificarlo si se desea utilizar ese intervalo.

```bash
# Sensor de luz
python sensor.py --tipo luz --grupo g99

# Sensor de humedad
python sensor.py --tipo humedad --grupo g99

# Sensor de temperatura
python sensor.py --tipo temperatura --grupo g99

# Sensor de presencia
python sensor.py --tipo presencia --grupo g99
```

Para modificar el periodo de publicación, se puede utilizar el parámetro `--periodo`. Por ejemplo, para publicar una lectura cada segundo:

```bash
python sensor.py --tipo luz --grupo g99 --periodo 2.0
```

Cada sensor puede ejecutarse en una terminal independiente, permitiendo controlar individualmente su funcionamiento y periodo de publicación.

### Detener el sistema

Pulsa `Ctrl + C` en cada terminal donde se esté ejecutando un componente. En el caso del lanzador, este se encarga de finalizar los procesos hijos de forma ordenada.

---

## 4.- Reglas Domóticas Evaluadas

El motor de reglas (`reglas.py`) analiza los valores recibidos de los sensores y el estado conocido de los actuadores para decidir qué acciones deben ejecutarse.

Se han implementado cinco reglas:

- **R1: Entrada de una persona con poca iluminación.** Cuando la presencia cambia de 0 a 1 y la luz es inferior a 150 lux, se enciende la bombilla.
- **R2: Salida de una persona.** Cuando la presencia cambia de 1 a 0, se apaga la bombilla y se cierra la persiana.
- **R3: Humedad elevada.** Cuando la humedad relativa supera el 70 %, se abre la persiana para favorecer la ventilación.
- **R4: Exceso de luz natural y humedad baja.** Cuando la iluminación supera los 600 lux y la humedad es inferior al 40 %, se cierra la persiana.
- **R5: Presencia activa con poca iluminación.** Si hay una persona en la habitación y la luz baja de 150 lux, se enciende la bombilla, aunque la persona ya estuviera dentro.

Las órdenes generadas por el motor de reglas se publican en los tópicos `set` de los actuadores mediante QoS 1.

Los actuadores reciben estas órdenes, actualizan su estado y publican una confirmación en sus respectivos tópicos `estado`.

---

## 5.- Demostración de Mensajes Retenidos (`avanzado_retained.py`)

Este script permite comprobar el funcionamiento del atributo `retain` de MQTT y las diferencias entre los mensajes retenidos y los mensajes efímeros.

Se publican dos mensajes en tópicos diferentes:

- Un mensaje con `retain=False`, que no queda almacenado en el broker.
- Un mensaje con `retain=True`, cuyo último valor queda almacenado para futuros suscriptores.

Después de desconectar al publicador, un nuevo cliente se suscribe a ambos tópicos para comprobar que recibe el mensaje retenido, pero no el mensaje efímero publicado anteriormente.

**Ejecución:**

```bash
python avanzado_retained.py g99
```

---

## 6.- Demostración de Last Will and Testament (LWT) y Keepalive (`avanzado_lwt.py`)

Este script demuestra el mecanismo **Last Will and Testament (LWT)** y el funcionamiento del parámetro `Keepalive`.

El cliente sensor se conecta al broker y registra un mensaje de testamento (`OFFLINE`). A continuación, publica su estado `ONLINE` y simula una caída inesperada de la conexión.

Un segundo cliente permanece conectado al broker y escucha el tópico del testamento para detectar cuándo HiveMQ publica automáticamente el mensaje `OFFLINE`.

El programa mide el tiempo transcurrido desde la caída simulada hasta la recepción del mensaje LWT.

**Ejecución:**

```bash
python avanzado_lwt.py g99
```

---

## 7.- Comparación de Calidad de Servicio y Latencia (QoS) (`avanzado_qos_latencia.py`)

Este script permite comparar los tres niveles de calidad de servicio de MQTT y observar cómo afectan al tiempo de respuesta de las publicaciones.

Se envían diez mensajes para cada nivel de QoS:

- **QoS 0 – At most once:** el mensaje se envía sin confirmación de entrega.
- **QoS 1 – At least once:** el broker confirma la recepción mediante `PUBACK`. Puede producirse la entrega de mensajes duplicados.
- **QoS 2 – Exactly once:** utiliza un intercambio de cuatro paquetes (`PUBLISH`, `PUBREC`, `PUBREL` y `PUBCOMP`) para garantizar la entrega exactamente una vez dentro del protocolo.

Para cada nivel se calculan las siguientes estadísticas:

- Tiempo medio.
- Tiempo mínimo.
- Tiempo máximo.
- Desviación típica.

En QoS 0 se mide el tiempo de envío local, ya que no existe una confirmación de recepción equivalente a la de los otros niveles. En QoS 1 y QoS 2 se mide el tiempo hasta completar el intercambio de confirmación correspondiente.

**Ejecución:**

```bash
python avanzado_qos_latencia.py g99
```

---

## 8.- Sesiones Persistentes y Caducidad de Mensajes MQTT 5 (`avanzado_sesion_per.py`)

Este script demuestra el funcionamiento de las sesiones persistentes y la caducidad de mensajes mediante MQTT 5.

Se conecta un actuador utilizando una sesión persistente y, posteriormente, se desconecta de forma ordenada. Mientras permanece desconectado, otro cliente publica tres órdenes QoS 1 con distintos tiempos de expiración.

Las órdenes utilizadas son:

| Orden | Prioridad lógica | Caducidad |
|---|---:|---:|
| Orden 1 | 1 | 30 segundos |
| Orden 2 | 2 | 60 segundos |
| Orden 3 | 3 | 3 segundos |

Durante la desconexión del actuador se espera un intervalo de seis segundos. Después, el actuador vuelve a conectarse utilizando el mismo identificador de cliente y recupera su sesión.

El objetivo es comprobar que:

- La sesión persistente permite conservar la suscripción y los mensajes pendientes mientras el cliente está desconectado.
- La Orden 1 y la Orden 2 siguen dentro de su periodo de validez y pueden entregarse al reconectar.
- La Orden 3 ha superado su tiempo de expiración y el broker debe descartarla.

La prioridad indicada es únicamente una clasificación lógica de las órdenes: MQTT no incorpora un mecanismo nativo de prioridad para ordenar automáticamente los mensajes.

**Ejecución:**

```bash
python avanzado_sesion_per.py g99
```

---

## 9.- Almacenamiento y Registro de Datos

El controlador central (`controlador.py`) recibe los mensajes publicados por los sensores y los actuadores y almacena la información en archivos CSV.

Se generan dos tipos de registros:

**Registro general de sensores:**

```text
output/registro_sensores.csv
```

Contiene las lecturas recibidas de los sensores.

**Registros individuales de eventos:**

```text
output/events/
├── presencia.csv
├── temperatura.csv
├── humedad.csv
└── luz.csv
```

Estos archivos permiten consultar y analizar por separado los eventos registrados para cada sensor.

---

## 10.- Arquitectura de Comunicación MQTT

La comunicación entre los componentes se realiza mediante tópicos MQTT organizados por grupo.

La estructura general utiliza el prefijo:

```text
iotlab26/{grupo}/
```

Los principales canales de comunicación son:

| Tópico | Función |
|---|---|
| `sensor/{tipo}` | Publicación de lecturas de los sensores. |
| `actuador/{tipo}/set` | Recepción de órdenes por parte de los actuadores. |
| `actuador/{tipo}/estado` | Publicación del estado actual de los actuadores. |
| `actuador/{tipo}/lwt` | Comunicación del estado de conexión mediante LWT. |
| `sistema/regla` | Publicación de las reglas domóticas activadas. |

El flujo principal de comunicación es el siguiente:

1. Los sensores publican sus lecturas en el broker.
2. El motor de reglas recibe los datos y evalúa las condiciones domóticas.
3. Cuando es necesario, publica órdenes en los tópicos `set` de los actuadores.
4. Los actuadores reciben las órdenes, ejecutan los cambios y publican sus estados en los tópicos `estado`.
5. El controlador central recibe los mensajes y actualiza la información de la habitación, además de almacenar los registros CSV.

De esta forma, los componentes funcionan de manera independiente y se comunican mediante el broker MQTT, sin necesidad de establecer conexiones directas entre ellos.