#!/usr/bin/env python3
"""Demostración de sesiones persistentes y caducidad de mensajes MQTT 5.0."""

import sys
import time
import threading
import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
from config import BROKER_DEFAULT, PUERTO_DEFAULT, GRUPO_DEFAULT


# ********************************************************************
#          1.- CONFIGURACIÓN GENERAL DEL SISTEMA
# ********************************************************************

GRUPO = sys.argv[1] if len(sys.argv) > 1 else GRUPO_DEFAULT

KEEPALIVE = 60
SESSION_EXPIRY = 300

# Tiempo de caducidad de cada orden, expresado en segundos.
EXPIRACION_ORDEN_1 = 30
EXPIRACION_ORDEN_2 = 60
EXPIRACION_ORDEN_3 = 3

# Tiempo que permanece apagado el actuador antes de reconectarse.
TIEMPO_ESPERA = 6

TIMEOUT_CONEXION = 15
TIMEOUT_SUSCRIPCION = 15
TIMEOUT_RECEPCION = 10

# Se reutiliza el mismo Client ID para recuperar la sesión persistente.
CLIENT_ID_ACTUADOR = f"actuador-persistente-{GRUPO}-{time.time_ns()}"
CLIENT_ID_EMISOR = f"emisor-persistente-{GRUPO}-{time.time_ns()}"

TOPIC_ORDENES = f"iotlab26/{GRUPO}/demo/sesion_persistente"

# Orden 2 tiene la prioridad lógica más alta.
ORDENES = [
    ("Orden 1", EXPIRACION_ORDEN_1, 1),
    ("Orden 2", EXPIRACION_ORDEN_2, 3),
    ("Orden 3", EXPIRACION_ORDEN_3, 2),
]

mensajes_recibidos = []

conexion_evento = threading.Event()
suscripcion_evento = threading.Event()
mensajes_evento = threading.Event()

estado_conexion = {
    "codigo": None,
    "sesion_presente": False
}

estado_suscripcion = {
    "error": None
}


# ********************************************************************
#          2.- CONFIGURACIÓN DE PROPIEDADES MQTT 5.0
# ********************************************************************

def crear_propiedades_sesion():
    """
    Establece el tiempo durante el que el broker conservará la sesión
    del actuador mientras permanezca desconectado.
    """

    propiedades = Properties(PacketTypes.CONNECT)
    propiedades.SessionExpiryInterval = SESSION_EXPIRY

    return propiedades


def crear_propiedades_caducidad(expiracion):
    """
    Define el tiempo máximo que el broker conservará una orden
    pendiente antes de descartarla.
    """

    propiedades = Properties(PacketTypes.PUBLISH)
    propiedades.MessageExpiryInterval = expiracion

    return propiedades


# ********************************************************************
#          3.- CALLBACKS DEL CLIENTE ACTUADOR
# ********************************************************************

def on_connect_actuador(client, userdata, flags, reason_code, properties):
    """
    Comprueba la conexión y recupera la suscripción si existe
    una sesión persistente anterior.
    """

    estado_conexion["codigo"] = reason_code
    estado_conexion["sesion_presente"] = flags.session_present

    if reason_code.is_failure:
        print(f"[ACTUADOR] Error de conexión: {reason_code}")
        conexion_evento.set()
        return

    print("[ACTUADOR] Conectado al broker.")

    if flags.session_present:
        print("[ACTUADOR] Sesión persistente recuperada.")
    else:
        print("[ACTUADOR] Nueva sesión. Suscribiendo al tópico...")

        resultado, _ = client.subscribe(TOPIC_ORDENES, qos=1)

        if resultado != mqtt.MQTT_ERR_SUCCESS:
            estado_suscripcion["error"] = "No se pudo realizar la suscripción."
            suscripcion_evento.set()

    conexion_evento.set()


def on_subscribe_actuador(client, userdata, mid, reason_code_list, properties):
    """Comprueba si el broker ha aceptado la suscripción."""

    for codigo in reason_code_list:
        if codigo.is_failure:
            estado_suscripcion["error"] = str(codigo)
            print(f"[ACTUADOR] Error en la suscripción: {codigo}")
            break

    suscripcion_evento.set()


