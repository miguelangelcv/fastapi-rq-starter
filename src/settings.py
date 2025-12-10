"""
Configuración de la aplicación.

Gestiona todas las variables de configuración usando Pydantic Settings.
Las variables pueden ser configuradas mediante:
- Variables de entorno
- Archivo .env en la raíz del proyecto
- Valores por defecto
"""

from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv()


class Settings(BaseSettings):
    """Configuración global de la aplicación.
    
    Attributes:
        REDIS_URL: URL de conexión a Redis (formato: redis://host:port/db)
        API_HOST: Host donde escucha la API
        API_PORT: Puerto donde escucha la API
        RESULT_TTL: Tiempo en segundos para mantener resultados exitosos (1 hora)
        FAILURE_TTL: Tiempo en segundos para mantener tareas fallidas (24 horas)
        TASK_TIMEOUT: Timeout máximo para ejecución de tareas (10 minutos)
        IDEMP_MARGIN: Margen adicional en segundos para TTL de idempotencia (5 minutos)
    """
    REDIS_URL: str = "redis://localhost:6379/0"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    RESULT_TTL: int = 3600  # 1 hora
    FAILURE_TTL: int = 86400  # 24 horas
    TASK_TIMEOUT: int = 600  # 10 minutos
    IDEMP_MARGIN: int = 300  # 5 minutos

# Instancia global de configuración
settings = Settings()
