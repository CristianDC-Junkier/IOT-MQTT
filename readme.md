# Práctica 2: Sistema IoT Domótico con Protocolo MQTT

Este proyecto implementa una solución completa de IoT para la gestión inteligente de una habitación utilizando el protocolo **MQTT**, el broker público **HiveMQ** (`broker.hivemq.com`), y almacenamiento local protegido de datos de telemetría y eventos.

---

## 1.- Estructura del Proyecto

Asegúrate de que la estructura de carpetas y archivos en tu directorio de trabajo sea la siguiente:

```text
Practica_2_IoT/
├── config.py             # Configuración central (broker, tópicos y umbrales)
├── sensor.py             # Emulador de sensores virtuales (luz, humedad, temperatura, presencia)
├── actuador.py           # Simulador interactivo de actuadores (bombilla, persiana)
├── reglas.py             # Motor reactivo de 7 reglas domóticas
├── controlador.py         # Monitor central y generador de persistencia CSV
├── lanzar_todo.py        # Lanzador automatizado conjunto mediante subprocesos
├── data/                 # Ficheros CSV de entrada para los sensores virtuales
│   ├── datos_luz.csv
│   ├── datos_humedad.csv
│   ├── datos_temperatura.csv
│   ├── datos_presencia.csv
│   └── datos_sensores.csv (opcional unificado)
└── output/               # Carpeta generada automáticamente para los CSVs de salida
    ├── registro_sensores.csv
    └── events/
        ├── presencia.csv
        ├── temperatura.csv
        ├── humedad.csv
        └── luz.csv
```

---

## 2.- Requisitos Previos e Instalación

### Requisitos
- Python 3.8 o superior.
- Conexión activa a Internet (para conectar con el broker público `broker.hivemq.com`).

### Instalación de dependencias
Instala la biblioteca cliente oficial de MQTT para Python:

```bash
pip install paho-mqtt
```

---

## 3. Guía de Ejecución

Existen dos modalidades principales para ejecutar y probar la práctica.

---

### Opción A: Modo Automatizado (Recomendado)

Inicia todo el sistema (Monitor, Actuador Bombilla, Actuador Persiana, Motor de Reglas y los 4 Sensores) en un único comando y en una sola terminal.

#### 1.- Ejecución estándar (Grupo `g99` por defecto):
```bash
python lanzar_todo.py 
```

#### 2.- Parámetros opcionales del lanzador:
* **Cambiar el periodo de muestreo de los sensores (ej. cada 1.0 s):**
  ```bash
  python lanzar_todo.py g99 --periodo 1.0
  ```
* **Lanzar solo los actuadores y reglas (sin sensores):**
  ```bash
  python lanzar_todo.py g99 --solo-servicios
  ```
* **Detener el sistema:**
  Presiona `Ctrl + C` en la terminal donde ejecutaste el comando. Todos los procesos hijos finalizan de forma limpia.

---

### Opción B: Modo Manual (Múltiples Terminales)

Para depurar, interactuar manualmente con los actuadores o ver las trazas de cada módulo por separado, abre **varias terminales simultáneas** en el directorio raíz del proyecto y ejecuta los siguientes comandos en el orden indicado:

#### Terminal 1: Monitor y Registro CSV (`controlador.py`)
Escucha toda la actividad del grupo (`iotlab26/g99/#`) y guarda las capturas en `output/`:
```bash
python controlador.py 
```

#### Terminal 2: Motor de Reglas Domóticas (`reglas.py`)
Procesa eventos y evalúa las 7 reglas (R1 a R7):
```bash
python reglas.py 
```

#### Terminal 3: Actuador de Bombilla (`actuador.py`)
Simula la bombilla e interactúa por consola escribiendo `ON`, `OFF` o `q`:
```bash
python actuador.py --tipo bombilla --grupo g99
```

#### Terminal 4: Actuador de Persiana (`actuador.py`)
Simula la persiana e interactúa por consola escribiendo `ABIERTA`, `CERRADA` o `q`:
```bash
python actuador.py --tipo persiana --grupo g99
```

#### Terminal 5: Sensores Virtuales (`sensor.py`)
Puedes arrancar cada sensor individualmente especificando su tipo:
```bash
# Terminal 5a - Sensor de Luz
python sensor.py --tipo luz --grupo g99 --periodo 2.0

# Terminal 5b - Sensor de Humedad
python sensor.py --tipo humedad --grupo g99 --periodo 2.0

# Terminal 5c - Sensor de Temperatura
python sensor.py --tipo temperatura --grupo g99 --periodo 2.0

# Terminal 5d - Sensor de Presencia
python sensor.py --tipo presencia --grupo g99 --periodo 2.0
```

---

## 4. Resumen de Reglas Domóticas Evaluadas

* **R1:** Entrada de persona ($0 \rightarrow 1$) con Luz $< 150\text{ lux} \Rightarrow \text{Bombilla ON}$ (Confort visual).
* **R2:** Salida de persona ($1 \rightarrow 0$) $\Rightarrow \text{Bombilla OFF}$ y $\text{Persiana CERRADA}$ (Eficiencia energética).
* **R3:** Humedad relativa $> 70\% \Rightarrow \text{Persiana ABIERTA}$ (Ventilación).
* **R4:** Luz natural $> 600\text{ lux}$ y Humedad $< 40\% \Rightarrow \text{Persiana CERRADA}$ (Protección solar).
* **R5:** Presencia activa ($1$) con Luz $< 150\text{ lux} \Rightarrow \text{Bombilla ON}$ (Mantenimiento de luz).
* **R6:** Temperatura $> 30^\circ\text{C}$ con Presencia activa ($1$) $\Rightarrow \text{Persiana ABIERTA}$ (Refrigeración pasiva).
* **R7:** Temperatura $< 18^\circ\text{C} \Rightarrow \text{Persiana CERRADA}$ (Aislamiento térmico).

## 5. Script Avanzado de Mensajes Retenidos (`avanzado_retained.py`)

Para demostrar el comportamiento del flag `retain=True` frente a los mensajes efímeros (`retain=False`) tal como se exige en la práctica:

## 6. Testamento (Last Will and Testament, LWT) y Keepalive (`avanzado_lwt.py`)

Este script automatizado mide el tiempo real que tarda el broker en detectar la caída imprevista de un nodo y disparar su testamento sin recurrir a polling HTTP continuo.

#### Ejecución:
```bash
python avanzado_lwt.py g99
```

### Ejecución de la prueba:
```bash
python avanzado_retained.py g99
```