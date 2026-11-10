#!/usr/bin/env python3
"""Script Automatizado de Demostración de Mensajes Retenidos para la Práctica 2 IoT."""

import sys
import time
import paho.mqtt.client as mqtt
from config import BROKER_DEFAULT, PUERTO_DEFAULT, GRUPO_DEFAULT

GRUPO = sys.argv[1] if len(sys.argv) > 1 else GRUPO_DEFAULT

TOPIC_EFIMERO = f"iotlab26/{GRUPO}/demo/sensor_efimero"
TOPIC_RETENIDO = f"iotlab26/{GRUPO}/demo/actuador_estado"

# Variables globales para capturar lo que recibe el nuevo suscriptor
mensajes_recibidos = []

def on_message_suscriptor(client, userdata, msg):
    """Callback que registra los mensajes que le llegan al nuevo suscriptor."""
    payload = msg.payload.decode("utf-8", errors="replace")
    mensajes_recibidos.append((msg.topic, payload, msg.retain))
    print(f"   [NUEVO SUSCRIPTOR] Recibido en [{msg.topic}] -> {payload} (Retained: {msg.retain})")

def main():
    print("=" * 70)
    print(f"DEMOSTRACION AUTOMATIZADA DE MENSAJES RETENIDOS (Grupo: {GRUPO})")
    print("=" * 70)

    # 1. Fase de publicacion
    client_pub_id = f"demo-pub-{int(time.time())}"
    client_pub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_pub_id)
    client_pub.connect(BROKER_DEFAULT, PUERTO_DEFAULT, keepalive=60)
    client_pub.loop_start()
    time.sleep(1)

    print("[PASO 1] Publicando mensajes...");
    client_pub.publish(TOPIC_EFIMERO, payload="Sensor: 21.5 C", qos=1, retain=False)
    client_pub.publish(TOPIC_RETENIDO, payload="Actuador: ON", qos=1, retain=True)
    
    time.sleep(1)
    print("[PASO 2] El publicador original finaliza y se desconecta del broker.\n")
    client_pub.loop_stop()
    client_pub.disconnect()

    # Pausa simulando el paso del tiempo con el emisor apagado
    time.sleep(2)

    # 3. Fase de nuevo suscriptor
    print("[PASO 3] Conectando un NUEVO SUSCRIPTOR al broker tras la desconexion...")
    client_sub_id = f"demo-sub-{int(time.time())}"
    client_sub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_sub_id)
    client_sub.on_message = on_message_suscriptor
    
    client_sub.connect(BROKER_DEFAULT, PUERTO_DEFAULT, keepalive=60)
    client_sub.loop_start()

    # Se suscribe a ambos tópicos para comprobar qué almacena el broker
    client_sub.subscribe(TOPIC_EFIMERO, qos=1)
    client_sub.subscribe(TOPIC_RETENIDO, qos=1)

    # Esperamos unos segundos a que el broker entregue los mensajes retenidos
    time.sleep(2)

    print("\n" + "=" * 70)
    print("RESULTADO DE LA PRUEBA:")
    print("=" * 70)
    topics_con_mensaje = [m[0] for m in mensajes_recibidos]
    
    if TOPIC_RETENIDO in topics_con_mensaje and TOPIC_EFIMERO not in topics_con_mensaje:
        print("EXITO: El nuevo suscriptor SOLO ha recibido el mensaje retenido.")
        print("El mensaje efimero se desecho porque no habia nadie escuchando al publicar.")
    else:
        print("Comprobando recepcion...")
        
    client_sub.loop_stop()
    client_sub.disconnect()
    print("=" * 70)

if __name__ == "__main__":
    main()