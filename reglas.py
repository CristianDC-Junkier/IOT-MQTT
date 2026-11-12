
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


# ********************************************************************
#     1.- GESTIÓN DE ARGUMENTOS Y CONFIGURACIÓN DEL SISTEMA
# ********************************************************************

# Captura el identificador del grupo por argumento de consola.
# Si no se proporciona, utiliza el grupo configurado por defecto.
# Ejemplo: python reglas.py g99

GRUPO = sys.argv[1] if len(sys.argv) > 1 else GRUPO_DEFAULT


# ********************************************************************
#                  2.- ESTADO GLOBAL DE LA ESTANCIA
# ********************************************************************

# Diccionario global que almacena las últimas lecturas recibidas
# de los sensores y el estado conocido de los actuadores.
#
# presencia_anterior permite detectar los cambios de presencia
# necesarios para ejecutar las reglas de entrada y salida.

estado_habitacion = {
    "luz": None,
    "humedad": None,
    "temperatura": None,
    "presencia": 0,
    "presencia_anterior": 0,
    "bombilla": "OFF",
    "persiana": "CERRADA"
}


# ********************************************************************
#              3.- EVALUACIÓN DE LAS REGLAS DOMÓTICAS
# ********************************************************************

def evaluar_reglas(e):
    """Evalúa las reglas domóticas según el estado actual y anterior.

    Reglas implementadas:
    - R1: Entrada de persona (0 a 1) Y Luz < 150 lux -> Bombilla ON.
      Justificación: Confort visual inmediato al acceder a una habitación oscura.
    - R2: Salida de persona (1 a 0) -> Bombilla OFF y Persiana CERRADA.
      Justificación: Eficiencia energética y seguridad cuando la estancia queda vacía.
    - R3: Humedad relativa > 70% -> Persiana ABIERTA.
      Justificación: Ventilación natural para disipar condensaciones o vapor.
    - R4: Luz natural > 600 lux Y Humedad < 40% -> Persiana CERRADA.
      Justificación: Protección solar pasiva contra el sobrecalentamiento.
    - R5: Presencia activa (1) Y Luz < 150 lux -> Bombilla ON.
      Justificación: Mantener la iluminación artificial si oscurece con usuarios dentro.
    """

    ordenes = {}
    reglas_disparadas = []

    # Recupera las últimas lecturas de los sensores y los actuadores.
    luz = e["luz"]
    humedad = e["humedad"]
    temperatura = e["temperatura"]
    presencia = e["presencia"]
    presencia_ant = e["presencia_anterior"]
    bombilla_actual = e["bombilla"]
    persiana_actual = e["persiana"]

    # Detecta las transiciones de entrada y salida de personas.
    ha_entrado = (presencia == 1 and presencia_ant == 0)
    ha_salido = (presencia == 0 and presencia_ant == 1)


    # *************************************************************
    # REGLA R2: SALIDA DE PERSONA -> APAGAR BOMBILLA Y CERRAR PERSIANA
    # *************************************************************

    # Cuando la presencia cambia de 1 a 0, se apaga la iluminación
    # y se cierra la persiana si alguno de los actuadores lo necesita.
    if ha_salido:

        if bombilla_actual != "OFF":
            ordenes["bombilla"] = "OFF"

        if persiana_actual != "CERRADA":
            ordenes["persiana"] = "CERRADA"

        reglas_disparadas.append("R2: Persona ha salido -> B OFF y P CER")


    # *************************************************************
    # REGLA R1: ENTRADA DE PERSONA CON POCA LUZ -> BOMBILLA ON
    # *************************************************************

    # Se activa cuando se detecta una entrada y la iluminación
    # disponible está por debajo del umbral de luz baja.
    if ha_entrado and luz is not None and luz < UMBRAL_LUZ_BAJA:

        if bombilla_actual != "ON":
            ordenes["bombilla"] = "ON"
            reglas_disparadas.append("R1: Entrada de persona con poca luz -> B ON")


    # *************************************************************
    # REGLA R5: PRESENCIA ACTIVA CON POCA LUZ -> BOMBILLA ON
    # *************************************************************

    # Se comprueba también cuando llega una nueva lectura de luz.
    # Así, si una persona ya está dentro y la iluminación disminuye,
    # se enciende la bombilla sin necesitar una nueva detección de presencia.
    #
    # Se utiliza elif para evitar activar simultáneamente R1 y R5
    # cuando la persona acaba de entrar con poca iluminación.
    elif presencia == 1 and luz is not None and luz < UMBRAL_LUZ_BAJA:

        if bombilla_actual != "ON":
            ordenes["bombilla"] = "ON"
            reglas_disparadas.append("R5: Presencia activa con poca luz -> B ON")


    # *************************************************************
    # REGLA R3: HUMEDAD ALTA -> ABRIR PERSIANA
    # *************************************************************

    # Si la humedad supera el umbral establecido, se abre la persiana
    # para favorecer la ventilación natural de la estancia.
    if humedad is not None and humedad > UMBRAL_HUMEDAD_ALTA:

        if persiana_actual != "ABIERTA":
            ordenes["persiana"] = "ABIERTA"
            reglas_disparadas.append("R3: Humedad alta -> P ABI")


    # *************************************************************
    # REGLA R4: MUCHA LUZ Y AIRE SECO -> CERRAR PERSIANA
    # *************************************************************

    # Si existe mucha luz natural y la humedad es baja, se cierra
    # la persiana para reducir la entrada de radiación solar.
    elif (
        luz is not None and luz > UMBRAL_LUZ_ALTA
        and humedad is not None and humedad < UMBRAL_HUMEDAD_BAJA
    ):

        if persiana_actual != "CERRADA":
            ordenes["persiana"] = "CERRADA"
            reglas_disparadas.append("R4: Mucha luz y aire seco -> P CER")

    return ordenes, reglas_disparadas


