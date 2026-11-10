#!/usr/bin/env python3
"""Script Único de Demostración y Prueba de LWT y Keepalive para la Práctica 2 IoT."""

import sys
import time
import threading
import paho.mqtt.client as mqtt
from config import BROKER_DEFAULT, PUERTO_DEFAULT, GRUPO_DEFAULT

GRUPO = sys.argv[1] if len(sys.argv) > 1 else GRUPO_DEFAULT

# Tópico único para esta ejecución para evitar interferencias de mensajes anteriores
SESION_ID = int(time.time())
TOPIC_LWT = f"iotlab26/{GRUPO}/demo/todo_en_uno_{SESION_ID}/lwt"

# Variable global para registrar cuándo llegó el LWT
tiempo_lwt_recibido = None

def on_message_monitor(client, userdata, msg):
    """Callback del monitor interno cuando recibe un mensaje en el canal LWT."""
    global tiempo_lwt_recibido
    payload = msg.payload.decode("utf-8", errors="replace")
    ahora = time.strftime("%H:%M:%S")
    print(f"   [MONITOR] [{ahora}] Recibido en [{msg.topic}] -> {payload}")
    if payload == "OFFLINE":
        tiempo_lwt_recibido = time.time()

def main():
    print("=" * 70)
    print(f"DEMOSTRACION COMPLETA Y UNICA DE LWT Y KEEPALIVE (Grupo: {GRUPO})")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. Arrancar el Monitor en segundo plano
    # -------------------------------------------------------------
    print("[FASE 1] Iniciando monitor interno para escuchar el testamento...")
    client_mon_id = f"monitor-unico-{SESION_ID}"
    client_mon = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_mon_id)
    client_mon.on_message = on_message_monitor
    client_mon.connect(BROKER_DEFAULT, PUERTO_DEFAULT, keepalive=60)
    client_mon.loop_start()
    client_mon.subscribe(TOPIC_LWT, qos=1)
    time.sleep(1)

    # -------------------------------------------------------------
    # 2. Conectar el Sensor con Keepalive de 8 segundos y LWT configurado
    # -------------------------------------------------------------
    KEEPALIVE_SECS = 8
    print(f"[FASE 2] Conectando sensor emulado con keepalive={KEEPALIVE_SECS}s...")
    client_sensor_id = f"sensor-unico-{SESION_ID}"
    client_sensor = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_sensor_id)
    
    # Configuración del Testamento: Si muere sin avisar, publicará OFFLINE
    client_sensor.will_set(TOPIC_LWT, payload="OFFLINE", qos=1)
    
    client_sensor.connect(BROKER_DEFAULT, PUERTO_DEFAULT, keepalive=KEEPALIVE_SECS)
    client_sensor.loop_start()
    time.sleep(1)

    # Publicamos estado ONLINE inicial
    print(f"[FASE 3] Publicando estado ONLINE inicial en el canal LWT...")
    client_sensor.publish(TOPIC_LWT, payload="ONLINE", qos=1)
    time.sleep(2)

    # -------------------------------------------------------------
    # 3. Simular apagón o congelamiento repentino (Silencio de pings)
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("[FASE 4] SIMULANDO APAGON: Congelando el envio de PINGs del sensor...")
    print("El sensor deja de enviar pings al broker sin cerrar el socket limpiamente.")
    print("=" * 70)
    
    # Detenemos bruscamente el bucle del sensor que enviaba los PINGREQ de keepalive
    client_sensor.loop_stop()
    
    inicio_cronometro = time.time()
    print(f"Cronometro iniciado. Esperando a que el broker detecte la expiracion ({KEEPALIVE_SECS}s + margen)...")

    # Espera activa hasta que el monitor reciba el mensaje OFFLINE del broker
    tiempo_maximo_espera = KEEPALIVE_SECS + 10
    global tiempo_lwt_recibido
    tiempo_lwt_recibido = None

    while (time.time() - inicio_cronometro) < tiempo_maximo_espera:
        if tiempo_lwt_recibido is not None:
            break
        time.sleep(0.2)

    # -------------------------------------------------------------
    # 4. Resultados de la prueba
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("RESULTADO DE LA DEMOSTRACION UNIFICADA:")
    print("=" * 70)
    
    if tiempo_lwt_recibido is not None:
        duracion_real = tiempo_lwt_recibido - inicio_cronometro
        print(f"EXITO: El broker detecto la caida automatica tras {duracion_real:.2f} segundos.")
        print("El temporizador de Keepalive expiro y el broker activo el testamento (LWT) correctamente.")
    else:
        print("AVISO: Se agoto el tiempo maximo de espera sin recibir el LWT.")

    # Cierre ordenado del monitor
    client_mon.loop_stop()
    client_mon.disconnect()
    print("=" * 70)

if __name__ == "__main__":
    main()