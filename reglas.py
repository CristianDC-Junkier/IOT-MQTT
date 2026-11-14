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

# ************************************************************
#   1.- GESTIÓN DE ARGUMENTOS Y CONFIGURACIÓN DEL SISTEMA
# ************************************************************

# Permite especificar el grupo MQTT desde la línea de comandos.
# Si no se proporciona ningún argumento, se utiliza el grupo
# configurado por defecto en el módulo config.
# Ejemplo: python controlador.py g99

GRUPO = sys.argv[1] if len(sys.argv) > 1 else GRUPO_DEFAULT


# ************************************************************
#           2.- ESTADO GLOBAL DE LA ESTANCIA
# ************************************************************

# Almacena las últimas lecturas de los sensores y los estados
# conocidos de los actuadores.

estado_habitacion = {
    "luz": None,
    "humedad": None,
    "temperatura": None,
    "presencia": 0,
    "presencia_anterior": 0,
    "bombilla": "OFF",
    "persiana": "CERRADA"
}


# ************************************************************
#              3.- EVALUACIÓN DE LAS REGLAS DOMÓTICAS
# ************************************************************

def evaluar_reglas(e):
    """Evalúa las reglas domóticas según el estado actual y anterior.

    Reglas implementadas:
    - R1: Entrada de persona (0 a 1) Y Luz < 150 lux -> Bombilla ON.
    - R2: Salida de persona (1 a 0) -> Bombilla OFF y Persiana CERRADA.
    - R3: Humedad relativa > 70% -> Persiana ABIERTA.
    - R4: Luz natural > 600 lux Y Humedad < 40% -> Persiana CERRADA.
    - R5: Presencia activa (1) Y Luz < 150 lux -> Bombilla ON.
    """

    ordenes = {}
    reglas_disparadas = []

    # Recupera las últimas lecturas de los sensores y actuadores.
    luz = e["luz"]
    humedad = e["humedad"]
    presencia = e["presencia"]
    presencia_ant = e["presencia_anterior"]
    bombilla_actual = e["bombilla"]
    persiana_actual = e["persiana"]

    # Detecta las transiciones de entrada y salida.
    ha_entrado = (presencia == 1 and presencia_ant == 0)
    ha_salido = (presencia == 0 and presencia_ant == 1)


    # ************************************************************
    # REGLA R2: SALIDA DE PERSONA -> B OFF Y P CER
    # ************************************************************

    # Cuando una persona sale, se apaga la bombilla y se cierra
    # la persiana si alguno de los actuadores lo necesita.
    if ha_salido:

        if bombilla_actual != "OFF":
            ordenes["bombilla"] = "OFF"

        if persiana_actual != "CERRADA":
            ordenes["persiana"] = "CERRADA"

        # La regla se registra una sola vez por transición.
        reglas_disparadas.append(
            "R2: Persona ha salido -> B OFF y P CER"
        )


    # ************************************************************
    # REGLA R1: ENTRADA CON POCA LUZ -> B ON
    # ************************************************************

    # Se activa cuando una persona entra y la iluminación
    # disponible está por debajo del umbral establecido.
    if ha_entrado and luz is not None and luz < UMBRAL_LUZ_BAJA:

        if bombilla_actual != "ON":
            ordenes["bombilla"] = "ON"

            reglas_disparadas.append(
                "R1: Entrada de persona con poca luz -> B ON"
            )


    # ************************************************************
    # REGLA R5: PRESENCIA ACTIVA CON POCA LUZ -> B ON
    # ************************************************************

    # Permite encender la bombilla cuando disminuye la iluminación
    # mientras una persona permanece dentro de la habitación.
    elif presencia == 1 and luz is not None and luz < UMBRAL_LUZ_BAJA:

        if bombilla_actual != "ON":
            ordenes["bombilla"] = "ON"

            reglas_disparadas.append(
                "R5: Presencia activa con poca luz -> B ON"
            )


    # ************************************************************
    # REGLA R3: HUMEDAD ALTA -> ABRIR PERSIANA
    # ************************************************************

    # Si la humedad supera el umbral establecido, se abre la persiana
    # para favorecer la ventilación natural de la estancia.
    if humedad is not None and humedad > UMBRAL_HUMEDAD_ALTA:

        if persiana_actual != "ABIERTA":

            ordenes["persiana"] = "ABIERTA"

            reglas_disparadas.append(
                "R3: Humedad alta -> P ABI"
            )


    # ************************************************************
    # REGLA R4: MUCHA LUZ Y AIRE SECO -> CERRAR PERSIANA
    # ************************************************************

    # Si existe mucha luz natural y la humedad es baja, se cierra
    # la persiana para reducir la entrada de radiación solar.
    if (
        luz is not None
        and luz > UMBRAL_LUZ_ALTA
        and humedad is not None
        and humedad < UMBRAL_HUMEDAD_BAJA
    ):

        if persiana_actual != "CERRADA":

            ordenes["persiana"] = "CERRADA"

            reglas_disparadas.append(
                "R4: Mucha luz y aire seco -> P CER"
            )

    return ordenes, reglas_disparadas


# ************************************************************
#       4.- CALLBACKS DE MQTT (CONEXIÓN Y RECEPCIÓN DE MENSAJES)
# ************************************************************