def on_message_actuador(client, userdata, mensaje):
    """
    Procesa las órdenes recibidas y registra su contenido.
    Cuando llegan las dos órdenes que no han caducado, activa el evento.
    """

    orden = mensaje.payload.decode("utf-8")

    mensajes_recibidos.append(orden)

    print(f"[ACTUADOR] Orden recibida: {orden}")

    if len(mensajes_recibidos) >= 2:
        mensajes_evento.set()


# ********************************************************************
#          4.- CREACIÓN Y CONEXIÓN DEL ACTUADOR
# ********************************************************************

def crear_cliente_actuador():
    """Crea el cliente MQTT 5.0 encargado de recibir las órdenes."""

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID_ACTUADOR,
        protocol=mqtt.MQTTv5
    )

    client.on_connect = on_connect_actuador
    client.on_subscribe = on_subscribe_actuador
    client.on_message = on_message_actuador

    return client


def conectar_actuador(client, reconexion=False):
    """
    Conecta el actuador y espera a que el broker confirme la conexión.
    En la reconexión comprueba que se haya recuperado la sesión anterior.
    """

    conexion_evento.clear()
    suscripcion_evento.clear()

    estado_conexion["codigo"] = None
    estado_conexion["sesion_presente"] = False
    estado_suscripcion["error"] = None

    client.connect(
        BROKER_DEFAULT,
        PUERTO_DEFAULT,
        keepalive=KEEPALIVE,
        clean_start=False,
        properties=crear_propiedades_sesion()
    )

    client.loop_start()

    if not conexion_evento.wait(TIMEOUT_CONEXION):
        raise TimeoutError("El actuador no ha podido conectarse.")

    if estado_conexion["codigo"].is_failure:
        raise ConnectionError("El broker ha rechazado la conexión.")

    # En la primera conexión se espera a que termine la suscripción.
    if not reconexion and not estado_conexion["sesion_presente"]:
        if not suscripcion_evento.wait(TIMEOUT_SUSCRIPCION):
            raise TimeoutError("No se ha confirmado la suscripción.")

        if estado_suscripcion["error"]:
            raise ConnectionError(estado_suscripcion["error"])

    # Al reconectar, el broker debe recuperar la sesión anterior.
    if reconexion and not estado_conexion["sesion_presente"]:
        raise RuntimeError("No se ha recuperado la sesión persistente.")

    print("[ACTUADOR] Preparado para recibir órdenes.")


# ********************************************************************
#          5.- DESCONEXIÓN DEL ACTUADOR
# ********************************************************************

def desconectar_actuador(client):
    """
    Desconecta el actuador sin eliminar su sesión.
    El broker conservará las suscripciones y las órdenes pendientes.
    """

    print("\n[ACTUADOR] Desconectando temporalmente...")

    client.disconnect()
    client.loop_stop()

    print("[ACTUADOR] Desconectado. La sesión permanece almacenada.")


# ********************************************************************
#          6.- PUBLICACIÓN DE LAS TRES ÓRDENES
# ********************************************************************

def publicar_ordenes():
    """
    Publica las tres órdenes con QoS 1 y diferentes tiempos de caducidad.
    El broker almacenará las órdenes mientras el actuador esté desconectado.
    """

    conexion_emisor = threading.Event()

    def on_connect_emisor(client, userdata, flags, reason_code, properties):
        """Notifica cuándo el emisor ha conectado correctamente."""

        if reason_code.is_failure:
            print(f"[EMISOR] Error de conexión: {reason_code}")
        else:
            print("[EMISOR] Conectado al broker.")

        conexion_emisor.set()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID_EMISOR,
        protocol=mqtt.MQTTv5
    )

    client.on_connect = on_connect_emisor

    try:
        client.connect(
            BROKER_DEFAULT,
            PUERTO_DEFAULT,
            keepalive=KEEPALIVE
        )

        client.loop_start()

        if not conexion_emisor.wait(TIMEOUT_CONEXION):
            raise TimeoutError("El emisor no ha podido conectarse.")

        for nombre, expiracion, prioridad in ORDENES:

            # Cada publicación incluye su propio intervalo de caducidad.
            propiedades = crear_propiedades_caducidad(expiracion)

            print(
                f"[EMISOR] Publicando {nombre} | "
                f"Caducidad: {expiracion}s | "
                f"Prioridad: {prioridad}"
            )

            resultado = client.publish(
                TOPIC_ORDENES,
                payload=nombre,
                qos=1,
                retain=False,
                properties=propiedades
            )

            if resultado.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"No se pudo publicar {nombre}.")

            # Se espera al PUBACK para confirmar que el broker ha recibido
            # correctamente cada publicación QoS 1.
            resultado.wait_for_publish(timeout=TIMEOUT_CONEXION)

            if not resultado.is_published():
                raise TimeoutError(f"No se ha confirmado {nombre}.")

        print("[EMISOR] Las tres órdenes han sido publicadas.")

    finally:
        if client.is_connected():
            client.disconnect()

        client.loop_stop()


