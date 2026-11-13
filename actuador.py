
#!/usr/bin/env python3
"""Módulo de Actuador Simulado e Interactivo para la Práctica 2 IoT."""

import argparse
import json
import sys
import threading
import time
import paho.mqtt.client as mqtt

from config import (
    BROKER_DEFAULT,
    PUERTO_DEFAULT,
    GRUPO_DEFAULT,
    topic_actuador_set,
    topic_actuador_estado,
)


# ********************************************************************
#          1.- CONFIGURACIÓN DE ESTADOS DE LOS ACTUADORES
# ********************************************************************

# Define los estados válidos que puede adoptar cada actuador.
# La bombilla permite encenderse o apagarse, mientras que la persiana
# puede abrirse o cerrarse.

ESTADOS_VALIDOS = {
    "bombilla": ["ON", "OFF"],
    "persiana": ["ABIERTA", "CERRADA"],
}

# Establece el estado inicial de cada actuador al iniciar su ejecución.
# Estos valores se publicarán al controlador una vez establecida
# la conexión con el broker MQTT.

ESTADO_INICIAL = {
    "bombilla": "OFF",
    "persiana": "CERRADA",
}


# ********************************************************************
#                  2.- GESTIÓN DE ARGUMENTOS
# ********************************************************************


def parse_args():
    """
    Configura los parámetros permitidos al ejecutar el actuador.
    Permite seleccionar el tipo de componente, grupo MQTT y los datos
    de conexión con el broker.
    """

    parser = argparse.ArgumentParser(
        description="Actuador IoT interactivo"
    )

    # Identifica el actuador que se desea ejecutar.
    parser.add_argument(
        "--tipo",
        type=str,
        required=True,
        choices=["bombilla", "persiana"],
        help="Tipo de actuador: bombilla o persiana",
    )

    # Identificador del grupo utilizado para construir los tópicos MQTT.
    parser.add_argument(
        "--grupo",
        type=str,
        default=GRUPO_DEFAULT,
        help=f"Identificador del grupo (por defecto '{GRUPO_DEFAULT}')",
    )

    # Parámetros de conexión con el broker MQTT.
    parser.add_argument(
        "--broker",
        type=str,
        default=BROKER_DEFAULT,
        help=f"Broker MQTT (por defecto {BROKER_DEFAULT})",
    )

    parser.add_argument(
        "--puerto",
        type=int,
        default=PUERTO_DEFAULT,
        help=f"Puerto del broker (por defecto {PUERTO_DEFAULT})",
    )

    return parser.parse_args()


# ********************************************************************
#              3.- CLASE PRINCIPAL DEL ACTUADOR SIMULADO
# ********************************************************************

