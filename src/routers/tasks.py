"""
Router de tareas para FastAPI + RQ.

Este módulo proporciona endpoints REST para:
- Encolar tareas en Redis Queue (RQ)
- Consultar el estado de tareas
- Cancelar tareas en ejecución
- Idempotencia automática para evitar duplicados
"""

from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from rq import Retry
from rq.job import Job

from settings import settings
from utils import make_idem_key, redis_conn, q_default, q_high
import worker_tasks

router = APIRouter(prefix="/tasks", tags=["tasks"])


#region MODELOS PYDANTIC
class CreateTaskBody(BaseModel):
    """Modelo para crear la tarea long_task con duración personalizada.
    
    Attributes:
        task_name: Nombre de la tarea (solo 'long_task' soportado)
        duration: Duración en segundos de la tarea
        payload: Datos adicionales para la tarea
        high: Si True, usa cola de alta prioridad
    """
    task_name: str = "long_task"
    duration: int
    payload: Dict[str, Any] = {}
    high: bool = False


class TaskBody(BaseModel):
    """Modelo para tareas que requieren un user_id.
    
    Usado por task_a y task_b.
    
    Attributes:
        user_id: ID del usuario a procesar
        high: Si True, usa cola de alta prioridad
    """
    user_id: int
    high: bool = False
#endregion MODELOS PYDANTIC


#region FUNCIONES HELPER
def _enqueue_task(
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
        job_id = existing.decode() if isinstance(existing, bytes) else existing
        return {"duplicate": True, "job_id": job_id}
    
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

#region ENDPOINTS
@router.post("/")
def create_task(body: CreateTaskBody) -> dict:
    """Crear y encolar una tarea long_task con duración personalizada.
    
    Esta tarea ejecuta un loop que dura 'duration' segundos, actualizando
    el progreso en cada iteración. Soporta cancelación cooperativa.
    
    Args:
        body: Parámetros de la tarea (duration, payload, high)
    
    Returns:
        Dict con job_id y queue, o duplicate=True si ya existe
    
    Raises:
        HTTPException 400: Si duration <= 0 o task_name inválido
    
    Example:
        POST /tasks/
        {
            "task_name": "long_task",
            "duration": 10,
            "payload": {"data": "ejemplo"},
            "high": false
        }
    """
    # Validar parámetros
    if body.duration <= 0:
        raise HTTPException(400, "duration debe ser > 0")
    if body.task_name != "long_task":
        raise HTTPException(400, "task_name desconocido (usa 'long_task')")

    # Generar clave única y verificar duplicados
    idem_key = make_idem_key(body.task_name, body.payload, body.duration)
    ttl = body.duration + settings.IDEMP_MARGIN
    
    existing = redis_conn.get(idem_key)
    if existing:
        job_id = existing.decode() if isinstance(existing, bytes) else existing
        return {"duplicate": True, "job_id": job_id}

    # Encolar tarea con retry
    q = q_high if body.high else q_default
    job = q.enqueue(
        worker_tasks.long_task,
        body.duration,
        body.task_name,
        idem_key,
        retry=Retry(max=3, interval=[10, 30, 60]),
        job_timeout=settings.TASK_TIMEOUT,
        result_ttl=settings.RESULT_TTL,
        failure_ttl=settings.FAILURE_TTL,
    )
    
    # Guardar en Redis para idempotencia
    redis_conn.setex(idem_key, ttl, job.id)
    return {"job_id": job.id, "queue": q.name}


@router.post("/a")
def create_task_a(body: TaskBody) -> dict:
    """Crear y encolar task_a para procesar un usuario.
    
    Tarea de ejemplo que simula procesamiento de datos de usuario.
    Dura aproximadamente 5 segundos.
    
    Args:
        body: Parámetros con user_id y prioridad
    
    Returns:
        Dict con job_id, queue y task name
    
    Example:
        POST /tasks/a
        {"user_id": 123, "high": false}
    """
    return _enqueue_task(
        task_name="task_a",
        task_func=worker_tasks.task_a,
        task_args=(body.user_id,),
        idem_payload={"user_id": body.user_id},
        high=body.high
    )


@router.post("/b")
def create_task_b(body: TaskBody) -> dict:
    """Crear y encolar task_b para procesar un usuario.
    
    Tarea de ejemplo que simula envío de notificaciones.
    Dura aproximadamente 5 segundos.
    
    Args:
        body: Parámetros con user_id y prioridad
    
    Returns:
        Dict con job_id, queue y task name
    
    Example:
        POST /tasks/b
        {"user_id": 456, "high": true}
    """
    return _enqueue_task(
        task_name="task_b",
        task_func=worker_tasks.task_b,
        task_args=(body.user_id,),
        idem_payload={"user_id": body.user_id},
        high=body.high
    )


@router.get("/{job_id}")
def get_task(job_id: str) -> dict:
    """Obtener el estado y resultado de una tarea por su job_id.
    
    Retorna información completa del job incluyendo:
    - Estado actual (queued, started, finished, failed, cancelled)
    - Resultado (si completó)
    - Metadatos (progreso, información adicional)
    - Timestamps de encolado, inicio y fin
    
    Args:
        job_id: ID único del job (UUID)
    
    Returns:
        Dict con toda la información del job
    
    Raises:
        HTTPException 404: Si el job_id no existe
    
    Example:
        GET /tasks/550e8400-e29b-41d4-a716-446655440000
        
        Respuesta:
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "finished",
            "result": {"type": "task_a", "completed": true},
            "meta": {"status": "done"},
            "enqueued_at": "2025-12-10T18:30:00Z",
            "started_at": "2025-12-10T18:30:05Z",
            "ended_at": "2025-12-10T18:30:10Z"
        }
    """
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except Exception:
        raise HTTPException(404, "Job no encontrado")
    
    return {
        "id": job.id,
        "status": job.get_status(),
        "result": job.result,
        "meta": job.meta,
        "enqueued_at": job.enqueued_at,
        "started_at": job.started_at,
        "ended_at": job.ended_at,
    }


@router.delete("/{job_id}")
def cancel_task(job_id: str) -> dict:
    """Solicitar cancelación cooperativa de una tarea en ejecución.
    
    La cancelación es cooperativa, lo que significa que la tarea debe
    verificar periódicamente si se solicitó su cancelación.
    
    Este endpoint:
    1. Marca el job como cancelado en RQ
    2. Crea una clave en Redis que la tarea puede verificar
    3. La tarea debe comprobar esta clave y terminar voluntariamente
    
    Args:
        job_id: ID único del job a cancelar
    
    Returns:
        Dict confirmando que se solicitó la cancelación
    
    Raises:
        HTTPException 404: Si el job_id no existe
    
    Example:
        DELETE /tasks/550e8400-e29b-41d4-a716-446655440000
        
        Respuesta:
        {"id": "550e8400-...", "cancel_requested": true}
    
    Note:
        La cancelación no es instantánea. La tarea puede tardar hasta
        que complete su iteración actual antes de detectar la cancelación.
    """
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except Exception:
        raise HTTPException(404, "Job no encontrado")
    
    # Marcar job como cancelado en RQ
    job.cancel()
    
    # Crear flag de cancelación en Redis para que el worker lo detecte
    redis_conn.setex(f"cancel:{job.id}", 3600, "1")
    
    return {"id": job.id, "cancel_requested": True}
#endregion ENDPOINTS
