"""
Funciones worker para Redis Queue (RQ).

Estas funciones son ejecutadas por los workers de RQ cuando se procesan
tareas de las colas. Cada función debe:
- Recibir idem_key como último parámetro
- Liberar idem_key al terminar (finally o explícitamente)
- Actualizar job.meta para reportar progreso
- Manejar cancelaciones cooperativas cuando aplique
"""

import time
from rq import get_current_job
from utils import redis_conn


def long_task(duration: int, task_name: str, idem_key: str) -> str:
    """Tarea de duración variable con progreso y cancelación cooperativa.
    
    Ejecuta un loop durante 'duration' segundos, actualizando el progreso
    cada segundo. Verifica cancelaciones en cada iteración.
    
    Args:
        duration: Duración total en segundos
        task_name: Nombre de la tarea (para logging)
        idem_key: Clave de idempotencia en Redis a liberar al terminar
    
    Returns:
        String "cancelled" si fue cancelada, "done:{task_name}" si completó
    
    Raises:
        RuntimeError: Si no se puede obtener el job actual de RQ
    
    Note:
        Esta tarea actualiza job.meta con el progreso:
        {"progress": {"current": N, "total": duration, "name": task_name}}
    """
    job = get_current_job()
    if not job:
        raise RuntimeError("No se pudo obtener el job actual")
    
    # Loop principal con progreso
    for i in range(duration):
        time.sleep(1)
        
        # Actualizar progreso en job.meta
        job.meta = {
            "progress": {
                "current": i + 1,
                "total": duration,
                "name": task_name
            }
        }
        job.save_meta()
        
        # Verificar si se solicitó cancelación
        if redis_conn.get(f"cancel:{job.id}"):
            job.meta = {
                "status": "cancelled",
                "progress": job.meta.get("progress")
            }
            job.save_meta()
            redis_conn.delete(idem_key)
            return "cancelled"
    
    # Liberar lock de idempotencia al completar exitosamente
    redis_conn.delete(idem_key)
    return f"done:{task_name}"


def task_a(user_id: int, duration: int, idem_key: str) -> dict:
    """Tarea A de ejemplo - Procesar datos de usuario.
    
    Simula procesamiento de datos de un usuario. Tarea de demostración
    que dura 'duration' segundos.
    
    Args:
        user_id: ID del usuario a procesar
        duration: Duración total en segundos
        idem_key: Clave de idempotencia en Redis a liberar al terminar
    
    Returns:
        Dict con información del procesamiento:
        {"type": "task_a", "user_id": int, "completed": bool}
    
    Raises:
        RuntimeError: Si no se puede obtener el job actual de RQ
    
    Note:
        Esta tarea actualiza job.meta durante la ejecución:
        - Inicio: {"status": "running", "type": "task_a", "user_id": user_id}
        - Fin: {"status": "done", "result": {...}}
    """
    job = get_current_job()
    if not job:
        raise RuntimeError("No se pudo obtener el job actual")
    
    try:
        # Actualizar estado inicial
        job.meta = {
            "status": "running",
            "type": "task_a",
            "user_id": user_id
        }
        job.save_meta()
        
        # Simular trabajo ('duration' segundos)
        time.sleep(duration)
        
        # Preparar resultado
        result = {
            "type": "task_a",
            "user_id": user_id,
            "completed": True
        }
        
        # Actualizar estado final
        job.meta = {
            "status": "done",
            "result": result
        }
        job.save_meta()
        
        return result
    finally:
        # Siempre liberar la clave de idempotencia
        redis_conn.delete(idem_key)


def task_b(user_id: int, duration: int, idem_key: str) -> dict:
    """Tarea B de ejemplo - Procesar datos de usuario.
    
    Simula procesamiento de datos de un usuario. Tarea de demostración
    que dura 'duration' segundos.
    
    Args:
        user_id: ID del usuario a procesar
        duration: Duración total en segundos
        idem_key: Clave de idempotencia en Redis a liberar al terminar
    
    Returns:
        Dict con información del procesamiento:
        {"type": "task_b", "user_id": int, "completed": bool}
    
    Raises:
        RuntimeError: Si no se puede obtener el job actual de RQ
    
    Note:
        Esta tarea actualiza job.meta durante la ejecución:
        - Inicio: {"status": "running", "type": "task_b", "user_id": user_id}
        - Fin: {"status": "done", "result": {...}}
    """
    job = get_current_job()
    if not job:
        raise RuntimeError("No se pudo obtener el job actual")
    
    try:
        # Actualizar estado inicial
        job.meta = {
            "status": "running",
            "type": "task_b",
            "user_id": user_id
        }
        job.save_meta()
        
        # Simular trabajo ('duration' segundos)
        time.sleep(duration)
        
        # Preparar resultado
        result = {
            "type": "task_b",
            "user_id": user_id,
            "completed": True
        }
        
        # Actualizar estado final
        job.meta = {
            "status": "done",
            "result": result
        }
        job.save_meta()
        
        return result
    finally:
        # Siempre liberar la clave de idempotencia
        redis_conn.delete(idem_key)
