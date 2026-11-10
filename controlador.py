#!/usr/init/env python3
"""Monitor, Visor de Eventos y Registro CSV para la Práctica 2 IoT."""

import csv
import json
import os
import sys
import time
import paho.mqtt.client as mqtt
from config import BROKER_DEFAULT, PUERTO_DEFAULT, GRUPO_DEFAULT, topic_todo

GRUPO = sys.argv[1] if len(sys.argv) > 1 else GRUPO_DEFAULT

# Configuración de las rutas de almacenamiento local protegidas por el .gitignore
CARPETA_OUTPUT = "output"
CARPETA_EVENTS = os.path.join(CARPETA_OUTPUT, "events")

ARCHIVO_SNAPSHOT = os.path.join(CARPETA_OUTPUT, "registro_sensores.csv")
ARCHIVO_PRESENCIA = os.path.join(CARPETA_EVENTS, "presencia.csv")
ARCHIVO_TEMPERATURA = os.path.join(CARPETA_EVENTS, "temperatura.csv")
ARCHIVO_HUMEDAD = os.path.join(CARPETA_EVENTS, "humedad.csv")
ARCHIVO_LUZ = os.path.join(CARPETA_EVENTS, "luz.csv")

os.makedirs(CARPETA_OUTPUT, exist_ok=True)
os.makedirs(CARPETA_EVENTS, exist_ok=True)

# Diccionario global para mantener en memoria los valores vigentes de la sala
estado_habitacion = {
    "luz": "--",
    "humedad": "--",
    "temperatura": "--",
    "presencia": "--",
    "presencia_valor": 0,
    "bombilla": "OFF",
    "persiana": "CERRADA",
    "ultima_regla": "Ninguna",
}


# Imprime la tarjeta resumen estructurada con anchos exactos alineados
def imprimir_resumen_habitacion(hora_str):
    pres_val = estado_habitacion["presencia_valor"]
    pres_str = "SI (1)" if pres_val == 1 else "NO (0)"

    # Ancho total interior fijo de 62 caracteres exactos
    linea_sup = "+" + "-" * 62 + "+"
    
    print()
    print(linea_sup)
    print(f"| ESTADO ACTUAL DE LA ESTANCIA | Grupo: {GRUPO:<5} | Hora: {hora_str} |")
    print(linea_sup)
    print(f"| - Luz       : {str(estado_habitacion['luz']):<12} | Bombilla : {str(estado_habitacion['bombilla']):<20} |")
    print(f"| - Humedad   : {str(estado_habitacion['humedad']):<12} | Persiana : {str(estado_habitacion['persiana']):<20} |")
    print(f"| - Temp      : {str(estado_habitacion['temperatura']):<12} | Presencia: {pres_str:<20} |")
    print(linea_sup)
    print(f"| - Ultima regla: {str(estado_habitacion['ultima_regla'])[:44]:<44} |")
    print(linea_sup + "\n")


# Callback al conectar exitosamente al broker MQTT
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        topic = topic_todo(GRUPO)
        print("Monitor conectado exitosamente a HiveMQ")
        print(f"Escuchando actividad en: {topic}\n")
        client.subscribe(topic, qos=0)
    else:
        print(f"Error de conexion al broker. Codigo rc={rc}")


