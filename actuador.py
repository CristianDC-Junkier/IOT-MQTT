#!/usr/bin/env python3
"""Módulo de Actuador Simulado e Interactivo para la Práctica 2 IoT."""

import argparse
import json
import sys
import threading
import time
import paho.mqtt.client as mqtt
from config import (
    BROKER_DEFAULT,
    PUERTO_DEFAULT,
    GRUPO_DEFAULT,
    topic_actuador_set,
    topic_actuador_estado,
)

# Define los estados válidos permitidos para cada componente físico simulado
ESTADOS_VALIDOS = {"bombilla": ["ON", "OFF"], "persiana": ["ABIERTA", "CERRADA"]}
ESTADO_INICIAL = {"bombilla": "OFF", "persiana": "CERRADA"}


# Configura los argumentos requeridos al iniciar el script por consola
def parse_args():
    parser = argparse.ArgumentParser(description="Actuador IoT interactivo")
    parser.add_argument(
        "--tipo",
        type=str,
        required=True,
        choices=["bombilla", "persiana"],
        help="Tipo de actuador: bombilla o persiana",
    )
    parser.add_argument(
        "--grupo",
        type=str,
        default=GRUPO_DEFAULT,
        help=f"Identificador del grupo (por defecto '{GRUPO_DEFAULT}')",
    )
    parser.add_argument(
        "--broker",
        type=str,
        default=BROKER_DEFAULT,
        help=f"Broker MQTT (por defecto {BROKER_DEFAULT})",
    )
    parser.add_argument(
        "--puerto",
        type=int,
        default=PUERTO_DEFAULT,
        help=f"Puerto del broker (por defecto {PUERTO_DEFAULT})",
    )
    return parser.parse_args()


class ActuadorSimulado:

    def __init__(self, tipo, grupo, broker, puerto):
        self.tipo = tipo
        self.grupo = grupo
        self.broker = broker
        self.puerto = puerto
        self.estado = ESTADO_INICIAL[tipo]
        self.topic_set = topic_actuador_set(tipo, grupo)
        self.topic_estado = topic_actuador_estado(tipo, grupo)
        self.topic_lwt = f"iotlab26/{grupo}/actuador/{tipo}/lwt"
        self.estados_permitidos = ESTADOS_VALIDOS[tipo]
        self.activo = True
        self.lock = threading.Lock()

        client_id = f"act-{tipo}-{grupo}-{int(time.time())}"
        try:
            self.client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2, client_id=client_id
            )
        except AttributeError:
            self.client = mqtt.Client(client_id=client_id)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.will_set(
            self.topic_lwt, payload="OFFLINE", qos=1, retain=True
        )

    # Acciones ejecutadas automáticamente al conectar con éxito al broker
    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print(f"Conectado a HiveMQ ({self.broker}:{self.puerto})")
            print(f"Suscrito a órdenes en: {self.topic_set}")
            client.subscribe(self.topic_set, qos=1)
            client.publish(
                self.topic_lwt, payload="ONLINE", qos=1, retain=True
            )
            self.publicar_estado("INICIAL")
        else:
            print(f"Error de conexión al broker. Código rc={rc}")

    # Procesa las órdenes automáticas que llegan a través de MQTT
    def on_message(self, client, userdata, msg):
        try:
            orden_raw = msg.payload.decode("utf-8").strip()
            if orden_raw.startswith("{"):
                datos = json.loads(orden_raw)
                nuevo_estado = str(
                    datos.get("estado", datos.get("orden", ""))
                ).upper()
            else:
                nuevo_estado = orden_raw.upper()

            if nuevo_estado in self.estados_permitidos:
                with self.lock:
                    if nuevo_estado != self.estado:
                        antiguo = self.estado
                        self.estado = nuevo_estado
                        print(
                            f"\n[ORDEN MQTT] Cambio de estado: {antiguo} -> {self.estado}"
                        )
                        self.publicar_estado("MQTT")
                        self.mostrar_prompt()
            else:
                print(f"\n[ORDEN RECHAZADA] Valor no válido: '{nuevo_estado}'")
                self.mostrar_prompt()
        except Exception as e:
            print(f"\nError procesando orden MQTT: {e}")
            self.mostrar_prompt()

    # Publica el estado actual confirmado empleando el flag retain en true
    def publicar_estado(self, origen="MANUAL"):
        payload = {
            "actuador": self.tipo,
            "estado": self.estado,
            "origen": origen,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "grupo": self.grupo,
        }
        self.client.publish(
            self.topic_estado,
            json.dumps(payload, ensure_ascii=False),
            qos=1,
            retain=True,
        )
        print(
            f"[ESTADO CONFIRMADO] {self.tipo.upper()} = {self.estado} (en {self.topic_estado})"
        )

    def mostrar_prompt(self):
        opciones = "/".join(self.estados_permitidos)
        print(
            f"\n[{self.tipo.upper()}] Estado: [{self.estado}] | Escribe ({opciones}) o 'q': ",
            end="",
            flush=True,
        )

    # Hilo secundario independiente para manejar cambios de estado manuales por teclado
    def bucle_consola_interactivo(self):
        time.sleep(1.5)
        while self.activo:
            try:
                self.mostrar_prompt()
                linea = sys.stdin.readline()
                if not linea:
                    break
                entrada = linea.strip().upper()
                if entrada == "Q":
                    self.activo = False
                    break
                if not entrada:
                    continue
                if entrada in self.estados_permitidos:
                    with self.lock:
                        if entrada != self.estado:
                            antiguo = self.estado
                            self.estado = entrada
                            print(
                                f"\n[MANUAL] Cambiado {self.tipo}: {antiguo} -> {self.estado}"
                            )
                            self.publicar_estado("MANUAL")
                else:
                    print(f"\nOpción no válida '{entrada}'.")
            except (EOFError, KeyboardInterrupt):
                self.activo = False
                break

    def iniciar(self):
        print("=" * 65)
        print(f"ACTUADOR SIMULADO: {self.tipo.upper()} (Grupo: {self.grupo})")
        print("=" * 65)
        self.client.connect(self.broker, self.puerto, keepalive=60)
        self.client.loop_start()
        threading.Thread(
            target=self.bucle_consola_interactivo, daemon=True
        ).start()
        try:
            while self.activo:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.activo = False
            self.client.publish(
                self.topic_lwt, payload="OFFLINE", qos=1, retain=True
            )
            self.client.loop_stop()
            self.client.disconnect()


def main():
    args = parse_args()
    ActuadorSimulado(
        args.tipo, args.grupo, args.broker, args.puerto
    ).iniciar()


if __name__ == "__main__":
    main()