#!/usr/bin/env python3
"""Módulo de Sensor Virtual para la Práctica 2 IoT."""

import argparse
import csv
import json
import os
import sys
import time
import paho.mqtt.client as mqtt
from config import BROKER_DEFAULT, PUERTO_DEFAULT, GRUPO_DEFAULT, topic_sensor

# Diccionario que asocia cada sensor con su unidad de medida física
UNIDADES = {
    "luz": "lux",
    "humedad": "%",
    "temperatura": "C",
    "presencia": "binario",
}


# Configura los parámetros que se pueden pasar por la línea de comandos
def parse_args():
    parser = argparse.ArgumentParser(description="Emulador de Sensor IoT")
    parser.add_argument(
        "--tipo",
        type=str,
        required=True,
        choices=["luz", "humedad", "temperatura", "presencia"],
    )
    parser.add_argument("--grupo", type=str, default=GRUPO_DEFAULT)
    parser.add_argument("--periodo", type=float, default=2.0)
    parser.add_argument("--fichero", type=str, default=None)
    parser.add_argument("--broker", type=str, default=BROKER_DEFAULT)
    parser.add_argument("--puerto", type=int, default=PUERTO_DEFAULT)
    return parser.parse_args()


# Lee y extrae de forma segura los valores numéricos del archivo CSV correspondiente
def leer_datos_csv(ruta_fichero, tipo_sensor):
    valores = []
    if not os.path.exists(ruta_fichero):
        raise FileNotFoundError(f"No se encontró el fichero: {ruta_fichero}")
    with open(ruta_fichero, mode="r", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            if tipo_sensor in fila and fila[tipo_sensor] is not None:
                val = (
                    int(fila[tipo_sensor].strip())
                    if tipo_sensor == "presencia"
                    else float(fila[tipo_sensor].strip())
                )
                valores.append(val)
            elif "valor" in fila and fila["valor"] is not None:
                val = (
                    int(fila["valor"].strip())
                    if tipo_sensor == "presencia"
                    else float(fila["valor"].strip())
                )
                valores.append(val)
    return valores


def main():
    args = parse_args()
    tipo = args.tipo
    grupo = args.grupo
    periodo = args.periodo
    topic = topic_sensor(tipo, grupo)
    unidad = UNIDADES.get(tipo, "")

    # Define las rutas relativas para buscar los ficheros dentro de la carpeta data
    dir_actual = os.path.dirname(os.path.abspath(__file__))
    dir_data = os.path.join(dir_actual, "data")

    if args.fichero:
        ruta_csv = (
            args.fichero
            if os.path.isabs(args.fichero)
            else os.path.join(dir_actual, args.fichero)
        )
    else:
        ruta_dedicada = os.path.join(dir_data, f"datos_{tipo}.csv")
        ruta_unificada = os.path.join(dir_data, "datos_sensores.csv")

        if os.path.exists(ruta_dedicada):
            ruta_csv = ruta_dedicada
        elif os.path.exists(ruta_unificada):
            ruta_csv = ruta_unificada
        else:
            ruta_dedicada_raiz = os.path.join(dir_actual, f"datos_{tipo}.csv")
            ruta_csv = (
                ruta_dedicada_raiz
                if os.path.exists(ruta_dedicada_raiz)
                else os.path.join(dir_actual, "datos_sensores.csv")
            )

    datos = leer_datos_csv(ruta_csv, tipo)

    # Inicializa el cliente MQTT asegurando compatibilidad con las versiones 1 y 2
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"sensor-{tipo}-{grupo}-{int(time.time())}",
    )
    topic_lwt = f"iotlab26/{grupo}/sensor/{tipo}/lwt"

    # Configura el mensaje de testamento para notificar si el sensor se desconecta de forma anómala
    client.will_set(topic_lwt, payload="OFFLINE", qos=1, retain=True)

    client.connect(args.broker, args.puerto, keepalive=60)
    client.loop_start()
    client.publish(topic_lwt, payload="ONLINE", qos=1, retain=True)
    time.sleep(1)

    indice = 0
    total = len(datos)
    try:
        # Bucle principal para publicar de forma cíclica los valores leídos del CSV
        while True:
            valor_actual = datos[indice]
            ahora_str = time.strftime("%Y-%m-%d %H:%M:%S")
            payload = {
                "sensor": tipo,
                "valor": valor_actual,
                "unidad": unidad,
                "timestamp": ahora_str,
                "grupo": grupo,
            }
            client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=0)
            print(f"[{ahora_str}] Publicando {tipo.upper()}: {valor_actual} {unidad}")
            indice = (indice + 1) % total
            time.sleep(periodo)
    except KeyboardInterrupt:
        # Cierra la conexión de manera limpia al interrumpir con el teclado
        client.publish(topic_lwt, payload="OFFLINE", qos=1, retain=True)
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()