class ActuadorSimulado:
    """Representa un actuador virtual controlado mediante MQTT y teclado."""

    def __init__(self, tipo, grupo, broker, puerto):

        # Almacena la configuración correspondiente al actuador.
        self.tipo = tipo
        self.grupo = grupo
        self.broker = broker
        self.puerto = puerto

        # Inicializa el estado y recupera los estados permitidos.
        self.estado = ESTADO_INICIAL[tipo]
        self.estados_permitidos = ESTADOS_VALIDOS[tipo]

        # Obtiene los tópicos MQTT utilizados para recibir órdenes,
        # publicar estados confirmados y comunicar la disponibilidad.
        self.topic_set = topic_actuador_set(tipo, grupo)
        self.topic_estado = topic_actuador_estado(tipo, grupo)
        self.topic_lwt = f"iotlab26/{grupo}/actuador/{tipo}/lwt"

        # Controla la ejecución del actuador y protege el estado
        # compartido entre el hilo MQTT y el hilo de entrada por teclado.
        self.activo = True
        self.lock = threading.Lock()

        # Genera un identificador para distinguir cada instancia
        # del actuador cuando se conecta al broker.
        client_id = f"act-{tipo}-{grupo}-{int(time.time())}"

        # Crea el cliente MQTT utilizando la API de callbacks disponible.
        # Mantiene compatibilidad con las versiones 1 y 2 de Paho MQTT.
        try:
            self.client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=client_id,
            )

        except AttributeError:
            self.client = mqtt.Client(
                client_id=client_id,
            )

        # Asigna las funciones encargadas de gestionar la conexión
        # y procesar las órdenes recibidas a través de MQTT.
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # Configura el mensaje LWT (Last Will and Testament).
        # El broker publicará OFFLINE automáticamente si el actuador
        # pierde inesperadamente la conexión.
        self.client.will_set(
            self.topic_lwt,
            payload="OFFLINE",
            qos=1,
            retain=True,
        )


    # ****************************************************************
    #                4.- CALLBACKS DE CONEXIÓN MQTT
    # ****************************************************************

    def on_connect(self, client, userdata, flags, rc, properties=None):
        """
        Se ejecuta automáticamente cuando el cliente establece
        una conexión con el broker MQTT.
        Si la conexión es correcta, el actuador se suscribe a su tópico
        de órdenes, publica su disponibilidad y comunica su estado inicial.
        """

        # La API VERSION2 proporciona un objeto ReasonCode,
        # mientras que la versión anterior utiliza un código entero.
        codigo = getattr(rc, "value", rc)

        if codigo == 0:

            print(
                f"Conectado a HiveMQ ({self.broker}:{self.puerto})"
            )

            print(f"Suscrito a órdenes en: {self.topic_set}")

            # Se suscribe al tópico específico de órdenes del actuador.
            client.subscribe(
                self.topic_set,
                qos=1,
            )

            # Comunica que el actuador está disponible.
            client.publish(
                self.topic_lwt,
                payload="ONLINE",
                qos=1,
                retain=True,
            )

            # Publica el estado inicial para informar al controlador
            # del estado actual del componente simulado.
            self.publicar_estado("INICIAL")

        else:

            print(
                f"Error de conexión al broker. Código rc={codigo}"
            )


    # ****************************************************************
    #                5.- RECEPCIÓN Y PROCESAMIENTO DE ÓRDENES
    # ****************************************************************

    def on_message(self, client, userdata, msg):

        """
        Procesa las órdenes recibidas mediante el tópico MQTT del actuador.
        Acepta tanto mensajes de texto como mensajes JSON que contengan
        los campos "estado" u "orden".
        Solo se aplican los estados definidos como válidos para cada tipo
        de actuador. Los cambios se notifican al resto del sistema.
        """

        try:

            # Decodifica el contenido recibido desde el broker.
            orden_raw = msg.payload.decode(
                "utf-8",
                errors="replace",
            ).strip()

            # Comprueba si el mensaje contiene un objeto JSON.
            if orden_raw.startswith("{"):

                datos = json.loads(orden_raw)

                nuevo_estado = str(
                    datos.get("estado", datos.get("orden", ""))
                ).strip().upper()

            else:

                nuevo_estado = orden_raw.upper()

            # Comprueba que la orden corresponda a un estado permitido.
            if nuevo_estado not in self.estados_permitidos:

                print(
                    f"\n[ORDEN RECHAZADA] Valor no válido: '{nuevo_estado}'"
                )

                self.mostrar_prompt()
                return

            # Protege la actualización del estado frente a accesos
            # simultáneos desde el hilo MQTT y la consola interactiva.
            with self.lock:

                # Evita publicar confirmaciones cuando el estado
                # recibido coincide con el estado actual.
                if nuevo_estado != self.estado:

                    antiguo = self.estado
                    self.estado = nuevo_estado

                    print(
                        f"\n[ORDEN MQTT] Cambio de estado: "
                        f"{antiguo} -> {self.estado}"
                    )

                    # Confirma el nuevo estado mediante MQTT.
                    self.publicar_estado("MQTT")

            self.mostrar_prompt()

        except Exception as error:

            # Informa de los errores de procesamiento sin detener
            # el funcionamiento del actuador.
            print(
                f"\nError procesando orden MQTT: {error}"
            )

            self.mostrar_prompt()


    # ****************************************************************
    #              6.- PUBLICACIÓN DEL ESTADO DEL ACTUADOR
    # ****************************************************************


    def publicar_estado(self, origen="MANUAL"):

        """
        Publica el estado actual confirmado en el tópico correspondiente.
        El mensaje incluye información del actuador, estado, origen,
        fecha de publicación y grupo.
        Se utiliza retain=True para que los nuevos suscriptores puedan
        recuperar el último estado conocido del actuador.
        """

        # Construye el mensaje JSON con la información del actuador.
        payload = {
            "actuador": self.tipo,
            "estado": self.estado,
            "origen": origen,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "grupo": self.grupo,
        }

        # Publica el estado confirmado con QoS 1 y almacenamiento retained.
        self.client.publish(
            self.topic_estado,
            json.dumps(payload, ensure_ascii=False),
            qos=1,
            retain=True,
        )

        print(
            f"[ESTADO CONFIRMADO] {self.tipo.upper()} = "
            f"{self.estado} (en {self.topic_estado})"
        )


    # ****************************************************************
    #                  7.- INTERFAZ DE CONSOLA
    # ****************************************************************

    def mostrar_prompt(self):

        """
        Muestra las opciones disponibles para modificar manualmente
        el estado del actuador desde la terminal.
        """

        opciones = "/".join(self.estados_permitidos)

        print(
            f"\n[{self.tipo.upper()}] Estado: [{self.estado}] | "
            f"Escribe ({opciones}) o 'q': ",
            end="",
            flush=True,
        )


    def bucle_consola_interactivo(self):

        """
        Gestiona las entradas introducidas manualmente por teclado.
        Se ejecuta en un hilo independiente para permitir que el cliente
        MQTT continúe recibiendo órdenes mientras se utiliza la consola.
        Los cambios manuales también se publican mediante MQTT para que
        el controlador central conozca el nuevo estado del actuador.
        """

        # Espera brevemente para permitir que se establezca la conexión
        # MQTT antes de mostrar las opciones de interacción.
        time.sleep(1.5)

        while self.activo:

            try:

                self.mostrar_prompt()

                # Espera a que el usuario introduzca una opción.
                linea = sys.stdin.readline()

                if not linea:
                    break

                entrada = linea.strip().upper()

                # La opción Q permite finalizar la ejecución del actuador.
                if entrada == "Q":
                    self.activo = False
                    break

                # Ignora las entradas vacías.
                if not entrada:
                    continue

                # Comprueba que el estado introducido sea válido.
                if entrada in self.estados_permitidos:

                    with self.lock:

                        # Solo publica una confirmación si existe
                        # un cambio real respecto al estado actual.
                        if entrada != self.estado:

                            antiguo = self.estado
                            self.estado = entrada

                            print(
                                f"\n[MANUAL] Cambiado {self.tipo}: "
                                f"{antiguo} -> {self.estado}"
                            )

                            self.publicar_estado("MANUAL")

                else:

                    print(
                        f"\nOpción no válida '{entrada}'."
                    )

            except (EOFError, KeyboardInterrupt):

                # Finaliza el hilo de consola cuando se interrumpe
                # la entrada manual o se cierra la terminal.
                self.activo = False
                break


    # ****************************************************************
    #          8.- INICIALIZACIÓN Y EJECUCIÓN DEL ACTUADOR
    # ****************************************************************

    def iniciar(self):

        """
        Muestra la información inicial, establece la conexión MQTT
        e inicia los hilos necesarios para mantener el actuador operativo.
        El hilo principal supervisa la ejecución mientras el hilo MQTT
        y el hilo de consola trabajan de manera independiente.
        """

        print("=" * 65)
        print(
            f"ACTUADOR SIMULADO: {self.tipo.upper()} "
            f"(Grupo: {self.grupo})"
        )
        print("=" * 65)

        print(f"Broker MQTT: {self.broker}:{self.puerto}")
        print(f"Tópico de órdenes: {self.topic_set}")
        print(f"Tópico de estado: {self.topic_estado}")
        print("-" * 65)

        try:

            # Establece la conexión con el broker MQTT.
            self.client.connect(
                self.broker,
                self.puerto,
                keepalive=60,
            )

            # Inicia el bucle de comunicación MQTT en segundo plano.
            self.client.loop_start()

            # Inicia el hilo encargado de gestionar las órdenes manuales.
            hilo_consola = threading.Thread(
                target=self.bucle_consola_interactivo,
                daemon=True,
            )

            hilo_consola.start()

            # Mantiene el proceso principal activo mientras el actuador
            # continúe funcionando.
            while self.activo:
                time.sleep(0.5)

        except KeyboardInterrupt:

            # Captura la interrupción del teclado para iniciar
            # el cierre ordenado del actuador.
            print("\nDeteniendo el actuador...")

        except Exception as error:

            print(
                f"\nError durante la ejecución del actuador: {error}"
            )

        finally:

            # Indica a los hilos secundarios que deben finalizar.
            self.activo = False

            # Espera brevemente a que termine el hilo de consola.
            if "hilo_consola" in locals():
                hilo_consola.join(timeout=0.5)

            # Si el cliente continúa conectado, publica OFFLINE
            # antes de cerrar la conexión con el broker.
            if self.client.is_connected():

                info = self.client.publish(
                    self.topic_lwt,
                    payload="OFFLINE",
                    qos=1,
                    retain=True,
                )

                try:
                    info.wait_for_publish(timeout=5)

                except RuntimeError:
                    pass

            # Detiene el bucle MQTT y desconecta el cliente.
            self.client.loop_stop()

            if self.client.is_connected():
                self.client.disconnect()

            print(
                f"Actuador {self.tipo.upper()} detenido."
            )


# ********************************************************************
#       9.- FUNCIÓN PRINCIPAL DE INICIALIZACIÓN Y EJECUCIÓN
# ********************************************************************

def main():
    """Configura e inicia el actuador seleccionado desde consola."""

    # Recupera los argumentos introducidos al ejecutar el programa.
    args = parse_args()

    # Crea e inicia el actuador con la configuración seleccionada.
    actuador = ActuadorSimulado(
        args.tipo,
        args.grupo,
        args.broker,
        args.puerto,
    )

    actuador.iniciar()


if __name__ == "__main__":
    main()
