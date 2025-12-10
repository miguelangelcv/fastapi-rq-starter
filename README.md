# FastAPI + Redis + RQ + rq-dashboard (Starter)

Proyecto base para exponer una API FastAPI que encola tareas RQ en Redis, con:

- Idempotencia (evitar duplicados),
- Cancelación cooperativa,
- Progreso en `job.meta`,
- Prioridades por cola (`default`, `high`),
- Dashboard RQ.

## Arranque con Docker

```bash
docker compose up --build -d
```

- API: <http://localhost:8000> (docs en `/docs`)
- rq-dashboard: <http://localhost:9181>
- Redis: puerto 6379
- Workers: `default` y `high`

## Desarrollo local (Windows)

1. **Instalar dependencias:**
   ```powershell
   pip install -r requirements.txt
   ```

2. **Iniciar Redis** (con Docker):
   ```powershell
   docker run -d -p 6379:6379 redis:7
   ```

3. **Iniciar worker** (debe correr desde `src/`):
   ```powershell
   cd src
   rq worker default high --worker-class rq.worker.SimpleWorker
   ```
   > ⚠️ En Windows usa `SimpleWorker` porque `fork()` no está disponible.
   > ⚠️ Con `SimpleWorker` cada proceso es de un solo worker (sin multiproceso); si quieres más capacidad, abre más terminales y lanza más workers.

   Ejemplo (2 workers en paralelo, 2 terminales):

   ```powershell
   # Terminal 1
   cd src
   rq worker default high --worker-class rq.worker.SimpleWorker

   # Terminal 2
   cd src
   rq worker default high --worker-class rq.worker.SimpleWorker
   ```

4. **Iniciar API** (en otra terminal):
   ```powershell
   cd src
   uvicorn api:app --reload
   ```

5. **API disponible en:** <http://localhost:8000/docs>

## Endpoints

- **`GET /health`** → Verifica conectividad con Redis

- **`POST /tasks`** → Encola tarea `long_task` con idempotencia

   Body:

   ```json
   {
      "task_name": "long_task",
      "duration": 10,
      "payload": {"usuario_id": 123},
      "high": false
   }
   ```

   Respuesta:

   ```json
   {"job_id": "uuid", "queue": "default"}
   ```

   Duplicado:

   ```json
   {"duplicate": true, "job_id": "uuid"}
   ```

- **`POST /tasks/a`** → Demo `task_a` (procesar usuario)

   Body: `{"user_id": 123, "high": false}`

- **`POST /tasks/b`** → Demo `task_b` (notificaciones)

   Body: `{"user_id": 456, "high": true}`

- **`GET /tasks/{job_id}`** → Estado, resultado y progreso
- **`DELETE /tasks/{job_id}`** → Cancelación cooperativa
- **`GET /queues`** → Lista colas y su count
- **`DELETE /queues/{queue_name}/purge`** → Vacía una cola

## Desarrollo local (Linux/Mac)

```bash
# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Redis (con Docker)
docker run -d -p 6379:6379 redis:7

# Worker (desde src/)
cd src
rq worker default high

# API (en otra terminal, desde src/)
cd src
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

## Cómo funciona la idempotencia

El sistema evita ejecutar tareas duplicadas usando una clave única generada a partir de:

 
 
 
**Flujo:**

1. Se genera una clave única: `task:long_task:abc123`
2. Se verifica si existe en Redis → si existe, retorna el `job_id` existente
3. Si no existe, se encola la tarea y se guarda el `job_id` con TTL = `duration + IDEMP_MARGIN`
4. Cuando la tarea termina, el worker elimina la clave para permitir nuevas ejecuciones

 
 
 
**Resultado:** No se pueden crear tareas idénticas mientras una esté en cola o ejecutándose.

## Variables de entorno

Configurables en `.env` o docker-compose:

- `REDIS_URL`: URL de conexión a Redis (default: `redis://localhost:6379/0`)
- `API_HOST`: Host de la API (default: `0.0.0.0`)
- `API_PORT`: Puerto de la API (default: `8000`)
- `TASK_TIMEOUT`: Timeout máximo de tareas en segundos (default: `600`)
- `RESULT_TTL`: Tiempo de retención de resultados exitosos (default: `3600`)
- `FAILURE_TTL`: Tiempo de retención de tareas fallidas (default: `86400`)
- `IDEMP_MARGIN`: Margen adicional para el TTL de idempotencia (default: `300`)