# ********************************************************************
#          7.- ESPERA A LA CADUCIDAD DE LOS MENSAJES
# ********************************************************************

def esperar_caducidad():
    """
    Mantiene apagado el actuador durante seis segundos.
    Durante este intervalo, la Orden 3 supera su tiempo de caducidad
    y el broker debe descartarla.
    """

    print(f"\n[SISTEMA] Esperando {TIEMPO_ESPERA} segundos...")

    time.sleep(TIEMPO_ESPERA)

    print("[SISTEMA] Tiempo de espera finalizado.")


# ********************************************************************
#          8.- RECEPCIÓN Y COMPROBACIÓN DE LAS ÓRDENES
# ********************************************************************

def esperar_mensajes():
    """Espera a que el actuador reciba las dos órdenes pendientes."""

    print("\n[ACTUADOR] Esperando las órdenes almacenadas...")

    if not mensajes_evento.wait(TIMEOUT_RECEPCION):
        print("[ACTUADOR] Ha finalizado el tiempo de espera de recepción.")


def comprobar_resultado():
    """
    Comprueba que las órdenes 1 y 2 se han recibido y que la Orden 3
    ha caducado antes de que el actuador volviera a conectarse.
    """

    print("\n" + "=" * 60)
    print("                 RESULTADO DE LA DEMOSTRACIÓN")
    print("=" * 60)

    for nombre, expiracion, prioridad in ORDENES:
        recibida = nombre in mensajes_recibidos

        print(
            f"{nombre:<10} | "
            f"Caducidad: {expiracion:>2}s | "
            f"Prioridad: {prioridad} | "
            f"{'RECIBIDA' if recibida else 'NO RECIBIDA'}"
        )

    resultado_correcto = (
        "Orden 1" in mensajes_recibidos
        and "Orden 2" in mensajes_recibidos
        and "Orden 3" not in mensajes_recibidos
    )

    print("-" * 60)

    if resultado_correcto:
        print("[OK] Las órdenes recibidas coinciden con lo esperado.")
    else:
        print("[AVISO] El resultado no coincide con lo esperado.")

    print("=" * 60)


# ********************************************************************
#          9.- LIBERACIÓN DE RECURSOS
# ********************************************************************

def finalizar_cliente(client):
    """Cierra la conexión MQTT y detiene el hilo de comunicación."""

    if client is not None:
        if client.is_connected():
            client.disconnect()

        client.loop_stop()


# ********************************************************************
#          10.- FUNCIÓN PRINCIPAL
# ********************************************************************

def main():
    """Ejecuta la demostración de sesiones persistentes y caducidad MQTT."""

    client_actuador = None

    try:
        # Indicamos el grupo y el topic
        print(f"[CONFIGURACIÓN] Grupo: {GRUPO}")
        print(f"[CONFIGURACIÓN] Tópico: {TOPIC_ORDENES}\n")

        # El actuador se conecta y establece su suscripción.
        client_actuador = crear_cliente_actuador()
        conectar_actuador(client_actuador)

        # Se desconecta conservando su sesión en el broker.
        desconectar_actuador(client_actuador)

        # El emisor publica las tres órdenes mientras está desconectado.
        publicar_ordenes()

        # Se espera a que caduque la Orden 3.
        esperar_caducidad()

        # El actuador recupera su sesión y recibe las órdenes pendientes.
        conectar_actuador(client_actuador, reconexion=True)

        esperar_mensajes()
        comprobar_resultado()

    except KeyboardInterrupt:
        print("\n[SISTEMA] Demostración interrumpida.")

    except Exception as error:
        print(f"\n[ERROR] {error}")

    finally:
        finalizar_cliente(client_actuador)
        print("[SISTEMA] Demostración finalizada.")

if __name__ == "__main__":
    main()