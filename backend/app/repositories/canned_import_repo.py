import hashlib
import json
from dataclasses import asdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.models.canned_import import CannedImport, CannedImportRow
from app.models.user import User
from app.services.canned_import import ImportPlanRow


class CannedImportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        raw: bytes,
        filename: str,
        staff: User | None,
        counts: dict[str, int],
        planned: list[ImportPlanRow],
        reply_ids: dict[int, UUID | None],
    ) -> None:
        batch = CannedImport(
            filename=filename.replace("\\", "/").rsplit("/", 1)[-1].strip()[:255]
            or "canned-responses.csv",
            uploaded_by=staff.id if staff else None,
            uploaded_by_name=staff.display_name if staff else None,
            sha256=hashlib.sha256(raw).hexdigest(),
            raw_csv=raw,
            **counts,
        )
        self._session.add(batch)
        await self._session.flush()
        self._session.add_all(
            [
                CannedImportRow(
                    import_id=batch.id,
                    row_number=index + 1,
                    reply_id=reply_ids.get(index),
                    action=row.action,
                    snapshot=json.loads(json.dumps(asdict(row), default=str)),
                )
                for index, row in enumerate(planned)
            ]
        )

    async def list_batches(self, offset: int, limit: int) -> tuple[list[CannedImport], bool]:
        result = await self._session.execute(
            select(CannedImport)
            .options(defer(CannedImport.raw_csv))
            .order_by(CannedImport.id.desc())
            .offset(offset)
            .limit(limit + 1)
        )
        batches = list(result.scalars())
        return batches[:limit], len(batches) > limit

    async def get_batch(self, import_id: int) -> CannedImport | None:
        return await self._session.get(CannedImport, import_id)

    async def rows(
        self, import_id: int, offset: int, limit: int
    ) -> tuple[list[CannedImportRow], bool]:
        result = await self._session.execute(
            select(CannedImportRow)
            .where(CannedImportRow.import_id == import_id)
            .order_by(CannedImportRow.row_number)
            .offset(offset)
            .limit(limit + 1)
        )
        rows = list(result.scalars())
        return rows[:limit], len(rows) > limit
