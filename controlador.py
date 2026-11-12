#!/usr/bin/env python3
"""Monitor, Visor de Eventos y Registro CSV para la Práctica 2 IoT.

Este script actúa como el nodo central de supervisión del sistema domótico:

1. Se suscribe mediante un comodín (#) a todos los tópicos del grupo MQTT.
2. Recibe y muestra los mensajes publicados por sensores, actuadores y
   el motor de reglas.
3. Mantiene actualizado en memoria el estado general de la estancia.
4. Muestra una tarjeta resumen con el estado actual de la casa:
   - Una única vez al iniciar el monitor.
   - Cuando recibe nuevas confirmaciones de estado de los actuadores,
     excepto las recibidas como mensajes retenidos al conectarse.
   - Cada vez que recibe una orden dirigida a un actuador.
5. Almacena de forma persistente los datos recibidos en ficheros CSV:
   - Un registro general consolidado de sensores y actuadores.
   - Un fichero individual para cada tipo de sensor.
"""

import csv
import json
import os
import sys
import time
import paho.mqtt.client as mqtt

from config import BROKER_DEFAULT, PUERTO_DEFAULT, GRUPO_DEFAULT, topic_todo


# ********************************************************************
#     1.- GESTIÓN DE ARGUMENTOS Y CONFIGURACIÓN DE RUTAS LOCALES
# ********************************************************************

# Permite especificar el grupo MQTT desde la línea de comandos.
# Si no se proporciona ningún argumento, se utiliza el grupo
# configurado por defecto en el módulo config.
# Ejemplo: python controlador.py g99

GRUPO = sys.argv[1] if len(sys.argv) > 1 else GRUPO_DEFAULT


# Define los directorios donde se almacenarán los registros generados.
# La carpeta output y su contenido están protegidos por el .gitignore.
CARPETA_OUTPUT = "output"
CARPETA_EVENTS = os.path.join(CARPETA_OUTPUT, "events")


# Define las rutas de los ficheros CSV de salida.
ARCHIVO_SNAPSHOT = os.path.join(CARPETA_OUTPUT, "registro_sensores.csv")

ARCHIVO_PRESENCIA = os.path.join(CARPETA_EVENTS, "presencia.csv")
ARCHIVO_TEMPERATURA = os.path.join(CARPETA_EVENTS, "temperatura.csv")
ARCHIVO_HUMEDAD = os.path.join(CARPETA_EVENTS, "humedad.csv")
ARCHIVO_LUZ = os.path.join(CARPETA_EVENTS, "luz.csv")


# Crea los directorios de almacenamiento si todavía no existen.
# exist_ok=True evita generar un error cuando ya están creados.
os.makedirs(CARPETA_OUTPUT, exist_ok=True)
os.makedirs(CARPETA_EVENTS, exist_ok=True)


# ********************************************************************
#                  2.- ESTADO GLOBAL DE LA ESTANCIA
# ********************************************************************

# Diccionario global que mantiene en memoria los últimos valores
# conocidos de los sensores, actuadores y reglas del sistema.

# Se inicializa con valores predeterminados para poder mostrar
# una primera tarjeta de estado antes de recibir mensajes MQTT.

estado_habitacion = {
    "luz": "--",
    "humedad": "--",
    "temperatura": "--",
    "presencia": "--",
    "presencia_valor": 0,
    "bombilla": "OFF",
    "persiana": "CERRADA",
    "ultima_regla": "Ninguna",
}


# ********************************************************************
#              3.- FUNCIONES DE VISUALIZACIÓN EN CONSOLA
# ********************************************************************

def imprimir_resumen_habitacion(hora_str):
    """Imprime una tarjeta resumen estructurada con el estado de la casa.
    Presenta conjuntamente los últimos valores conocidos de los
    sensores, los actuadores y la última regla evaluada.
    Se ejecuta una vez al iniciar el monitor y posteriormente
    cuando se reciben confirmaciones de estado de los actuadores
    o nuevas órdenes dirigidas a ellos.
    """

    # Convierte el valor numérico de presencia en un texto legible.
    pres_val = estado_habitacion["presencia_valor"]
    pres_str = "SI (1)" if pres_val == 1 else "NO (0)"

    # Define un ancho interior fijo para mantener alineada la tarjeta.
    linea_sup = "+" + "-" * 62 + "+"

    print()
    print(linea_sup)
    print(f"| ESTADO ACTUAL DE LA ESTANCIA | Grupo: {GRUPO:<5} | Hora: {hora_str} |")
    print(linea_sup)

    print(
        f"| - Luz       : {str(estado_habitacion['luz']):<12} "
        f"| Bombilla : {str(estado_habitacion['bombilla']):<20} |"
    )

    print(
        f"| - Humedad   : {str(estado_habitacion['humedad']):<12} "
        f"| Persiana : {str(estado_habitacion['persiana']):<20} |"
    )

    print(
        f"| - Temp      : {str(estado_habitacion['temperatura']):<12} "
        f"| Presencia: {pres_str:<20} |"
    )

    print(linea_sup)

    print(
        f"| - Ultima regla: "
        f"{str(estado_habitacion['ultima_regla'])[:44]:<44} |"
    )

    print(linea_sup + "\n")


