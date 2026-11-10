#!/usr/bin/env python3
"""Motor de Reglas Domóticas (Consumidor de Eventos) para la Práctica 2 IoT."""

import sys
import time
import json
import paho.mqtt.client as mqtt
from config import (
    BROKER_DEFAULT, PUERTO_DEFAULT, GRUPO_DEFAULT,
    UMBRAL_LUZ_BAJA, UMBRAL_LUZ_ALTA,
    UMBRAL_HUMEDAD_ALTA, UMBRAL_HUMEDAD_BAJA,
    topic_base, topic_actuador_set, topic_reglas
)

# Captura el identificador del grupo por argumento de consola o usa el valor por defecto
GRUPO = sys.argv[1] if len(sys.argv) > 1 else GRUPO_DEFAULT

# Estado en memoria que almacena las lecturas de los sensores y el estado actual de los actuadores
estado_habitacion = {
    "luz": None,
    "humedad": None,
    "temperatura": None,
    "presencia": 0,
    "presencia_anterior": 0,
    "bombilla": "OFF",
    "persiana": "CERRADA"
}

def evaluar_reglas(e):
    """Evalúa el conjunto de reglas domóticas basándose en el estado actual y previo de la sala.
    
    Reglas implementadas:
    - R1: Entrada de persona (0 a 1) Y Luz < 150 lux -> Bombilla ON.
      Justificación: Confort visual inmediato al acceder a una habitación oscura
    - R2: Salida de persona (1 a 0) -> Bombilla OFF y Persiana CERRADA.
      Justificación: Eficiencia energética y seguridad cuando la estancia queda vacía
    - R3: Humedad relativa > 70% -> Persiana ABIERTA.
      Justificación: Ventilación natural de choque para disipar condensaciones o vapor
    - R4: Luz natural > 600 lux Y Humedad < 40% -> Persiana CERRADA.
      Justificación: Protección solar pasiva contra sobrecalentamiento por radiación
    - R5: Presencia activa (1) Y Luz < 150 lux -> Bombilla ON.
      Justificación: Mantenimiento de iluminación artificial si oscurece con usuarios dentro

    Reglas extra añadidas
    - R6: Temperatura > 30.0 C Y Presencia activa (1) -> Persiana ABIERTA.
      Justificación: Mejora del flujo de aire y refrigeración pasiva para confort térmico.
    - R7: Temperatura < 18.0 C -> Persiana CERRADA.
      Justificación: Aislamiento térmico pasivo para evitar pérdidas de calor en épocas frías.
    """
    ordenes = {}
    reglas_disparadas = []
    luz = e["luz"]
    humedad = e["humedad"]
    temperatura = e["temperatura"]
    presencia = e["presencia"]
    presencia_ant = e["presencia_anterior"]
    bombilla_actual = e["bombilla"]
    persiana_actual = e["persiana"]

    ha_entrado = (presencia == 1 and presencia_ant == 0)
    ha_salido = (presencia == 0 and presencia_ant == 1)

    # REGLA R2: Salida de persona -> Apagar bombilla y cerrar persiana
    # Justificación: Eficiencia energética y seguridad cuando la estancia queda vacía.
    if ha_salido:
        if bombilla_actual != "OFF":
            ordenes["bombilla"] = "OFF"
        if persiana_actual != "CERRADA":
            ordenes["persiana"] = "CERRADA"
        reglas_disparadas.append("R2: Persona ha salido -> B OFF y P CER")

    # REGLA R1: Entrada de persona Y luz < UMBRAL_LUZ_BAJA -> Encender bombilla
    # Justificación: Confort visual inmediato al acceder a una habitación oscura.
    if ha_entrado and (luz is not None and luz < UMBRAL_LUZ_BAJA):
        if bombilla_actual != "ON":
            ordenes["bombilla"] = "ON"
        reglas_disparadas.append(f"R1: Entrada de persona con poca luz -> B ON")

    # REGLA R5: Presencia activa Y luz < UMBRAL_LUZ_BAJA -> Encender bombilla
    # Justificación: Mantenimiento de iluminación artificial si oscurece con usuarios dentro.
    if presencia == 1 and (luz is not None and luz < UMBRAL_LUZ_BAJA):
        if bombilla_actual != "ON":
            ordenes["bombilla"] = "ON"
        reglas_disparadas.append(f"R5: Presencia activa con poca luz -> B ON")
    # REGLA R3: Humedad relativa > UMBRAL_HUMEDAD_ALTA -> Abrir persiana
    # Justificación: Ventilación natural de choque para disipar condensaciones o vapor.
    if humedad is not None and humedad > UMBRAL_HUMEDAD_ALTA:
        if persiana_actual != "ABIERTA":
            ordenes["persiana"] = "ABIERTA"
            reglas_disparadas.append(f"R3: Humedad alta -> P ABI")
            
    # REGLA R4: Luz natural > UMBRAL_LUZ_ALTA Y Humedad < UMBRAL_HUMEDAD_BAJA -> Cerrar persiana
    # Justificación: Protección solar pasiva contra sobrecalentamiento por radiación.
    elif (luz is not None and luz > UMBRAL_LUZ_ALTA) and (humedad is not None and humedad < UMBRAL_HUMEDAD_BAJA):
        if persiana_actual != "CERRADA":
            ordenes["persiana"] = "CERRADA"
            reglas_disparadas.append(f"R4: Mucha luz y aire seco -> P CER")

    # REGLA R6: Temperatura elevada (> 30.0 C) con presencia activa -> Abrir persiana
    # Justificación: Mejora del flujo de aire y refrigeración pasiva por confort térmico.
    if temperatura is not None and temperatura > 30.0 and presencia == 1:
        if persiana_actual != "ABIERTA":
            ordenes["persiana"] = "ABIERTA"
            reglas_disparadas.append(f"R6: Temperatura alta con presencia -> P ABI")

    # REGLA R7: Temperatura baja (< 18.0 C) -> Cerrar persiana
    # Justificación: Aislamiento térmico pasivo para evitar pérdidas de calor en épocas frías.
    if temperatura is not None and temperatura < 18.0:
        if persiana_actual != "CERRADA":
            ordenes["persiana"] = "CERRADA"
            reglas_disparadas.append(f"R7: Temperatura baja -> P CER")

    return ordenes, reglas_disparadas

