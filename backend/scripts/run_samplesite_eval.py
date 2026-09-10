"""Hit the local eval endpoint with the SampleSite dataset and print a scorecard."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from app.chat.outcome_copy import OFF_TOPIC_LINE, TRANSFER_OFFER, WAITING_LINE
from app.services.bot_eval import ObservedReply, case_from_dict, score_case

DEFAULT_URL = "http://127.0.0.1:8000/api/internal/eval/turn"
DATASET = Path(__file__).resolve().parents[1] / "tests" / "evals" / "dataset" / "samplesite.json"


def _post(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise SystemExit(f"HTTP {exc.code} for {payload.get('messages')!r}: {detail}") from exc


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    raw = json.loads(DATASET.read_text())
    site_key = raw["site_key"]
    cases = [case_from_dict(item) for item in raw["cases"]]
    passed = 0
    rows: list[str] = []
    for case in cases:
        payload = _post(url, {"site_key": site_key, "messages": list(case.turns)})
        observed = ObservedReply(
            state=str(payload.get("state") or ""),
            role=str(payload.get("role") or ""),
            body=str(payload.get("body") or ""),
            system_reason=payload.get("system_reason"),
            source_title=payload.get("source_title"),
        )
        verdict = score_case(case, observed)
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


if __name__ == "__main__":
    raise SystemExit(main())
