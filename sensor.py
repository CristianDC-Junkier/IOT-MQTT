
#!/usr/bin/env python3
"""Módulo de Sensor Virtual para la Práctica 2 IoT."""

import argparse
import csv
import json
import os
import time
import paho.mqtt.client as mqtt

from config import (
    BROKER_DEFAULT,
    PUERTO_DEFAULT,
    GRUPO_DEFAULT,
    topic_sensor,
)


# ********************************************************************
#             1.- CONFIGURACIÓN Y UNIDADES DE LOS SENSORES
# ********************************************************************

# Diccionario que relaciona cada sensor con su unidad de medida.
# Se utiliza para completar los mensajes publicados mediante MQTT
# y mostrar las lecturas por consola.

UNIDADES = {
    "luz": "lux",
    "humedad": "%",
    "temperatura": "C",
    "presencia": "binario",
}


# ********************************************************************
#                  2.- GESTIÓN DE ARGUMENTOS
# ********************************************************************

def validar_periodo(valor):
    """
    Valida que el periodo de publicación introducido sea positivo.
    Evita iniciar el sensor con intervalos nulos o negativos.
    """

    try:
        periodo = float(valor)

    except ValueError:
        raise argparse.ArgumentTypeError(
            "El periodo debe ser un número válido."
        )

    if periodo <= 0:
        raise argparse.ArgumentTypeError(
            "El periodo debe ser mayor que cero."
        )

    return periodo


def parse_args():
    """
    Configura los parámetros permitidos al ejecutar el sensor.
    Permite seleccionar el tipo de sensor, grupo MQTT, periodo de publicación,
    fichero CSV y datos de conexión con el broker.
    """

    parser = argparse.ArgumentParser(
        description="Emulador de Sensor IoT"
    )

    # Identifica el sensor que se desea ejecutar.
    parser.add_argument(
        "--tipo",
        type=str,
        required=True,
        choices=["luz", "humedad", "temperatura", "presencia"],
        help="Tipo de sensor que se desea iniciar",
    )

    # Identificador del grupo utilizado para construir los tópicos MQTT.
    parser.add_argument(
        "--grupo",
        type=str,
        default=GRUPO_DEFAULT,
        help="Identificador del grupo",
    )

    # Intervalo de tiempo entre publicaciones consecutivas.
    parser.add_argument(
        "--periodo",
        type=validar_periodo,
        default=2.0,
        help="Periodo de publicación en segundos",
    )

    # Permite especificar manualmente el fichero CSV de lecturas.
    parser.add_argument(
        "--fichero",
        type=str,
        default=None,
        help="Ruta del fichero CSV con los datos del sensor",
    )

    # Parámetros de conexión con el broker MQTT.
    parser.add_argument(
        "--broker",
        type=str,
        default=BROKER_DEFAULT,
        help="Dirección del broker MQTT",
    )

    parser.add_argument(
        "--puerto",
        type=int,
        default=PUERTO_DEFAULT,
        help="Puerto de conexión del broker MQTT",
    )

    return parser.parse_args()


# ********************************************************************
#                3.- LECTURA Y VALIDACIÓN DE DATOS CSV
# ********************************************************************


def leer_datos_csv(ruta_fichero, tipo_sensor):
    """
    Lee las lecturas correspondientes al sensor seleccionado.
    El fichero puede contener una columna específica para el sensor
    o una columna genérica denominada "valor".
    Las lecturas se convierten a valores numéricos para poder publicarlas
    posteriormente en los mensajes MQTT.

    """

    valores = []

    # Comprueba que el fichero indicado exista antes de intentar leerlo.
    if not os.path.isfile(ruta_fichero):
        raise FileNotFoundError(
            f"No se encontró el fichero: {ruta_fichero}"
        )

    with open(
        ruta_fichero,
        mode="r",
        encoding="utf-8-sig",
        newline="",
    ) as fichero:

        lector = csv.DictReader(fichero)

        # Comprueba qué columna contiene las lecturas del sensor.
        if lector.fieldnames is None:
            raise ValueError(
                f"El fichero CSV está vacío o no contiene cabeceras: {ruta_fichero}"
            )

        if tipo_sensor in lector.fieldnames:
            columna = tipo_sensor

        elif "valor" in lector.fieldnames:
            columna = "valor"

        else:
            raise ValueError(
                f"El fichero CSV no contiene una columna para "
                f"el sensor '{tipo_sensor}' ni una columna 'valor'."
            )

        # Recorre las filas del fichero y extrae las lecturas disponibles.
        for numero_fila, fila in enumerate(lector, start=2):

            contenido = fila.get(columna)

            # Ignora las filas que no contienen ningún valor.
            if contenido is None or not contenido.strip():
                continue

            try:

                # La presencia utiliza valores enteros (0 o 1).
                # El resto de sensores utilizan valores decimales.
                if tipo_sensor == "presencia":
                    valor = int(contenido.strip())

                    if valor not in (0, 1):
                        raise ValueError(
                            "La presencia debe ser 0 o 1."
                        )

                else:
                    valor = float(contenido.strip())

            except ValueError as error:
                raise ValueError(
                    f"Valor no válido en la fila {numero_fila} "
                    f"del fichero '{ruta_fichero}': {contenido}"
                ) from error

            valores.append(valor)

    # Evita iniciar un sensor que no tenga lecturas disponibles.
    if not valores:
        raise ValueError(
            f"No se encontraron lecturas válidas para el sensor "
            f"'{tipo_sensor}' en el fichero: {ruta_fichero}"
        )

    return valores


