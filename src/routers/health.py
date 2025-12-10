"""
Router de health checks.

Proporciona endpoints para verificar el estado de salud
de la aplicación y sus dependencias.
"""

from fastapi import APIRouter, HTTPException

from utils import redis_conn


router = APIRouter(tags=["system"])


#region ENDPOINTS
@router.get("/health")
def health() -> dict:
    """Verificar el estado de salud de la aplicación.
    
    Verifica la conectividad con Redis para asegurar que el sistema
    está funcionando correctamente.
    
    Returns:
        Dict con status "ok" si todo funciona correctamente
    
    Raises:
        HTTPException 500: Si hay problemas de conectividad con Redis
    
    Example:
        GET /health
        
        Respuesta:
        {"status": "ok"}
    """
    try:
        redis_conn.ping()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, f"Redis error: {e}")
#endregion ENDPOINTS
