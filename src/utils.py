"""
Utilidades compartidas para la aplicación.

Contiene conexiones compartidas a Redis y funciones helper
usadas por múltiples módulos.
"""

import hashlib
import json
from redis import Redis
from rq import Queue
from rq.job import Job

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


def enqueue_task(
    task_name: str, 
    task_func, 
    task_args: tuple, 
    idem_payload: dict, 
    high: bool = False, 
    ttl_extra: int = 10
) -> dict:
    """Encola una tarea en RQ con idempotencia automática.
    
    Esta función centraliza la lógica de encolado para evitar duplicación de código.
    Verifica si ya existe una tarea idéntica en cola/ejecución antes de crear una nueva.
    
    Args:
        task_name: Nombre identificador de la tarea
        task_func: Función del worker a ejecutar
        task_args: Tupla con los argumentos para task_func (sin incluir idem_key)
        idem_payload: Diccionario con datos para generar clave de idempotencia
        high: Si True, encola en cola 'high' (prioridad alta)
        ttl_extra: Segundos adicionales para el TTL de la clave de idempotencia
    
    Returns:
        Dict con:
        - duplicate: True si la tarea ya existía
        - job_id: ID del job (nuevo o existente)
        - queue: Nombre de la cola (si es nuevo)
        - task: Nombre de la tarea (si es nuevo)
    
    Example:
        >>> _enqueue_task(
        ...     task_name="task_a",
        ...     task_func=worker_tasks.task_a,
        ...     task_args=(123,),
        ...     idem_payload={"user_id": 123},
        ...     high=False
        ... )
        {"job_id": "uuid", "queue": "default", "task": "task_a"}
    """
    # Generar clave de idempotencia
    idem_key = make_idem_key(task_name, idem_payload, 0)
    ttl = ttl_extra + settings.IDEMP_MARGIN
    
    # Verificar si ya existe una tarea idéntica
    existing = redis_conn.get(idem_key)
    if existing:
        job_id = existing.decode() if isinstance(existing, bytes) else str(existing)
        try:
            job = Job.fetch(str(job_id), connection=redis_conn)
            status = job.get_status()
            if status in ("finished", "failed", "canceled", "cancelled"):
                pass  # Permitir encolar nueva tarea
            else:
                return {"duplicate": True, "job_id": job_id}
        except Exception:
            pass
    
    # Seleccionar cola según prioridad
    q = q_high if high else q_default

    # Encolar tarea con configuración
    job = q.enqueue(
        task_func,
        *task_args,
        idem_key,
        job_timeout=settings.TASK_TIMEOUT,
        result_ttl=settings.RESULT_TTL,
        failure_ttl=settings.FAILURE_TTL,
    )
    
    # Guardar job_id en Redis con TTL para idempotencia
    redis_conn.setex(idem_key, ttl, job.id)
    
    return {"job_id": job.id, "queue": q.name, "task": task_name}
#endregion FUNCIONES HELPER
