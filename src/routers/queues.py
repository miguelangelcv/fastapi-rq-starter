"""
Router de gestión de colas RQ.

Proporciona endpoints para inspeccionar y administrar
las colas de Redis Queue.
"""

from fastapi import APIRouter, HTTPException
from rq import Queue

from utils import redis_conn, q_default, q_high


router = APIRouter(prefix="/queues", tags=["queues"])


#region ENDPOINTS
@router.get("/")
def list_queues() -> list[dict]:
    """Listar todas las colas disponibles y su cantidad de tareas.
    
    Returns:
        Lista de diccionarios con información de cada cola:
        - name: Nombre de la cola
        - count: Número de tareas pendientes en la cola
    
    Example:
        GET /queues/
        
        Respuesta:
        [
            {"name": "default", "count": 5},
            {"name": "high", "count": 2}
        ]
    """
    queues = [q_default, q_high]
    return [{"name": q.name, "count": q.count} for q in queues]


@router.delete("/{queue_name}/purge")
def purge_queue(queue_name: str) -> dict:
    """Vaciar completamente una cola eliminando todas sus tareas pendientes.
    
    ADVERTENCIA: Esta operación es irreversible. Todas las tareas pendientes
    en la cola serán eliminadas permanentemente.
    
    Args:
        queue_name: Nombre de la cola a vaciar (ej: "default", "high")
    
    Returns:
        Dict confirmando la operación
    
    Raises:
        HTTPException 500: Si hay error al vaciar la cola
    
    Example:
        DELETE /queues/default/purge
        
        Respuesta:
        {"queue": "default", "purged": true}
    """
    try:
        q = Queue(queue_name, connection=redis_conn)
        q.empty()
        return {"queue": queue_name, "purged": True}
    except Exception as e:
        raise HTTPException(500, f"Error al vaciar la cola: {e}")
#endregion ENDPOINTS