# ********************************************************************
#                4.- RESOLUCIÓN DEL FICHERO DE DATOS
# ********************************************************************



def obtener_ruta_csv(dir_actual, tipo_sensor, fichero_personalizado=None):
    """
    Determina qué fichero CSV debe utilizar el sensor.
    Se prioriza el fichero específico del sensor dentro de la carpeta data.
    Si no existe, se utiliza el fichero unificado de sensores.
    También se permite indicar una ruta personalizada mediante --fichero.
    """

    dir_data = os.path.join(dir_actual, "data")

    # Si se proporciona un fichero manualmente, utiliza su ruta.
    # Las rutas relativas se interpretan desde el directorio del proyecto.
    if fichero_personalizado:

        if os.path.isabs(fichero_personalizado):
            return fichero_personalizado

        return os.path.join(
            dir_actual,
            fichero_personalizado,
        )

    # Comprueba primero los ficheros específicos de cada sensor.
    ruta_dedicada = os.path.join(
        dir_data,
        f"datos_{tipo_sensor}.csv",
    )

    # Si no existe el fichero específico, busca el CSV unificado.
    ruta_unificada = os.path.join(
        dir_data,
        "datos_sensores.csv",
    )

    if os.path.isfile(ruta_dedicada):
        return ruta_dedicada

    if os.path.isfile(ruta_unificada):
        return ruta_unificada

    # Como alternativa, busca los ficheros en el directorio principal.
    ruta_dedicada_raiz = os.path.join(
        dir_actual,
        f"datos_{tipo_sensor}.csv",
    )

    ruta_unificada_raiz = os.path.join(
        dir_actual,
        "datos_sensores.csv",
    )

    if os.path.isfile(ruta_dedicada_raiz):
        return ruta_dedicada_raiz

    return ruta_unificada_raiz


# ********************************************************************
#             5.- CONFIGURACIÓN Y CONEXIÓN CON MQTT
# ********************************************************************


def conectar_mqtt(tipo_sensor, grupo, broker, puerto):
    """
    Crea el cliente MQTT asociado al sensor y al grupo correspondiente.
    También configura el mensaje LWT (Last Will and Testament), que permite
    informar al resto del sistema si el sensor pierde la conexión
    inesperadamente con el broker.
    """

    # Crea un identificador único para cada ejecución del sensor.
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"sensor-{tipo_sensor}-{grupo}-{int(time.time())}",
    )

    # Obtiene los tópicos utilizados para publicar las lecturas
    # y comunicar el estado de conexión del sensor.
    topic = topic_sensor(tipo_sensor, grupo)
    topic_lwt = f"iotlab26/{grupo}/sensor/{tipo_sensor}/lwt"

    # Configura el mensaje que el broker publicará automáticamente
    # si detecta una desconexión inesperada del sensor.
    client.will_set(
        topic_lwt,
        payload="OFFLINE",
        qos=1,
        retain=True,
    )

    # Establece la conexión con el broker MQTT.
    client.connect(
        broker,
        puerto,
        keepalive=60,
    )

    # Inicia el bucle de comunicación en segundo plano.
    client.loop_start()

    # Publica el estado ONLINE para indicar que el sensor está disponible.
    info = client.publish(
        topic_lwt,
        payload="ONLINE",
        qos=1,
        retain=True,
    )

    # Espera a que el mensaje de conexión se haya enviado.
    info.wait_for_publish(timeout=5)

    return client, topic, topic_lwt


# ********************************************************************
#             6.- PUBLICACIÓN DE LECTURAS DEL SENSOR
# ********************************************************************


