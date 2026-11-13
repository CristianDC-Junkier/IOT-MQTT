
#!/usr/bin/env python3
"""Lanzador Conjunto Todo-en-Uno para la Práctica 2 IoT (MQTT Simple)."""

import argparse
import os
import subprocess
import sys
import time

from config import GRUPO_DEFAULT


# ********************************************************************
#     1.- GESTIÓN DE ARGUMENTOS Y CONFIGURACIÓN DEL SISTEMA
# ********************************************************************

# Obtiene la ruta del directorio donde se encuentra este script.
# Permite ejecutar los módulos independientemente del directorio
# desde el que se haya iniciado el lanzador.

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))


def parse_args():

    """
    Configura los parámetros permitidos al ejecutar el sistema.
    Se puede seleccionar el grupo, modificar el periodo de los sensores
    o elegir qué módulos se desean iniciar.
    """

    parser = argparse.ArgumentParser(
        description="Lanzador conjunto del sistema IoT de la Práctica 2"
    )

    # Identificador del grupo utilizado para construir los tópicos MQTT.
    # Si no se proporciona, se utiliza el grupo configurado por defecto.
    parser.add_argument(
        "grupo",
        nargs="?",
        default=GRUPO_DEFAULT,
        help="Identificador de grupo (por defecto 'g99')",
    )

    # Intervalo de tiempo entre publicaciones consecutivas de los sensores.
    parser.add_argument(
        "--periodo",
        type=float,
        default=2.0,
        help="Periodo de publicación de los sensores en segundos (por defecto 2.0)",
    )

    # Permite seleccionar un único modo de ejecución.
    modos = parser.add_mutually_exclusive_group()

    # Inicia exclusivamente los sensores del sistema.
    modos.add_argument(
        "--solo-sensores",
        action="store_true",
        help="Iniciar únicamente todos los sensores",
    )

    # Inicia los servicios centrales y los actuadores, sin sensores.
    modos.add_argument(
        "--solo-servicios",
        action="store_true",
        help="Iniciar controlador, motor de reglas y actuadores",
    )

    # Permite ejecutar los módulos sin iniciar el controlador central.
    parser.add_argument(
        "--sin-monitor",
        action="store_true",
        help="No iniciar el controlador central",
    )

    return parser.parse_args()


# ********************************************************************
#              2.- GESTIÓN E INICIALIZACIÓN DE PROCESOS
# ********************************************************************

