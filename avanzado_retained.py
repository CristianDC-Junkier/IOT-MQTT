
#!/usr/bin/env python3
"""
Script automatizado de demostración del funcionamiento de los mensajes
retenidos (Retained Messages) de MQTT para la Práctica 2 IoT.
"""

import sys
import time
import threading
import paho.mqtt.client as mqtt

from config import BROKER_DEFAULT, PUERTO_DEFAULT, GRUPO_DEFAULT


# ********************************************************************
#     1.- CONFIGURACIÓN DE LA DEMOSTRACIÓN
# ********************************************************************

GRUPO = sys.argv[1] if len(sys.argv) > 1 else GRUPO_DEFAULT

TOPIC_EFIMERO = f"iotlab26/{GRUPO}/demo/sensor_efimero"
TOPIC_RETENIDO = f"iotlab26/{GRUPO}/demo/actuador_estado"

TIEMPO_ESPERA = 5

# Se almacenan los mensajes recibidos por el nuevo suscriptor para
# comprobar posteriormente cuáles han sido entregados por el broker.
mensajes_recibidos = []

evento_conexion_pub = threading.Event()
evento_conexion_sub = threading.Event()
evento_suscripcion = threading.Event()


# ********************************************************************
#     2.- CALLBACKS DE CONEXIÓN MQTT
# ********************************************************************

def on_connect_publicador(client, userdata, flags, reason_code, properties):
    """
    Callback ejecutado cuando el publicador establece conexión
    con el broker MQTT.
    """

    if reason_code == 0:
        evento_conexion_pub.set()
        print("[MQTT] Publicador conectado correctamente.")
    else:
        print(f"[ERROR] No se pudo conectar el publicador: {reason_code}")


def on_connect_suscriptor(client, userdata, flags, reason_code, properties):
    """
    Callback ejecutado cuando el nuevo suscriptor establece conexión
    con el broker MQTT.
    """

    if reason_code == 0:
        evento_conexion_sub.set()
        print("[MQTT] Nuevo suscriptor conectado correctamente.")
    else:
        print(f"[ERROR] No se pudo conectar el suscriptor: {reason_code}")


# ********************************************************************
#     3.- CALLBACKS DE RECEPCIÓN Y SUSCRIPCIÓN
# ********************************************************************

def on_message_suscriptor(client, userdata, msg):
    """
    Callback que registra los mensajes recibidos por el nuevo suscriptor,
    incluyendo su tópico, contenido y condición de mensaje retenido.
    """

    payload = msg.payload.decode("utf-8", errors="replace")

    mensajes_recibidos.append(
        (msg.topic, payload, msg.retain)
    )

    print(
        f"   [NUEVO SUSCRIPTOR] Recibido en [{msg.topic}] -> "
        f"{payload} (Retained: {msg.retain})"
    )


def on_subscribe(client, userdata, mid, reason_code_list, properties):
    """
    Callback ejecutado cuando el broker confirma la suscripción
    del nuevo cliente a los tópicos de prueba.
    """

    evento_suscripcion.set()


# ********************************************************************
#     4.- CONEXIÓN DE LOS CLIENTES MQTT
# ********************************************************************

def conectar_cliente(client, evento_conexion, nombre):
    """
    Establece la conexión con el broker e inicia el bucle de red
    de Paho para gestionar los mensajes y callbacks MQTT.
    La función espera a que se confirme la conexión antes de continuar,
    evitando depender exclusivamente de pausas de tiempo arbitrarias.
    """

    client.connect(
        BROKER_DEFAULT,
        PUERTO_DEFAULT,
        keepalive=60
    )

    client.loop_start()

    if not evento_conexion.wait(TIEMPO_ESPERA):
        raise TimeoutError(
            f"No se ha podido establecer la conexión MQTT del {nombre}."
        )


# ********************************************************************
#     5.- PREPARACIÓN Y PUBLICACIÓN DE LOS MENSAJES
# ********************************************************************

def limpiar_mensajes_anteriores(client):
    """
    Elimina posibles mensajes retenidos de ejecuciones anteriores.
    Para borrar un mensaje retenido se publica un payload vacío
    utilizando retain=True en el mismo tópico.
    """

    print("[PREPARACIÓN] Limpiando posibles mensajes retenidos anteriores...")

    for topic in (TOPIC_EFIMERO, TOPIC_RETENIDO):
        info = client.publish(
            topic,
            payload="",
            qos=1,
            retain=True
        )

        info.wait_for_publish(timeout=TIEMPO_ESPERA)

        if not info.is_published():
            raise TimeoutError(
                f"No se pudo limpiar el mensaje retenido de {topic}."
            )


def publicar_mensajes(client):
    """
    Publica dos mensajes diferentes para comprobar el funcionamiento
    de los mensajes retenidos en MQTT.
    El primer mensaje se publica con retain=False, por lo que el broker
    no lo conservará para futuros suscriptores.
    El segundo mensaje se publica con retain=True, por lo que el broker
    almacenará su último valor y lo entregará a nuevos suscriptores.
    """

    print("\n[PASO 1] Publicando mensajes...")

    mensajes = [
        (TOPIC_EFIMERO, "Sensor: 21.5 C", False),
        (TOPIC_RETENIDO, "Actuador: ON", True)
    ]

    for topic, payload, retain in mensajes:
        info = client.publish(
            topic,
            payload=payload,
            qos=1,
            retain=retain
        )

        info.wait_for_publish(timeout=TIEMPO_ESPERA)

        if not info.is_published():
            raise TimeoutError(
                f"No se pudo publicar el mensaje en {topic}."
            )

        print(
            f"   [PUBLICACIÓN] {topic} -> {payload} "
            f"(Retained: {retain})"
        )


