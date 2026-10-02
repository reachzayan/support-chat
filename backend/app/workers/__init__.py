from app.workers.durable_work import start_durable_work, stop_durable_work
from app.workers.health import start_worker_heartbeat, stop_worker_heartbeat
from app.workers.idle_closer import start_idle_closer, stop_idle_closer
from app.workers.kb_ingest_worker import start_ingest_worker, stop_ingest_worker
from app.workers.location_enrichment import start_location_enrichment, stop_location_enrichment
from app.workers.maintenance import start_maintenance_worker, stop_maintenance_worker
from app.workers.status_sampler import start_status_sampler, stop_status_sampler


async def start_kb_workers() -> None:
    await start_worker_heartbeat()
    await start_status_sampler()
    await start_durable_work()
    await start_ingest_worker()
    await start_idle_closer()
    await start_location_enrichment()
    await start_maintenance_worker()


async def stop_kb_workers() -> None:
    await stop_maintenance_worker()
    await stop_idle_closer()
    await stop_location_enrichment()
    await stop_ingest_worker()
    await stop_durable_work()
    await stop_status_sampler()
    await stop_worker_heartbeat()