# ********************************************************************
#      4.- CALLBACKS DE MQTT (CONEXIÓN Y RECEPCIÓN DE MENSAJES)
# ********************************************************************

def on_connect(client, userdata, flags, rc, properties=None):
    """Callback ejecutado automáticamente al establecer la conexión.
    Comprueba si la conexión se ha realizado correctamente y, en ese
    caso, suscribe el monitor a todos los tópicos del grupo MQTT.
    """

    if rc == 0:

        # Obtiene el tópico global del grupo utilizando el comodín #.
        topic = topic_todo(GRUPO)

        print("Monitor conectado exitosamente a HiveMQ")
        print(f"Escuchando actividad en: {topic}\n")

        # Suscripción con QoS 0 para recibir los mensajes del grupo.
        # El broker también puede entregar los últimos mensajes
        # retenidos publicados anteriormente en esos tópicos.
        client.subscribe(topic, qos=0)

    else:
        print(f"Error de conexion al broker. Codigo rc={rc}")


def on_message(client, userdata, msg):
    """Callback ejecutado automáticamente al recibir un mensaje MQTT.
    Identifica el origen del mensaje y realiza las operaciones
    correspondientes: actualizar el estado, mostrar información
    por consola o almacenar los datos en los ficheros CSV.
    """

    global estado_habitacion

    # Obtiene el tópico y decodifica el contenido recibido.
    # errors="replace" evita errores si existen caracteres no válidos.
    topic = msg.topic
    payload_str = msg.payload.decode("utf-8", errors="replace")

    # Obtiene la hora de recepción para identificar los eventos.
    ahora = time.strftime("%H:%M:%S")

    try:

        # *************************************************************
        # CASO A: MENSAJES PROCEDENTES DE LOS SENSORES VIRTUALES
        # *************************************************************

        if "/sensor/" in topic and not topic.endswith("/lwt"):

            # Identifica el tipo de sensor a partir del último segmento
            # del tópico MQTT (temperatura, humedad, presencia o luz).
            tipo_sensor = topic.split("/")[-1]

            # Intenta interpretar el contenido como un mensaje JSON.
            # Si falla, se considera que el payload contiene directamente
            # el valor del sensor en formato de texto.
            try:
                datos = json.loads(payload_str)

                valor = datos.get("valor", payload_str)
                unidad = datos.get("unidad", "")

            except Exception:
                valor = payload_str
                unidad = ""

            # Actualiza el último valor conocido del sensor,
            # incluyendo su unidad de medida cuando está disponible.
            estado_habitacion[tipo_sensor] = f"{valor} {unidad}".strip()

            # Mantiene un valor numérico auxiliar para la presencia.
            # Permite representar fácilmente el resultado como SI o NO.
            if tipo_sensor == "presencia":
                estado_habitacion["presencia_valor"] = int(float(valor))

            # Selecciona el fichero CSV individual correspondiente
            # al sensor que ha generado el mensaje.
            archivo_destino = None

            if tipo_sensor == "presencia":
                archivo_destino = ARCHIVO_PRESENCIA

            elif tipo_sensor == "temperatura":
                archivo_destino = ARCHIVO_TEMPERATURA

            elif tipo_sensor == "humedad":
                archivo_destino = ARCHIVO_HUMEDAD

            elif tipo_sensor == "luz":
                archivo_destino = ARCHIVO_LUZ

            # Almacena la lectura individual del sensor.
            # Cada fila contiene la fecha, la hora y el valor recibido.
            if archivo_destino:

                with open(
                    archivo_destino,
                    mode="a",
                    newline="",
                    encoding="utf-8"
                ) as f:

                    writer = csv.writer(f)

                    writer.writerow([
                        time.strftime("%Y-%m-%d %H:%M:%S"),
                        valor
                    ])

            # Muestra la lectura recibida por consola.
            print(
                f"[{ahora}] [SENSOR] "
                f"{tipo_sensor.upper()} = {valor} {unidad}"
            )

            # Registra una fotografía del estado general de la casa.
            # Se incluyen los últimos valores conocidos de todos los
            # sensores y actuadores en el momento de esta lectura.
            with open(
                ARCHIVO_SNAPSHOT,
                mode="a",
                newline="",
                encoding="utf-8"
            ) as f:

                writer = csv.writer(f)

                writer.writerow([
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    estado_habitacion["presencia_valor"],
                    estado_habitacion["temperatura"],
                    estado_habitacion["humedad"],
                    estado_habitacion["luz"],
                    estado_habitacion["bombilla"],
                    estado_habitacion["persiana"]
                ])


        # *************************************************************
        # CASO B: ÓRDENES ENVIADAS HACIA LOS ACTUADORES (/set)
        # *************************************************************

        elif "/actuador/" in topic and topic.endswith("/set"):

            # Identifica el actuador destinatario de la orden.
            tipo_act = topic.split("/")[-2]

            # Muestra la orden publicada, aunque todavía no se modifica
            # el estado almacenado: se espera su confirmación posterior.
            print(
                f"[{ahora}] [ORDEN ACT] "
                f"{tipo_act.upper()} -> {payload_str}"
            )


        # *************************************************************
        # CASO C: ESTADOS CONFIRMADOS POR LOS ACTUADORES (/estado)
        # *************************************************************

        elif "/actuador/" in topic and topic.endswith("/estado"):

            # Identifica el actuador que ha publicado la confirmación.
            tipo_act = topic.split("/")[-2]

            # Intenta extraer el estado y su procedencia del mensaje JSON.
            # Si el contenido no es JSON, se utiliza como texto plano.
            try:
                datos = json.loads(payload_str)

                estado = datos.get("estado", payload_str)
                origen = datos.get("origen", "MQTT")

            except Exception:
                estado = payload_str
                origen = "RAW"

            # Recupera el estado anterior antes de actualizarlo.
            estado_anterior = estado_habitacion.get(tipo_act)

            # Actualiza el estado del actuador en memoria.
            estado_habitacion[tipo_act] = str(estado).strip().upper()

            # Identifica si el mensaje ha sido entregado como retenido.
            # Los mensajes retained se reciben automáticamente al realizar
            # la suscripción y representan estados publicados anteriormente.
            ret = " [RETENIDO]" if msg.retain else ""

            # Muestra siempre la confirmación recibida por consola,
            # conservando la información del actuador y su procedencia.
            print(
                f"[{ahora}] [ESTADO ACT] "
                f"{tipo_act.upper()} = {estado} ({origen}){ret}"
            )

            # Los mensajes retenidos sirven para recuperar el último
            # estado conocido de cada actuador al iniciar el monitor.
            # Se actualiza la memoria, pero no se vuelve a imprimir
            # la tarjeta inicial por cada mensaje retenido.
            if msg.retain:
                return

            # Si el mensaje no es retenido, se comprueba si existe
            # un cambio real respecto al estado que tenía el actuador.
            # Solo entonces se imprime la tarjeta resumen actualizada.
            if estado_anterior != estado_habitacion[tipo_act]:
                imprimir_resumen_habitacion(ahora)


        # *************************************************************
        # CASO D: AUDITORÍAS DE REGLAS DEL MOTOR DE REGLAS
        # *************************************************************

        elif "/sistema/regla" in topic:

            # Intenta extraer la descripción de la regla desde JSON.
            # Si el contenido no tiene formato JSON, utiliza el payload.
            try:
                datos = json.loads(payload_str)
                regla_txt = datos.get("regla", payload_str)

            except Exception:
                regla_txt = payload_str

            # Actualiza la última regla evaluada para que aparezca
            # en la siguiente tarjeta resumen de la estancia.
            estado_habitacion["ultima_regla"] = regla_txt

            # Muestra la auditoría recibida por consola.
            print(f"[{ahora}] [REGLA] {regla_txt}")


        # *************************************************************
        # CASO E: MENSAJES DE TESTAMENTO (LWT)
        # *************************************************************

        elif topic.endswith("/lwt"):

            # Identifica el nodo que ha publicado el mensaje LWT.
            nodo = topic.split("/")[-2]

            # Obtiene el estado comunicado por el nodo.
            estado = payload_str.strip().upper()

            # Muestra el mensaje de disponibilidad o desconexión.
            print(f"[{ahora}] [LWT] Nodo '{nodo}' -> {estado}")


    except Exception as e:

        # Informa de cualquier error inesperado durante el procesamiento
        # de un mensaje sin detener el funcionamiento del monitor.
        print(f"Error procesando mensaje en {topic}: {e}")