# Callback al recibir cualquier mensaje a través de la suscripción comodín
def on_message(client, userdata, msg):
    global estado_habitacion
    topic = msg.topic
    payload_str = msg.payload.decode("utf-8", errors="replace")
    ahora = time.strftime("%H:%M:%S")

    try:
        # Procesar mensajes provenientes de los sensores
        if "/sensor/" in topic and not topic.endswith("/lwt"):
            tipo_sensor = topic.split("/")[-1]
            try:
                datos = json.loads(payload_str)
                valor = datos.get("valor", payload_str)
                unidad = datos.get("unidad", "")
            except Exception:
                valor = payload_str
                unidad = ""

            estado_habitacion[tipo_sensor] = f"{valor} {unidad}".strip()

            if tipo_sensor == "presencia":
                estado_habitacion["presencia_valor"] = int(float(valor))

            archivo_destino = None
            if tipo_sensor == "presencia":
                archivo_destino = ARCHIVO_PRESENCIA
            elif tipo_sensor == "temperatura":
                archivo_destino = ARCHIVO_TEMPERATURA
            elif tipo_sensor == "humedad":
                archivo_destino = ARCHIVO_HUMEDAD
            elif tipo_sensor == "luz":
                archivo_destino = ARCHIVO_LUZ

            if archivo_destino:
                with open(archivo_destino, mode="a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), valor])

            print(f"[{ahora}] [SENSOR] {tipo_sensor.upper():<12} = {valor} {unidad}")

            # Registrar snapshot consolidado en CSV
            with open(ARCHIVO_SNAPSHOT, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    estado_habitacion["presencia_valor"],
                    estado_habitacion["temperatura"],
                    estado_habitacion["humedad"],
                    estado_habitacion["luz"],
                    estado_habitacion["bombilla"],
                    estado_habitacion["persiana"]
                ])

        # Procesar órdenes emitidas hacia los actuadores
        elif "/actuador/" in topic and topic.endswith("/set"):
            tipo_act = topic.split("/")[-2]
            print(f"[{ahora}] [ORDEN ACT]  {tipo_act.upper():<12} -> {payload_str}")

        # Procesar reportes de estado confirmados por los actuadores
        elif "/actuador/" in topic and topic.endswith("/estado"):
            tipo_act = topic.split("/")[-2]
            try:
                datos = json.loads(payload_str)
                estado = datos.get("estado", payload_str)
                origen = datos.get("origen", "MQTT")
            except Exception:
                estado = payload_str
                origen = "RAW"

            estado_habitacion[tipo_act] = str(estado).strip().upper()
            ret = " [RETENIDO]" if msg.retain else ""
            print(f"[{ahora}] [ESTADO ACT] {tipo_act.upper():<12} = {estado} ({origen}){ret}")
            imprimir_resumen_habitacion(ahora)

        # Procesar auditorías de reglas emitidas por el motor de reglas
        elif "/sistema/regla" in topic:
            try:
                datos = json.loads(payload_str)
                regla_txt = datos.get("regla", payload_str)
            except Exception:
                regla_txt = payload_str

            estado_habitacion["ultima_regla"] = regla_txt
            print(f"[{ahora}] [REGLA]      {regla_txt}")

        # Procesar mensajes de testamento LWT
        elif topic.endswith("/lwt"):
            nodo = topic.split("/")[-2]
            estado = payload_str.strip().upper()
            print(f"[{ahora}] [LWT]  Nodo '{nodo}' -> {estado}")

    except Exception as e:
        print(f"Error procesando mensaje en {topic}: {e}")


def main():
    print("=" * 64)
    print(f"MONITOR Y VISOR DE EVENTOS MQTT (Grupo: {GRUPO})")
    print("=" * 64)
    print(f"Broker : {BROKER_DEFAULT}:{PUERTO_DEFAULT}")
    print(f"Filtro : {topic_todo(GRUPO)}")
    print("-" * 64)

    for archivo in [ARCHIVO_PRESENCIA, ARCHIVO_TEMPERATURA, ARCHIVO_HUMEDAD, ARCHIVO_LUZ]:
        if not os.path.exists(archivo):
            with open(archivo, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp_Llegada", "Valor"])

    if not os.path.exists(ARCHIVO_SNAPSHOT):
        with open(ARCHIVO_SNAPSHOT, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Presencia", "Temperatura_C", "Humedad_pct", "Luz_lux", "Luz_Bombilla", "Persiana"])

    client_id = f"monitor-{GRUPO}-{int(time.time())}"
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    except AttributeError:
        client = mqtt.Client(client_id=client_id)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER_DEFAULT, PUERTO_DEFAULT, keepalive=60)
    client.loop_start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
            print("\nDeteniendo monitor...")
            client.loop_stop()
            client.disconnect()
            print("Monitor desconectado correctamente.\n")


if __name__ == "__main__":
    main()