#!/usr/bin/env python3
"""
Script automatizado de demostración y prueba del funcionamiento de
Last Will and Testament (LWT) y Keepalive para la Práctica 2 IoT.
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

# Se utiliza un identificador único para evitar interferencias entre
# diferentes ejecuciones de la demostración.
SESION_ID = int(time.time())

TOPIC_LWT = f"iotlab26/{GRUPO}/demo/todo_en_uno_{SESION_ID}/lwt"

# Se registra el instante en el que el monitor recibe el testamento.
tiempo_lwt_recibido = None


# ********************************************************************
#     2.- CALLBACK DE RECEPCIÓN DEL MONITOR MQTT
# ********************************************************************

def on_message_monitor(client, userdata, msg):
    """
    Callback ejecutado cuando el monitor recibe un mensaje en el tópico
    LWT. Registra el contenido recibido y el instante de recepción.

    Cuando el broker publica OFFLINE, se almacena el momento exacto
    para calcular posteriormente el tiempo de detección de la caída.
    """

    global tiempo_lwt_recibido

    payload = msg.payload.decode(
        "utf-8",
        errors="replace"
    )

    ahora = time.strftime("%H:%M:%S")

    print(
        f"   [MONITOR] [{ahora}] Recibido en [{msg.topic}] -> {payload}"
    )

    if payload == "OFFLINE":
        tiempo_lwt_recibido = time.time()


# ********************************************************************
#     3.- EJECUCIÓN PRINCIPAL DE LA DEMOSTRACIÓN
# ********************************************************************

def main():
    """
    Ejecuta las distintas fases de la demostración:

    1. Inicia un monitor MQTT para escuchar el tópico LWT.
    2. Conecta un sensor emulado con Keepalive y LWT configurados.
    3. Publica el estado ONLINE inicial.
    4. Simula una pérdida repentina de conexión.
    5. Espera a que el broker publique automáticamente el testamento.
    6. Calcula el tiempo de detección y muestra los resultados.
    """

    global tiempo_lwt_recibido

    tiempo_lwt_recibido = None

    client_mon = None
    client_sensor = None

    print("=" * 70)
    print(
        f"DEMOSTRACIÓN COMPLETA Y UNIFICADA DE LWT Y KEEPALIVE "
        f"(Grupo: {GRUPO})"
    )
    print("=" * 70)

    try:

        # ************************************************************
        #     3.1.- INICIALIZACIÓN DEL MONITOR MQTT
        # ************************************************************

        print(
            "[FASE 1] Iniciando monitor interno para escuchar "
            "el testamento..."
        )

        client_mon_id = f"monitor-unico-{SESION_ID}"

        client_mon = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_mon_id
        )

        client_mon.on_message = on_message_monitor

        client_mon.connect(
            BROKER_DEFAULT,
            PUERTO_DEFAULT,
            keepalive=60
        )

        client_mon.loop_start()

        # El monitor se suscribe al tópico donde el broker publicará
        # automáticamente el testamento del sensor.
        client_mon.subscribe(
            TOPIC_LWT,
            qos=1
        )

        time.sleep(1)


        # ************************************************************
        #     3.2.- CONEXIÓN DEL SENSOR Y CONFIGURACIÓN DEL LWT
        # ************************************************************

        KEEPALIVE_SECS = 8

        print(
            f"[FASE 2] Conectando sensor emulado con "
            f"keepalive={KEEPALIVE_SECS}s..."
        )

        client_sensor_id = f"sensor-unico-{SESION_ID}"

        client_sensor = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_sensor_id
        )

        # Configuramos el testamento que publicará el broker si el
        # sensor pierde la conexión de forma inesperada.
        client_sensor.will_set(
            TOPIC_LWT,
            payload="OFFLINE",
            qos=1
        )

        client_sensor.connect(
            BROKER_DEFAULT,
            PUERTO_DEFAULT,
            keepalive=KEEPALIVE_SECS
        )

        client_sensor.loop_start()

        time.sleep(1)


        # ************************************************************
        #     3.3.- PUBLICACIÓN DEL ESTADO ONLINE
        # ************************************************************

        print(
            "[FASE 3] Publicando estado ONLINE inicial "
            "en el canal LWT..."
        )

        client_sensor.publish(
            TOPIC_LWT,
            payload="ONLINE",
            qos=1
        )

        time.sleep(2)


        # ************************************************************
        #     3.4.- SIMULACIÓN DE LA PÉRDIDA DE CONEXIÓN
        # ************************************************************

        print("\n" + "=" * 70)

        print(
            "[FASE 4] SIMULANDO APAGÓN: Congelando el envío "
            "de PINGs del sensor..."
        )

        print(
            "El sensor deja de enviar pings al broker sin cerrar "
            "el socket limpiamente."
        )

        print("=" * 70)

        # Detenemos bruscamente el bucle del sensor que se encargaba
        # de gestionar los paquetes PINGREQ de Keepalive.
        client_sensor.loop_stop()

        inicio_cronometro = time.time()

        print(
            f"Cronómetro iniciado. Esperando a que el broker detecte "
            f"la expiración ({KEEPALIVE_SECS}s + margen)..."
        )

        # Esperamos hasta que el monitor reciba el mensaje OFFLINE.
        # El margen adicional permite contemplar el tiempo de detección
        # que necesita el broker para considerar perdida la conexión.
        tiempo_maximo_espera = KEEPALIVE_SECS + 10

        tiempo_lwt_recibido = None

        while (time.time() - inicio_cronometro) < tiempo_maximo_espera:

            if tiempo_lwt_recibido is not None:
                break

            time.sleep(0.2)


        # ************************************************************
        #     3.5.- COMPROBACIÓN DE LOS RESULTADOS
        # ************************************************************

        print("\n" + "=" * 70)
        print("RESULTADO DE LA DEMOSTRACIÓN UNIFICADA:")
        print("=" * 70)

        if tiempo_lwt_recibido is not None:

            duracion_real = (
                tiempo_lwt_recibido - inicio_cronometro
            )

            print(
                f"EXITO: El broker detectó la caída automática "
                f"tras {duracion_real:.2f} segundos."
            )

            print(
                "El temporizador de Keepalive expiró y el broker "
                "activó el testamento (LWT) correctamente."
            )

        else:

            print(
                "AVISO: Se agotó el tiempo máximo de espera "
                "sin recibir el LWT."
            )

        print("=" * 70)

    except KeyboardInterrupt:

        print("\n[INFO] Demostración interrumpida por el usuario.")

    except Exception as error:

        print(f"\n[ERROR] Error durante la demostración: {error}")

    finally:

        # ************************************************************
        #     3.6.- FINALIZACIÓN DE LOS CLIENTES MQTT
        # ************************************************************

        # El sensor se desconecta al finalizar la prueba para liberar
        # los recursos utilizados durante la simulación.
        if client_sensor is not None:
            client_sensor.loop_stop()
            client_sensor.disconnect()

        # El monitor finaliza mediante una desconexión ordenada.
        if client_mon is not None:
            client_mon.loop_stop()
            client_mon.disconnect()

if __name__ == "__main__":
    main()
