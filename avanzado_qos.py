
#!/usr/bin/env python3
"""Demostración avanzada de QoS 0, 1 y 2 y medición de latencia MQTT."""

import sys
import time
import threading
import statistics
import paho.mqtt.client as mqtt

from config import BROKER_DEFAULT, PUERTO_DEFAULT, GRUPO_DEFAULT


# ********************************************************************
#     1.- CONFIGURACIÓN GENERAL DEL SISTEMA
# ********************************************************************

GRUPO = sys.argv[1] if len(sys.argv) > 1 else GRUPO_DEFAULT

NUM_MENSAJES = 10
KEEPALIVE = 60

TOPIC_QOS = f"iotlab26/{GRUPO}/demo/qos_latencia"


# ********************************************************************
#     2.- CONEXIÓN CON EL BROKER MQTT
# ********************************************************************

def conectar_mqtt():
    """Crea el cliente MQTT y espera la confirmación de conexión."""

    conexion_evento = threading.Event()
    resultado_conexion = {"codigo": None}

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"qos-latencia-{GRUPO}-{int(time.time())}"
    )

    def on_connect(client, userdata, flags, reason_code, properties):
        resultado_conexion["codigo"] = reason_code
        conexion_evento.set()

        if reason_code == 0:
            print("[CONEXIÓN] HiveMQ ha aceptado la conexión.")
        else:
            print(f"[CONEXIÓN] HiveMQ ha rechazado la conexión: {reason_code}")

    client.on_connect = on_connect

    print("\n[CONEXIÓN] Conectando con el broker HiveMQ...")

    client.connect(
        BROKER_DEFAULT,
        PUERTO_DEFAULT,
        KEEPALIVE
    )

    client.loop_start()

    if not conexion_evento.wait(timeout=15):
        client.disconnect()
        client.loop_stop()
        raise TimeoutError(
            "HiveMQ no ha respondido a la solicitud de conexión."
        )

    if resultado_conexion["codigo"] != 0:
        client.disconnect()
        client.loop_stop()
        raise ConnectionError(
            f"HiveMQ ha rechazado la conexión: "
            f"{resultado_conexion['codigo']}"
        )

    print(f"[CONEXIÓN] Conectado a {BROKER_DEFAULT}:{PUERTO_DEFAULT}")
    print(f"[CONFIGURACIÓN] Grupo: {GRUPO}")
    print(f"[CONFIGURACIÓN] Tópico: {TOPIC_QOS}")

    return client


# ********************************************************************
#     3.- MEDICIÓN DE LATENCIA DE UNA PUBLICACIÓN
# ********************************************************************

def medir_publicacion(client, qos, numero):
    """Publica un mensaje y mide el tiempo de envío o confirmación."""

    mensaje = f"Mensaje {numero} - QoS {qos}"

    inicio = time.perf_counter()

    resultado = client.publish(
        TOPIC_QOS,
        payload=mensaje,
        qos=qos,
        retain=False
    )

    if resultado.rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(
            f"Error al publicar el mensaje {numero} con QoS {qos}: "
            f"{resultado.rc}"
        )

    resultado.wait_for_publish(timeout=15)

    if not resultado.is_published():
        raise TimeoutError(
            f"No se ha completado la publicación del mensaje {numero} "
            f"con QoS {qos}."
        )

    fin = time.perf_counter()

    latencia_ms = (fin - inicio) * 1000

    return latencia_ms


# ********************************************************************
#     4.- EJECUCIÓN DE LAS PRUEBAS PARA CADA NIVEL DE QoS
# ********************************************************************

def ejecutar_prueba_qos(client, qos):
    """Envía una ráfaga de mensajes y almacena sus tiempos."""

    latencias = []

    print("\n" + "=" * 65)
    print(f" PRUEBA QoS {qos} - {NUM_MENSAJES} MENSAJES")
    print("=" * 65)

    for numero in range(1, NUM_MENSAJES + 1):

        latencia = medir_publicacion(
            client,
            qos,
            numero
        )

        latencias.append(latencia)

        print(
            f"[QoS {qos}] Mensaje {numero:02d}/{NUM_MENSAJES} "
            f"-> {latencia:.3f} ms"
        )

    return latencias


# ********************************************************************
#     5.- CÁLCULO DE ESTADÍSTICAS
# ********************************************************************

def calcular_estadisticas(latencias):
    """Calcula la media, el mínimo, el máximo y la desviación típica."""

    media = statistics.mean(latencias)
    minimo = min(latencias)
    maximo = max(latencias)
    desviacion = statistics.stdev(latencias)

    return media, minimo, maximo, desviacion


# ********************************************************************
#     6.- PRESENTACIÓN DE RESULTADOS
# ********************************************************************

def mostrar_resultados(resultados):
    """Muestra una tabla comparativa de los tres niveles de QoS."""

    print("\n")
    print("=" * 90)
    print("                              RESULTADOS DE LATENCIA MQTT")
    print("=" * 90)

    print(
        f"{'QoS':<10}"
        f"{'Media (ms)':>15}"
        f"{'Mínimo (ms)':>17}"
        f"{'Máximo (ms)':>17}"
        f"{'Desv. típica':>17}"
    )

    print("-" * 90)

    for qos in (0, 1, 2):

        media, minimo, maximo, desviacion = calcular_estadisticas(
            resultados[qos]
        )

        print(
            f"{qos:<10}"
            f"{media:>15.3f}"
            f"{minimo:>17.3f}"
            f"{maximo:>17.3f}"
            f"{desviacion:>17.3f}"
        )

    print("=" * 90)

    print(f"\n[INFORMACIÓN] Mensajes por nivel de QoS: {NUM_MENSAJES}")
    print("[INFORMACIÓN] Unidad de medida: milisegundos (ms)")


# ********************************************************************
#     7.- DESCONEXIÓN DEL BROKER MQTT
# ********************************************************************

def desconectar_mqtt(client):
    """Detiene el bucle de red y cierra la conexión MQTT."""

    print("\n[DESCONEXIÓN] Cerrando conexión con HiveMQ...")

    client.disconnect()
    client.loop_stop()

    print("[DESCONEXIÓN] Cliente desconectado correctamente.")


# ********************************************************************
#     8.- FUNCIÓN PRINCIPAL
# ********************************************************************

def main():

    client = None

    try:

        client = conectar_mqtt()

        resultados = {}

        for qos in (0, 1, 2):

            resultados[qos] = ejecutar_prueba_qos(
                client,
                qos
            )

        mostrar_resultados(resultados)

    except KeyboardInterrupt:

        print("\n[INTERRUPCIÓN] Prueba detenida por el usuario.")

    except Exception as e:

        print(f"\n[ERROR] Se ha producido un error: {e}")

    finally:

        if client is not None:
            desconectar_mqtt(client)


if __name__ == "__main__":
    main()
