#!/usr/bin/env python3
"""Lanzador Conjunto Todo-en-Uno para la Práctica 2 IoT (MQTT Simple)."""

import argparse
import os
import subprocess
import sys
import time

from config import GRUPO_DEFAULT

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))


# Configura los parámetros de entrada permitidos al ejecutar el script automatizado
def parse_args():
    parser = argparse.ArgumentParser(
        description="Lanzador conjunto del sistema IoT de la Práctica 2"
    )
    parser.add_argument(
        "grupo",
        nargs="?",
        default=GRUPO_DEFAULT,
        help="Identificador de grupo (por defecto 'g99')",
    )
    parser.add_argument(
        "--periodo",
        type=float,
        default=2.0,
        help="Periodo de publicación de los sensores en segundos (por defecto 2.0)",
    )
    parser.add_argument(
        "--sin-monitor",
        action="store_true",
        help="No iniciar el controlador central integrado",
    )
    parser.add_argument(
        "--solo-servicios",
        action="store_true",
        help="Iniciar solo actuadores",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    grupo = args.grupo
    periodo = str(args.periodo)
    python_exe = sys.executable

    print("=" * 72)
    print(
        f"INICIANDO SISTEMA COMPLETO IoT (MQTT Simple) - GRUPO: {grupo.upper()}"
    )
    print("=" * 72)
    print(f"Intérprete Python: {python_exe}")
    print(f"Directorio base:   {DIR_ACTUAL}")
    print(f"Periodo sensores:  {periodo} s")
    print("-" * 72)

    procesos = []

    # Función auxiliar encargada de arrancar y registrar cada subproceso por separado
    def lanzar(comando, nombre):
        print(f"Lanzando {nombre}...")
        p = subprocess.Popen(comando, cwd=DIR_ACTUAL)
        procesos.append((nombre, p))
        time.sleep(0.8)

    try:
        if not args.sin_monitor:
            lanzar([python_exe, "controlador.py", grupo], "Controlador Central")

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

        if not args.solo_servicios:
            sensores = ["luz", "humedad", "temperatura", "presencia"]
            for s in sensores:
                lanzar(
                    [
                        python_exe,
                        "sensor.py",
                        "--tipo",
                        s,
                        "--grupo",
                        grupo,
                        "--periodo",
                        periodo,
                    ],
                    f"Sensor {s.capitalize()}",
                )

        print("\n" + "=" * 72)
        print("TODOS LOS MÓDULOS ESTÁN EN EJECUCIÓN Y CONECTADOS A HIVEMQ")
        print("=" * 72)
        print(
            "\nPresiona Ctrl+C en esta terminal para detener todo el sistema limpiamente."
        )
        print("=" * 72 + "\n")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        # Captura la señal de cierre por teclado para terminar ordenadamente todos los procesos hijos
        print(
            "\n\nSolicitud de parada recibida. Cerrando todos los procesos..."
        )
        for nombre, p in reversed(procesos):
            try:
                print(f"   Deteniendo {nombre}...")
                p.terminate()
            except Exception:
                pass

        time.sleep(1.5)
        for nombre, p in procesos:
            if p.poll() is None:
                try:
                    p.kill()
                except Exception:
                    pass

        print(
            "Todos los módulos se han detenido correctamente. ¡Hasta pronto!\n"
        )


if __name__ == "__main__":
    main()