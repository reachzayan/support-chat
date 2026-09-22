from app.workers.idle_closer import start_idle_closer, stop_idle_closer
from app.workers.kb_ingest_worker import start_ingest_worker, stop_ingest_worker
from app.workers.maintenance import start_maintenance_worker, stop_maintenance_worker


async def start_kb_workers() -> None:
    await start_ingest_worker()
    await start_idle_closer()
    await start_maintenance_worker()


async def stop_kb_workers() -> None:
    await stop_maintenance_worker()
    await stop_idle_closer()
    await stop_ingest_worker()
