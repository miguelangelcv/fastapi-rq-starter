"""
Utilidades compartidas para la aplicación.

Contiene conexiones compartidas a Redis y funciones helper
usadas por múltiples módulos.
"""

import hashlib
import json
from redis import Redis
from rq import Queue

from settings import settings

#region CONEXIONES
# Conexión Redis única compartida por toda la aplicación
redis_conn = Redis.from_url(settings.REDIS_URL)

# Colas RQ compartidas
q_default = Queue("default", connection=redis_conn)
q_high = Queue("high", connection=redis_conn)
#endregion CONEXIONES

#region FUNCIONES HELPER
def make_idem_key(task_name: str, payload: dict, duration: int) -> str:
    """Genera una clave única de idempotencia para una tarea.
    
    La clave se genera mediante un hash SHA-256 de los parámetros de la tarea.
    Esto permite identificar tareas duplicadas basadas en su contenido.
    
    Args:
        task_name: Nombre identificador de la tarea
        payload: Diccionario con los datos/parámetros de la tarea
        duration: Duración esperada de la tarea en segundos
    
    Returns:
        String con formato "task:{task_name}:{hash_16_chars}"
    
    Example:
        >>> make_idem_key("task_a", {"user_id": 123}, 0)
        "task:task_a:a1b2c3d4e5f6g7h8"
    
    Note:
        - El hash se trunca a 16 caracteres para reducir longitud de clave
        - El payload se ordena alfabéticamente para garantizar consistencia
        - Tareas con mismos parámetros generan la misma clave
    """
    # Crear estructura de datos con todos los parámetros relevantes
    data = {
        "task": task_name,
        "payload": payload or {},
        "duration": duration
    }
    
    # Serializar a JSON con formato consistente (ordenado, sin espacios)
    body = json.dumps(data, sort_keys=True, separators=(",", ":"))
    
    # Generar hash SHA-256 y truncar a 16 caracteres
    h = hashlib.sha256(body.encode()).hexdigest()[:16]
    
    return f"task:{task_name}:{h}"
#endregion FUNCIONES HELPER