## Producción: recomendaciones

- Usa múltiples workers para mejor concurrencia
- Configura workers separados para cada cola según prioridad
- Ajusta `TASK_TIMEOUT`, `RESULT_TTL`, `FAILURE_TTL` según necesidades
- Monitorea `FailedJobRegistry` para tareas fallidas
- Considera `rq-scheduler` para tareas programadas
- Redis en producción: habilita persistencia (AOF/RDB)
- En Linux/Mac, usa el worker por defecto (más eficiente que SimpleWorker)

## Depuración y ejecución local

### Lanzar la API en modo debug (Visual Studio Code)

Usa la configuración `API: Uvicorn (debug)` del `launch.json`:

```jsonc
{
   "name": "API: Uvicorn (debug)",
   "type": "debugpy",
   "request": "launch",
   "module": "uvicorn",
   "args": [
      "api:app",
      "--host", "0.0.0.0",
      "--port", "8000",
      "--reload",
      "--log-level", "debug"
   ],
   "cwd": "${workspaceFolder}/src",
   "env": {
      "REDIS_URL": "redis://localhost:6379/0"
   },
   "console": "integratedTerminal"
}
```

### Lanzar workers en modo debug (Visual Studio Code)

- **Windows (SimpleWorker, un proceso = un worker)**

   Usa la configuración `Worker: RQ (Windows SimpleWorker)` del `launch.json`:

   ```jsonc
   {
      "name": "Worker: RQ (Windows SimpleWorker)",
      "type": "debugpy",
      "request": "launch",
      "module": "rq",
      "args": ["worker", "default", "high", "--worker-class", "rq.worker.SimpleWorker"],
      "cwd": "${workspaceFolder}/src",
      "env": { "REDIS_URL": "redis://localhost:6379/0" }
   }
   ```

   Para más capacidad en Windows, abre varias terminales y lanza múltiples procesos con la misma configuración (cada uno es un worker).

- **Linux/Mac (worker por defecto con fork)**

   Usa la configuración `Worker: RQ (Linux/Mac)`:

   ```jsonc
   {
      "name": "Worker: RQ (Linux/Mac)",
      "type": "debugpy",
      "request": "launch",
      "module": "rq",
      "args": ["worker", "default", "high"],
      "cwd": "${workspaceFolder}/src",
      "env": { "REDIS_URL": "redis://localhost:6379/0" }
   }
   ```

   Para más capacidad en Linux/Mac, ejecuta más procesos worker (por ejemplo, con systemd/supervisor/docker-compose). RQ usa fork, por lo que cada proceso puede manejar múltiples jobs en paralelo.

### Multiplicando workers (resumen rápido)

- **Windows:** `SimpleWorker` → 1 proceso = 1 worker. Levanta N terminales si quieres N workers.
- **Linux/Mac:** usa worker por defecto → levanta varios procesos (p.ej. `rq worker default high` en varias terminales o via supervisor). Cada proceso usa fork para manejar múltiples jobs.

### Consejos de depuración

- Asegúrate de que `cwd` sea `src/` al lanzar API o workers (import paths correctos).
- Define `REDIS_URL` en el entorno si no usas el valor por defecto.
- Revisa los logs de RQ: al fallar una tarea verás el traceback en la terminal del worker.
- Para limpiar colas rápidamente: `DELETE /queues/{queue}/purge` o `rq empty default` (CLI).

## Licencia

MIT