# ********************************************************************
#     5.- FUNCIÓN PRINCIPAL DE INICIALIZACIÓN Y BUCLE DE EJECUCIÓN
# ********************************************************************

def main():
    """Inicializa los registros, muestra el estado inicial y conecta MQTT."""

    # Muestra la información general del monitor y del broker utilizado.
    print("=" * 64)
    print(f"MONITOR Y VISOR DE EVENTOS MQTT (Grupo: {GRUPO})")
    print("=" * 64)
    print(f"Broker : {BROKER_DEFAULT}:{PUERTO_DEFAULT}")
    print(f"Filtro : {topic_todo(GRUPO)}")
    print("-" * 64)


    # *************************************************************
    # INICIALIZACIÓN DE LOS FICHEROS CSV
    # *************************************************************

    # Comprueba si existen los ficheros individuales de eventos.
    # Si alguno no existe, lo crea y escribe su correspondiente cabecera.
    for archivo in [
        ARCHIVO_PRESENCIA,
        ARCHIVO_TEMPERATURA,
        ARCHIVO_HUMEDAD,
        ARCHIVO_LUZ
    ]:

        if not os.path.exists(archivo):

            with open(
                archivo,
                mode="w",
                newline="",
                encoding="utf-8"
            ) as f:

                writer = csv.writer(f)
                writer.writerow(["Timestamp_Llegada", "Valor"])


    # Comprueba si existe el fichero general consolidado.
    # En caso contrario, lo crea con las columnas correspondientes.
    if not os.path.exists(ARCHIVO_SNAPSHOT):

        with open(
            ARCHIVO_SNAPSHOT,
            mode="w",
            newline="",
            encoding="utf-8"
        ) as f:

            writer = csv.writer(f)

            writer.writerow([
                "Timestamp",
                "Presencia",
                "Temperatura_C",
                "Humedad_pct",
                "Luz_lux",
                "Luz_Bombilla",
                "Persiana"
            ])


    # *************************************************************
    # MOSTRAR EL ESTADO INICIAL DE LA CASA
    # *************************************************************

    # Imprime una única tarjeta inicial con los valores predeterminados.
    # Las confirmaciones retained que lleguen posteriormente actualizarán
    # los valores en memoria sin provocar nuevas impresiones de la tarjeta.
    imprimir_resumen_habitacion(time.strftime("%H:%M:%S"))


    # *************************************************************
    # CONFIGURACIÓN DEL CLIENTE MQTT
    # *************************************************************

    # Genera un identificador único para evitar conflictos con otras
    # instancias del monitor conectadas simultáneamente al mismo broker.
    client_id = f"monitor-{GRUPO}-{int(time.time())}"

    # Utiliza la API de callbacks de MQTT versión 2.
    # Si la versión instalada no dispone de ella, utiliza el constructor
    # compatible con versiones anteriores de la biblioteca Paho MQTT.
    try:
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id
        )

    except AttributeError:
        client = mqtt.Client(client_id=client_id)


    # Asigna las funciones que gestionan la conexión y la recepción.
    client.on_connect = on_connect
    client.on_message = on_message


    # *************************************************************
    # CONEXIÓN Y EJECUCIÓN DEL MONITOR
    # *************************************************************

    # Establece la conexión con el broker MQTT utilizando un keepalive
    # de 60 segundos para mantener activa la comunicación.
    client.connect(
        BROKER_DEFAULT,
        PUERTO_DEFAULT,
        keepalive=60
    )

    # Inicia el bucle de red en segundo plano.
    # Este hilo se encarga de gestionar la recepción de mensajes
    # y ejecutar automáticamente los callbacks correspondientes.
    client.loop_start()


    # Mantiene el programa en ejecución hasta que el usuario
    # interrumpa manualmente el monitor mediante Ctrl+C.
    try:

        while True:
            time.sleep(1)

    except KeyboardInterrupt:

        # Detiene ordenadamente el monitor cuando el usuario
        # solicita finalizar su ejecución.
        print("\nDeteniendo monitor...")

        client.loop_stop()
        client.disconnect()

        print("Monitor desconectado correctamente.\n")


if __name__ == "__main__":
    main()