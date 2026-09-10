from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.db import SessionDep
from app.repositories.site_repo import SiteRepository
from app.services.bot_eval import EvalCase, load_dataset, run_case
from app.settings import get_settings

router = APIRouter()


class EvalTurnIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_key: str
    messages: list[str] = Field(min_length=1)


class EvalRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_key: str | None = None
    family: str | None = None
    case_id: str | None = None


def eval_endpoints_enabled() -> bool:
    return get_settings().app_env != "production"


@router.post("/api/internal/eval/turn")
async def eval_turn(payload: EvalTurnIn, session: SessionDep) -> dict:
    if not eval_endpoints_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    site = await SiteRepository(session).get_by_key(payload.site_key)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    origin = site.allowed_origins[0] if site.allowed_origins else "http://localhost:3000"
    case = EvalCase(
        id="adhoc",
        family="adhoc",
        turns=tuple(payload.messages),
        expected_state="bot",
    )
    observed, _verdict = await run_case(session, site, case, parent_origin=origin)
    return {
        "state": observed.state,
        "role": observed.role,
        "body": observed.body,
        "system_reason": observed.system_reason,
        "source_title": observed.source_title,
    }


@router.post("/api/internal/eval/run")
async def eval_run(payload: EvalRunIn, session: SessionDep) -> dict:
    if not eval_endpoints_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    site_key, cases = load_dataset()
    key = payload.site_key or site_key
    site = await SiteRepository(session).get_by_key(key)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    origin = site.allowed_origins[0] if site.allowed_origins else "http://localhost:3000"
    selected = cases
    if payload.case_id:
        selected = tuple(item for item in cases if item.id == payload.case_id)
    elif payload.family:
        selected = tuple(item for item in cases if item.family.startswith(payload.family))
    results = []
    passed = 0
    for case in selected:
        observed, verdict = await run_case(session, site, case, parent_origin=origin)
        if verdict.passed:
            passed += 1
        results.append(
            {
                "id": case.id,
                "family": case.family,
                "passed": verdict.passed,
                "failures": list(verdict.failures),
                "state": observed.state,
                "reason": observed.system_reason,
                "body": observed.body,
            }
        )
    return {"site_key": key, "passed": passed, "total": len(results), "results": results}