def publicar_datos(client, topic, tipo, grupo, periodo, datos):
    """
    Recorre cíclicamente las lecturas obtenidas del fichero CSV.
    Cada publicación contiene el tipo de sensor, el valor medido,
    su unidad, la fecha de registro y el grupo al que pertenece.
    """
    indice = 0
    total = len(datos)
    unidad = UNIDADES.get(tipo, "")

    print(f"Sensor {tipo.upper()} iniciado correctamente.")
    print(f"Tópico MQTT: {topic}")
    print(f"Lecturas disponibles: {total}")
    print(f"Periodo de publicación: {periodo} s")
    print("-" * 65)

    # Mantiene la publicación activa hasta que se interrumpa el programa.
    while True:

        # Recupera la siguiente lectura del fichero CSV.
        valor_actual = datos[indice]

        # Genera la marca temporal de la publicación.
        ahora_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Construye el mensaje JSON que recibirá el resto del sistema.
        payload = {
            "sensor": tipo,
            "valor": valor_actual,
            "unidad": unidad,
            "timestamp": ahora_str,
            "grupo": grupo,
        }

        # Publica la lectura en el tópico correspondiente al sensor.
        client.publish(
            topic,
            json.dumps(payload, ensure_ascii=False),
            qos=0,
        )

        print(
            f"[{ahora_str}] Publicando "
            f"{tipo.upper()}: {valor_actual} {unidad}"
        )

        # Avanza a la siguiente lectura y vuelve al principio del CSV
        # cuando se alcanza el final del fichero.
        indice = (indice + 1) % total

        # Espera hasta la siguiente publicación.
        time.sleep(periodo)


# ********************************************************************
#            7.- CIERRE Y DESCONEXIÓN DEL SENSOR
# ********************************************************************




def desconectar_mqtt(client, topic_lwt):
    """
    Publica el estado OFFLINE antes de cerrar la conexión.
    De esta forma, el controlador puede conocer que el sensor
    ha finalizado su ejecución de manera ordenada.
    Si se produce una desconexión inesperada, el broker utilizará
    el mensaje LWT configurado durante la conexión.
    """

    try:

        if client.is_connected():

            # Comunica que el sensor ha dejado de estar disponible.
            info = client.publish(
                topic_lwt,
                payload="OFFLINE",
                qos=1,
                retain=True,
            )

            # Espera a que se publique el último mensaje de estado.
            info.wait_for_publish(timeout=5)

    except Exception as error:

        print(f"Error publicando el estado OFFLINE: {error}")

    finally:

        # Detiene el bucle de comunicación y libera la conexión MQTT.
        client.loop_stop()

        if client.is_connected():
            client.disconnect()


# ********************************************************************
#       8.- FUNCIÓN PRINCIPAL DE INICIALIZACIÓN Y EJECUCIÓN
# ********************************************************************

def main():
    """Configura el sensor, carga sus lecturas e inicia la publicación."""

    client = None
    topic_lwt = None

    try:

        # Recupera los parámetros de ejecución del sensor.
        args = parse_args()

        tipo = args.tipo
        grupo = args.grupo
        periodo = args.periodo

        # Obtiene el directorio del proyecto y resuelve la ruta del CSV.
        dir_actual = os.path.dirname(os.path.abspath(__file__))

        ruta_csv = obtener_ruta_csv(
            dir_actual,
            tipo,
            args.fichero,
        )

        # Carga las lecturas que utilizará el sensor durante su ejecución.
        datos = leer_datos_csv(
            ruta_csv,
            tipo,
        )

        # Muestra la configuración inicial del sensor.
        print("=" * 65)
        print(f"SENSOR VIRTUAL: {tipo.upper()} (Grupo: {grupo})")
        print("=" * 65)
        print(f"Fichero de datos: {ruta_csv}")
        print(f"Broker MQTT: {args.broker}:{args.puerto}")

        # Establece la conexión MQTT y anuncia que el sensor está disponible.
        client, topic, topic_lwt = conectar_mqtt(
            tipo,
            grupo,
            args.broker,
            args.puerto,
        )

        print("Sensor conectado exitosamente a HiveMQ.")

        # Inicia la publicación cíclica de las lecturas del CSV.
        publicar_datos(
            client,
            topic,
            tipo,
            grupo,
            periodo,
            datos,
        )

    except KeyboardInterrupt:

        # Captura la interrupción del teclado para finalizar
        # la ejecución del sensor de manera ordenada.
        print("\nDeteniendo el sensor...")

    except Exception as error:

        # Informa de los errores de lectura, configuración o conexión
        # sin ocultar el motivo por el que no se ha iniciado el sensor.
        print(f"Error en el sensor: {error}")

    finally:

        # Garantiza la desconexión MQTT tanto si el sensor termina
        # por una interrupción como si se produce un error durante
        # su ejecución.
        if client is not None:
            desconectar_mqtt(
                client,
                topic_lwt,
            )

if __name__ == "__main__":
    main()