# ********************************************************************
#       4.- CALLBACKS DE MQTT (CONEXIÓN Y RECEPCIÓN DE MENSAJES)
# ********************************************************************

def on_connect(client, userdata, flags, rc, properties=None):
    """Callback que se ejecuta cuando el cliente se conecta al broker MQTT."""

    if rc == 0:

        # Obtiene el tópico base correspondiente al grupo configurado.
        base = topic_base(GRUPO)

        print("Motor de Reglas conectado exitosamente a HiveMQ")
        print(f"Suscrito a: {base}/sensor/# y {base}/actuador/+/estado")

        # Se suscribe a los canales de telemetría de los sensores
        # y a los estados confirmados de los actuadores.
        client.subscribe(f"{base}/sensor/#", qos=0)
        client.subscribe(f"{base}/actuador/+/estado", qos=1)

    else:
        print(f"Error de conexion al broker. Codigo rc={rc}")


def on_message(client, userdata, msg):
    """Callback ejecutado automáticamente al recibir un mensaje MQTT."""

    global estado_habitacion

    # Obtiene el tópico y decodifica el contenido recibido.
    topic = msg.topic
    payload_str = msg.payload.decode("utf-8", errors="replace")

    try:

        # *************************************************************
        # CASO A: MENSAJES PROCEDENTES DE LOS SENSORES
        # *************************************************************

        if "/sensor/" in topic:

            # Identifica el tipo de sensor a partir del último segmento.
            tipo_sensor = topic.split("/")[-1]

            # Solo procesa los sensores utilizados por el motor de reglas.
            if tipo_sensor in ["luz", "humedad", "temperatura", "presencia"]:

                # Intenta interpretar el contenido como un mensaje JSON.
                # Si no es JSON, utiliza directamente el valor recibido.
                if payload_str.startswith("{"):
                    datos = json.loads(payload_str)
                    valor = datos.get("valor")
                else:
                    valor = payload_str

                # Convierte la lectura a un valor numérico.
                valor = float(valor)

                # Actualiza el histórico de presencia antes de almacenar
                # el nuevo valor para poder detectar entradas y salidas.
                if tipo_sensor == "presencia":

                    estado_habitacion["presencia_anterior"] = (
                        estado_habitacion["presencia"]
                    )

                    estado_habitacion["presencia"] = int(valor)

                else:
                    # Actualiza la lectura del sensor correspondiente.
                    estado_habitacion[tipo_sensor] = valor


        # *************************************************************
        # CASO B: ESTADOS CONFIRMADOS POR LOS ACTUADORES
        # *************************************************************

        elif "/actuador/" in topic and topic.endswith("/estado"):

            # Identifica el actuador que ha publicado la confirmación.
            tipo_act = topic.split("/")[-2]

            # Solo se mantienen los estados de los actuadores utilizados
            # directamente por las reglas del sistema.
            if tipo_act in ["bombilla", "persiana"]:

                # Intenta extraer el estado desde un mensaje JSON.
                # Si no es JSON, utiliza directamente el texto recibido.
                if payload_str.startswith("{"):
                    estado_act = str(
                        json.loads(payload_str).get("estado", "")
                    ).strip().upper()

                else:
                    estado_act = payload_str.strip().upper()

                # Actualiza el último estado confirmado del actuador.
                if estado_act:
                    estado_habitacion[tipo_act] = estado_act


        # *************************************************************
        # CASO C: EVALUACIÓN Y PUBLICACIÓN DE LAS REGLAS
        # *************************************************************

        # Después de actualizar cualquier sensor o actuador,
        # se evalúan las reglas utilizando el estado más reciente.
        #
        # Esto permite que R5 se active cuando llega una nueva lectura
        # de luz y ya existe presencia en la habitación.
        ordenes, reglas = evaluar_reglas(estado_habitacion)

        # Publica las órdenes de control generadas hacia los actuadores.
        for act, nuevo_estado in ordenes.items():

            # Obtiene el tópico MQTT correspondiente al actuador.
            topic_set = topic_actuador_set(act, GRUPO)

            # Publica la orden con QoS 1 para solicitar su entrega.
            client.publish(topic_set, payload=nuevo_estado, qos=1)

            print(f"[ORDEN EMITIDA] -> {topic_set}: {nuevo_estado}")


        # *************************************************************
        # CASO D: PUBLICACIÓN DE AUDITORÍAS DE LAS REGLAS
        # *************************************************************

        # Publica las reglas que se han activado durante la evaluación.
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


    except Exception as e:

        # Informa de cualquier error durante el procesamiento
        # sin detener el funcionamiento del motor de reglas.
        print(f"Error procesando evento: {e}")


# ********************************************************************
#     5.- FUNCIÓN PRINCIPAL DE INICIALIZACIÓN Y EJECUCIÓN
# ********************************************************************

def main():
    """Configura la conexión inicial e inicia el bucle permanente de escucha."""

    # Muestra la información general del motor de reglas.
    print("=" * 65)
    print(f"MOTOR DE REGLAS DOMÓTICAS (Grupo: {GRUPO})")
    print("=" * 65)

    # Crea el cliente MQTT con un identificador asociado al grupo.
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"reglas-{GRUPO}"
    )

    # Asigna las funciones encargadas de gestionar la conexión
    # y la recepción de mensajes MQTT.
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

        # Desconecta ordenadamente el motor al recibir Ctrl+C.
        print("\nDeteniendo el motor de reglas...")
        client.disconnect()


if __name__ == "__main__":
    main()