def main():

    # Recupera los argumentos introducidos por consola y prepara
    # la configuración que utilizarán todos los módulos del sistema.
    args = parse_args()

    grupo = args.grupo
    periodo = str(args.periodo)
    python_exe = sys.executable

    # Muestra la información general y el modo de ejecución seleccionado.
    print("=" * 72)
    print(
        f"INICIANDO SISTEMA IoT (MQTT Simple) - GRUPO: {grupo.upper()}"
    )
    print("=" * 72)
    print(f"Intérprete Python: {python_exe}")
    print(f"Directorio base:   {DIR_ACTUAL}")
    print(f"Periodo sensores:  {periodo} s")

    if args.solo_sensores:
        print("Modo de ejecución: SOLO SENSORES")

    elif args.solo_servicios:
        print("Modo de ejecución: CONTROLADOR, REGLAS Y ACTUADORES")

    else:
        print("Modo de ejecución: SISTEMA COMPLETO")

    print("-" * 72)

    # Lista que almacena los procesos iniciados para poder detenerlos
    # posteriormente cuando el usuario solicite finalizar el sistema.
    procesos = []


    # ****************************************************************
    #             3.- FUNCIÓN AUXILIAR DE LANZAMIENTO
    # ****************************************************************

    # Inicia cada módulo como un proceso independiente de Python.
    # Registra su identificador y espera brevemente antes de continuar
    # para facilitar el arranque ordenado de los distintos componentes.

    def lanzar(comando, nombre):

        print(f"Lanzando {nombre}...")

        proceso = subprocess.Popen(
            comando,
            cwd=DIR_ACTUAL,
        )

        procesos.append((nombre, proceso))

        time.sleep(0.8)


    # ****************************************************************
    #                  4.- ARRANQUE DE LOS MÓDULOS
    # ****************************************************************

    try:

        # ************************************************************
        #                    CONTROLADOR CENTRAL
        # ************************************************************

        # Inicia el controlador encargado de recibir las lecturas
        # de los sensores, registrar los eventos y mostrar el estado
        # general de la habitación.
        #
        # No se inicia en el modo exclusivo de sensores ni cuando
        # se utiliza explícitamente el argumento --sin-monitor.

        if not args.solo_sensores and not args.sin_monitor:

            lanzar(
                [python_exe, "controlador.py", grupo],
                "Controlador Central",
            )


        # ************************************************************
        #                      MOTOR DE REGLAS
        # ************************************************************

        # Inicia el motor encargado de evaluar las condiciones
        # de automatización y publicar las órdenes correspondientes
        # a los actuadores mediante MQTT.
        #
        # Se ejecuta en todos los modos que incluyen los servicios.

        if not args.solo_sensores:

            lanzar(
                [python_exe, "reglas.py", grupo],
                "Motor de Reglas",
            )


        # ************************************************************
        #                         ACTUADORES
        # ************************************************************

        # Inicia los actuadores disponibles en la instalación.
        # Cada actuador se ejecuta como un proceso independiente
        # y escucha las órdenes recibidas a través de su tópico MQTT.

        if not args.solo_sensores:

            lanzar(
                [
                    python_exe,
                    "actuador.py",
                    "--tipo",
                    "bombilla",
                    "--grupo",
                    grupo,
                ],
                "Actuador Bombilla",
            )

            lanzar(
                [
                    python_exe,
                    "actuador.py",
                    "--tipo",
                    "persiana",
                    "--grupo",
                    grupo,
                ],
                "Actuador Persiana",
            )


        # ************************************************************
        #                          SENSORES
        # ************************************************************

        # Inicia los sensores encargados de obtener las lecturas
        # ambientales y de presencia de la habitación.
        #
        # Todos utilizan el mismo periodo de publicación, que puede
        # modificarse mediante el argumento --periodo.
        #
        # No se inician cuando se selecciona el modo --solo-servicios.

        if not args.solo_servicios:

            sensores = [
                "luz",
                "humedad",
                "temperatura",
                "presencia",
            ]

            for sensor in sensores:

                lanzar(
                    [
                        python_exe,
                        "sensor.py",
                        "--tipo",
                        sensor,
                        "--grupo",
                        grupo,
                        "--periodo",
                        periodo,
                    ],
                    f"Sensor {sensor.capitalize()}",
                )


        # ************************************************************
        #                   SISTEMA EN EJECUCIÓN
        # ************************************************************

        # Informa de que todos los módulos correspondientes al modo
        # seleccionado han sido iniciados correctamente.
        #
        # El lanzador permanece activo mientras los procesos hijos
        # continúan ejecutándose en segundo plano.

        print("\n" + "=" * 72)
        print("TODOS LOS MÓDULOS SOLICITADOS ESTÁN EN EJECUCIÓN")
        print("=" * 72)

        print(
            "\nPresiona Ctrl+C en esta terminal para detener "
            "todos los procesos limpiamente."
        )

        print("=" * 72 + "\n")

        while True:
            time.sleep(1)


    # ****************************************************************
    #                 5.- CIERRE ORDENADO DEL SISTEMA
    # ****************************************************************

    except KeyboardInterrupt:

        # Captura la interrupción del teclado para iniciar el cierre
        # de todos los módulos que hayan sido lanzados previamente.
        print(
            "\n\nSolicitud de parada recibida. "
            "Cerrando todos los procesos..."
        )

        # Solicita la finalización de los procesos en orden inverso
        # al de su inicio para facilitar un cierre ordenado.
        for nombre, proceso in reversed(procesos):

            try:
                print(f"Deteniendo {nombre}...")
                proceso.terminate()

            except Exception:
                pass

        # Espera brevemente para permitir que los procesos finalicen.
        time.sleep(1.5)

        # Fuerza la finalización de aquellos procesos que todavía
        # continúen activos después de la solicitud de cierre.
        for nombre, proceso in procesos:

            if proceso.poll() is None:

                try:
                    proceso.kill()

                except Exception:
                    pass

        print(
            "Todos los módulos se han detenido correctamente. "
            "¡Hasta pronto!\n"
        )


if __name__ == "__main__":
    main()
