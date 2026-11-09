"""Configuración central para la Práctica 2 de IoT (MQTT Simple).
Define los parámetros de conexión al broker HiveMQ, los umbrales de las
reglas domóticas y los generadores de topics MQTT.
"""

# Dirección del servidor broker público MQTT de HiveMQ
BROKER_DEFAULT = "broker.hivemq.com"

# Puerto estándar predeterminado para las comunicaciones MQTT sin cifrar
PUERTO_DEFAULT = 1883

# Tiempo máximo de inactividad en segundos antes de considerar una desconexión
KEEPALIVE_DEFAULT = 60

# Identificador alfanumérico del grupo de prácticas asignado
GRUPO_DEFAULT = "g99"

# Umbrales numéricos de referencia para evaluar las reglas automáticas
UMBRAL_LUZ_BAJA = 150.0  # lux
UMBRAL_LUZ_ALTA = 600.0  # lux
UMBRAL_HUMEDAD_ALTA = 70.0  # porcentaje
UMBRAL_HUMEDAD_BAJA = 40.0  # porcentaje


# Genera la ruta raíz jerárquica para aislar el tráfico del grupo
def topic_base(grupo=GRUPO_DEFAULT):
    """Devuelve el prefijo raíz para el grupo."""
    return f"iotlab26/{grupo}"


# Genera el tópico específico para enviar o recibir telemetría de un sensor
def topic_sensor(tipo, grupo=GRUPO_DEFAULT):
    """Topic para la telemetría de un sensor: luz, humedad, temperatura, presencia."""
    return f"{topic_base(grupo)}/sensor/{tipo}"


# Genera el tópico para enviar órdenes de control hacia un actuador concreto
def topic_actuador_set(nombre, grupo=GRUPO_DEFAULT):
    """Topic para enviar órdenes a un actuador: bombilla, persiana."""
    return f"{topic_base(grupo)}/actuador/{nombre}/set"


# Genera el tópico donde el actuador publica su estado real confirmado con persistencia
def topic_actuador_estado(nombre, grupo=GRUPO_DEFAULT):
    """Topic donde el actuador publica su estado confirmado (con Retain)."""
    return f"{topic_base(grupo)}/actuador/{nombre}/estado"


# Genera el tópico destinado a registrar auditorías y eventos del motor de reglas
def topic_reglas(grupo=GRUPO_DEFAULT):
    """Topic para auditoría de reglas activadas por el motor."""
    return f"{topic_base(grupo)}/sistema/regla"


# Genera el comodín jerárquico para suscribirse a toda la actividad simultáneamente
def topic_todo(grupo=GRUPO_DEFAULT):
    """Topic comodín para suscribirse a toda la actividad del grupo."""
    return f"{topic_base(grupo)}/#"