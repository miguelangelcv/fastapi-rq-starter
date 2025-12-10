"""
Aplicación principal FastAPI + Redis Queue.

Este módulo inicializa la aplicación FastAPI y registra
todos los routers disponibles (tasks, queues, health).
"""

from fastapi import FastAPI

from routers import tasks, queues, health


# Inicializar aplicación FastAPI
app = FastAPI(
    title="FastAPI + Redis + RQ",
    version="1.0.0",
    description="API para encolar y gestionar tareas con Redis Queue"
)

# Registrar routers
app.include_router(health.router)
app.include_router(tasks.router)
app.include_router(queues.router)