def on_connect(client, userdata, flags, rc, properties=None):
    """Callback que se ejecuta cuando el cliente se conecta correctamente al broker MQTT."""
    if rc == 0:
        base = topic_base(GRUPO)
        print("Motor de Reglas conectado exitosamente a HiveMQ")
        print(f"Suscrito a: {base}/sensor/# y {base}/actuador/+/estado\n")
        # Se suscribe a los canales de telemetría de los sensores y a los estados confirmados de actuadores
        client.subscribe(f"{base}/sensor/#", qos=0)
        client.subscribe(f"{base}/actuador/+/estado", qos=1)

def on_message(client, userdata, msg):
    """Callback que se ejecuta de forma asíncrona ante la llegada de cada mensaje MQTT."""
    global estado_habitacion
    topic = msg.topic
    payload_str = msg.payload.decode("utf-8", errors="replace")
    try:
        # Procesa los mensajes provenientes de los sensores del grupo
        if "/sensor/" in topic:
            tipo_sensor = topic.split("/")[-1]
            if tipo_sensor in ["luz", "humedad", "temperatura", "presencia"]:
                if payload_str.startswith("{"):
                    valor = json.loads(payload_str).get("valor")
                else:
                    valor = float(payload_str)

                # Almacena el valor actual y actualiza el histórico de presencia
                if tipo_sensor == "presencia":
                    estado_habitacion["presencia_anterior"] = estado_habitacion["presencia"]
                    estado_habitacion["presencia"] = int(valor)
                else:
                    estado_habitacion[tipo_sensor] = float(valor)

        # Procesa los reportes de estado confirmados por los propios actuadores
        elif "/actuador/" in topic and topic.endswith("/estado"):
            tipo_act = topic.split("/")[-2]
            if tipo_act in ["bombilla", "persiana"]:
                if payload_str.startswith("{"):
                    estado_act = str(json.loads(payload_str).get("estado", "")).upper()
                else:
                    estado_act = payload_str.strip().upper()
                if estado_act:
                    estado_habitacion[tipo_act] = estado_act

        # Ejecuta la evaluación de reglas después de actualizar las variables de la sala
        ordenes, reglas = evaluar_reglas(estado_habitacion)
        estado_habitacion["presencia_anterior"] = estado_habitacion["presencia"]

        # Publica las órdenes de control generadas hacia los tópicos de los actuadores
        for act, nuevo_estado in ordenes.items():
            topic_set = topic_actuador_set(act, GRUPO)
            client.publish(topic_set, payload=nuevo_estado, qos=1)
            print(f"[ORDEN EMITIDA] -> {topic_set}: {nuevo_estado}")

        # Publica las auditorías de las reglas disparadas en el canal correspondiente
        for reg in reglas:
            print(f"[REGLA ACTIVADA] {reg}")
            client.publish(topic_reglas(GRUPO), json.dumps({"regla": reg, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}), qos=0)
            
    except Exception as e:
        print(f"Error procesando evento: {e}")

def main():
    """Función principal que configura la conexión inicial e inicia el bucle de escucha permanente."""
    print("=" * 65)
    print(f"MOTOR DE REGLAS DOMÓTICAS (Grupo: {GRUPO})")
    print("=" * 65)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"reglas-{GRUPO}")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER_DEFAULT, PUERTO_DEFAULT, keepalive=60)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo el motor de reglas...")
        client.disconnect()

if __name__ == "__main__":
    main()