# ********************************************************************
#     6.- DESCONEXIÓN DEL PUBLICADOR ORIGINAL
# ********************************************************************

def desconectar_publicador(client):
    """
    Desconecta el publicador original después de completar las
    publicaciones.
    El broker conserva el mensaje retenido aunque el cliente que
    lo publicó ya no permanezca conectado.
    """

    print(
        "\n[PASO 2] El publicador original finaliza y se desconecta "
        "del broker.\n"
    )

    client.loop_stop()
    client.disconnect()


# ********************************************************************
#     7.- CONEXIÓN Y SUSCRIPCIÓN DEL NUEVO CLIENTE
# ********************************************************************

def suscribir_nuevo_cliente():
    """
    Crea un nuevo cliente MQTT y lo suscribe a los dos tópicos de prueba.
    Como el publicador original ya está desconectado, el broker entregará
    únicamente los mensajes que conserve como retenidos.
    """

    print(
        "[PASO 3] Conectando un NUEVO SUSCRIPTOR al broker "
        "tras la desconexión..."
    )

    client_id = f"demo-sub-{time.time_ns()}"

    client_sub = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id
    )

    client_sub.on_connect = on_connect_suscriptor
    client_sub.on_subscribe = on_subscribe
    client_sub.on_message = on_message_suscriptor

    conectar_cliente(
        client_sub,
        evento_conexion_sub,
        "nuevo suscriptor"
    )

    resultado, mid = client_sub.subscribe(
        [
            (TOPIC_EFIMERO, 1),
            (TOPIC_RETENIDO, 1)
        ]
    )

    if resultado != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError("No se pudieron solicitar las suscripciones.")

    if not evento_suscripcion.wait(TIEMPO_ESPERA):
        raise TimeoutError(
            "El broker no ha confirmado las suscripciones."
        )

    # Esperamos a que el broker entregue los mensajes retenidos.
    time.sleep(2)

    return client_sub


# ********************************************************************
#     8.- COMPROBACIÓN DE LOS RESULTADOS
# ********************************************************************

def comprobar_resultado():
    """
    Comprueba los mensajes recibidos por el nuevo suscriptor y determina
    si el comportamiento de los mensajes retenidos es el esperado.
    """

    print("\n" + "=" * 70)
    print("RESULTADO DE LA PRUEBA:")
    print("=" * 70)

    topics_con_mensaje = [
        mensaje[0]
        for mensaje in mensajes_recibidos
    ]

    mensaje_efimero = TOPIC_EFIMERO in topics_con_mensaje
    mensaje_retenido = TOPIC_RETENIDO in topics_con_mensaje

    if mensaje_retenido and not mensaje_efimero:
        print(
            "EXITO: El nuevo suscriptor SOLO ha recibido "
            "el mensaje retenido."
        )

        print(
            """El mensaje efímero no se entregó porque no había """
            """ningún suscriptor cuando se publicó."""
        )

    elif mensaje_retenido and mensaje_efimero:
        print(
            "ERROR: Se han recibido ambos mensajes. "
            "El mensaje efímero no debería estar almacenado."
        )

    elif not mensaje_retenido and not mensaje_efimero:
        print(
            "ERROR: El nuevo suscriptor no ha recibido "
            "ninguno de los mensajes."
        )

    else:
        print(
            "ERROR: Se ha recibido el mensaje efimero, "
            "pero no el mensaje retenido."
        )

    print("=" * 70)


# ********************************************************************
#     9.- FINALIZACIÓN DE LOS CLIENTES MQTT
# ********************************************************************

def desconectar_cliente(client):
    """
    Detiene el bucle de red y desconecta el cliente MQTT de forma
    ordenada para liberar los recursos utilizados.
    """

    if client is not None:
        client.loop_stop()
        client.disconnect()


# ********************************************************************
#     10.- EJECUCIÓN PRINCIPAL DE LA DEMOSTRACIÓN
# ********************************************************************

def main():
    """
    Ejecuta las distintas fases de la demostración:

    1. Conecta el publicador original.
    2. Limpia posibles mensajes retenidos anteriores.
    3. Publica un mensaje efímero y otro retenido.
    4. Desconecta el publicador.
    5. Conecta un nuevo suscriptor.
    6. Comprueba los mensajes recibidos.
    7. Desconecta el nuevo suscriptor.
    """

    client_pub = None
    client_sub = None

    print("=" * 70)
    print(
        f"DEMOSTRACIÓN AUTOMATIZADA DE MENSAJES RETENIDOS "
        f"(Grupo: {GRUPO})"
    )
    print("=" * 70)

    try:
        # Creamos y conectamos el publicador original.
        client_pub_id = f"demo-pub-{time.time_ns()}"

        client_pub = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_pub_id
        )

        client_pub.on_connect = on_connect_publicador

        conectar_cliente(
            client_pub,
            evento_conexion_pub,
            "publicador"
        )

        # Publicamos los mensajes de prueba y desconectamos el emisor.
        limpiar_mensajes_anteriores(client_pub)
        publicar_mensajes(client_pub)

        desconectar_publicador(client_pub)
        client_pub = None

        # Simulamos el paso del tiempo con el emisor apagado.
        time.sleep(2)

        # Conectamos un nuevo cliente y comprobamos los mensajes.
        client_sub = suscribir_nuevo_cliente()

        comprobar_resultado()

    except KeyboardInterrupt:
        print("\n[INFO] Demostración interrumpida por el usuario.")

    except Exception as error:
        print(f"\n[ERROR] Error durante la demostración: {error}")

    finally:
        desconectar_cliente(client_pub)
        desconectar_cliente(client_sub)


if __name__ == "__main__":
    main()