def on_connect(client, userdata, flags, rc, properties=None):
    """Callback que se ejecuta cuando el cliente se conecta al broker MQTT."""

    if rc == 0:

        base = topic_base(GRUPO)

        print("Motor de Reglas conectado exitosamente a HiveMQ")
        print(f"Suscrito a: {base}/sensor/# y {base}/actuador/+/estado")

        # Suscripción a los sensores y estados de los actuadores.
        client.subscribe(f"{base}/sensor/#", qos=0)
        client.subscribe(f"{base}/actuador/+/estado", qos=1)

    else:
        print(f"Error de conexion al broker. Codigo rc={rc}")


def on_message(client, userdata, msg):
    """Callback ejecutado automáticamente al recibir un mensaje MQTT."""

    global estado_habitacion

    topic = msg.topic
    payload_str = msg.payload.decode("utf-8", errors="replace")

    try:

        # ************************************************************
        # CASO A: MENSAJES PROCEDENTES DE LOS SENSORES
        # ************************************************************

        if "/sensor/" in topic:

            tipo_sensor = topic.split("/")[-1]

            # Solo procesa los sensores utilizados por las reglas.
            if tipo_sensor not in [
                "luz", "humedad", "temperatura", "presencia"
            ]:
                return

            # Interpreta el contenido del mensaje.
            if payload_str.startswith("{"):
                datos = json.loads(payload_str)
                valor = datos.get("valor")
            else:
                valor = payload_str

            valor = float(valor)

            # Actualiza el estado del sensor de presencia.
            if tipo_sensor == "presencia":

                nueva_presencia = int(valor)

                # Solo registra el estado anterior cuando existe
                # un cambio real de presencia.
                if nueva_presencia != estado_habitacion["presencia"]:

                    estado_habitacion["presencia_anterior"] = (
                        estado_habitacion["presencia"]
                    )

                    estado_habitacion["presencia"] = nueva_presencia

            else:
                estado_habitacion[tipo_sensor] = valor


            # ************************************************************
            # CASO B: EVALUACIÓN DE LAS REGLAS
            # ************************************************************

            # Evalúa las reglas utilizando el estado actualizado.
            ordenes, reglas = evaluar_reglas(estado_habitacion)


            # ************************************************************
            # CASO C: PUBLICACIÓN DE ÓRDENES A LOS ACTUADORES
            # ************************************************************

            for act, nuevo_estado in ordenes.items():

                topic_set = topic_actuador_set(act, GRUPO)

                info = client.publish(
                    topic_set,
                    payload=nuevo_estado,
                    qos=1
                )

                # Actualiza el estado conocido para evitar enviar
                # órdenes duplicadas mientras llega la confirmación.
                if info.rc == mqtt.MQTT_ERR_SUCCESS:

                    estado_habitacion[act] = nuevo_estado

                    print(
                        f"[ORDEN EMITIDA] -> {topic_set}: {nuevo_estado}"
                    )


            # ************************************************************
            # CASO D: PUBLICACIÓN DE AUDITORÍAS DE LAS REGLAS
            # ************************************************************

            for reg in reglas:

                print(f"[REGLA ACTIVADA] {reg}")

                client.publish(
                    topic_reglas(GRUPO),
                    json.dumps({
                        "regla": reg,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }),
                    qos=0
                )


            # ************************************************************
            # CASO E: CONSUMO DE LA TRANSICIÓN DE PRESENCIA
            # ************************************************************

            # Una transición de entrada o salida solo debe procesarse
            # una vez. Después de evaluar las reglas, sincroniza ambos
            # valores para impedir que vuelva a detectarse la transición.
            estado_habitacion["presencia_anterior"] = (
                estado_habitacion["presencia"]
            )


        # ************************************************************
        # CASO F: ESTADOS CONFIRMADOS POR LOS ACTUADORES
        # ************************************************************

        elif "/actuador/" in topic and topic.endswith("/estado"):

            tipo_act = topic.split("/")[-2]

            if tipo_act in ["bombilla", "persiana"]:

                # Interpreta el estado confirmado por el actuador.
                if payload_str.startswith("{"):

                    estado_act = str(
                        json.loads(payload_str).get("estado", "")
                    ).strip().upper()

                else:
                    estado_act = payload_str.strip().upper()

                # Actualiza el estado conocido del actuador.
                # No se vuelven a evaluar las reglas por este mensaje.
                if estado_act:
                    estado_habitacion[tipo_act] = estado_act


    except Exception as e:

        print(f"Error procesando evento: {e}")


# ************************************************************
#    5.- FUNCIÓN PRINCIPAL DE INICIALIZACIÓN Y EJECUCIÓN
# ************************************************************

def main():
    """Configura la conexión inicial e inicia el bucle permanente de escucha."""

    print("=" * 65)
    print(f"MOTOR DE REGLAS DOMÓTICAS (Grupo: {GRUPO})")
    print("=" * 65)

    # Crea el cliente MQTT con un identificador asociado al grupo.
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"reglas-{GRUPO}"
    )

    # Asigna los callbacks de conexión y recepción.
    client.on_connect = on_connect
    client.on_message = on_message

    # Establece la conexión con el broker MQTT.
    client.connect(
        BROKER_DEFAULT,
        PUERTO_DEFAULT,
        keepalive=60
    )

    # Mantiene el motor escuchando mensajes hasta que se interrumpa.
    try:
        client.loop_forever()

    except KeyboardInterrupt:

        print("\nDeteniendo el motor de reglas...")
        client.disconnect()


if __name__ == "__main__":
    main()
