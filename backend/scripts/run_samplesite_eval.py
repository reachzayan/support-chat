"""Run the SampleSite eval dataset in-process and print a scorecard."""

from __future__ import annotations

import asyncio

from app.chat.outcome_copy import OFF_TOPIC_LINE, TRANSFER_OFFER, WAITING_LINE
from app.db import session_maker
from app.repositories.site_repo import SiteRepository
from app.services.bot_eval import load_dataset, run_case

FALLBACK_ORIGIN = "http://localhost:3000"


async def _run() -> int:
    site_key, cases = load_dataset()
    async with session_maker()() as session:
        site = await SiteRepository(session).get_by_key(site_key)
        if site is None:
            raise SystemExit(f"site {site_key!r} not found")
        origin = site.allowed_origins[0] if site.allowed_origins else FALLBACK_ORIGIN
        passed = 0
        rows: list[str] = []
        for case in cases:
            observed, verdict = await run_case(session, site, case, parent_origin=origin)
            mark = "PASS" if verdict.passed else "FAIL"
            if verdict.passed:
                passed += 1
            preview = (observed.body or "").replace("\n", " ")[:120]
            rows.append(
                f"{mark}  {case.id:36}  state={observed.state:8}  "
                f"reason={observed.system_reason or '-':16}  {preview}"
            )
            if not verdict.passed:
                for failure in verdict.failures:
                    rows.append(f"      {failure}")
                rows.append(f"      body={observed.body!r}")
    print("\n".join(rows))
    print(f"\n{passed}/{len(cases)} passed")
    print(f"OFF_TOPIC={OFF_TOPIC_LINE!r} WAITING={WAITING_LINE!r} TRANSFER={TRANSFER_OFFER!r}")
    return 0 if passed == len(cases) else 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
