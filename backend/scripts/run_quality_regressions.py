"""Source-derived live cases for the September 18 quality fixes; no LLM grading.

Run with the local opt-in eval API on port 8001. Use a new output directory for
a fresh run; existing directories resume their saved conversations.
"""

import argparse
import asyncio
from pathlib import Path

from scripts.run_sampledata_eval import cases, run


def quality_cases() -> list[dict]:
    selected = {
        "mail_workflow",
        "hiring",
        "conflict",
        "mock_record",
        "competitor",
        "comparison",
        "short_followup",
        "spanish",
        "abuse",
        "employment_policy",
    }
    dataset = [case for case in cases() if case["id"] in selected]

    def add(name: str, turns: list[str], rubrics: list[str]) -> None:
        dataset.append(
            {"id": name, "family": "quality_regression", "turns": turns, "rubric": rubrics}
        )

    add(
        "spanish_mail",
        [
            "¿Qué hace SampleMail para un despacho de abogados?",
            "¿Las cartas parecen enviadas por nuestro despacho?",
            "¿Cuánto cuesta cada carta?",
        ],
        [
            "Spanish; physical printing/mail, verified addresses, tracking; native citations.",
            "Spanish; appears sent by client firm; native citation; no uncited marketing summary.",
            "Spanish specific pricing limitation, no invented prices or English fallback.",
        ],
    )
    add(
        "spanish_plain",
        ["Cual es la diferencia entre VPOE y eVPOE"],
        [
            "Spanish despite no accents/punctuation; employment vs electronic lookup; native citations.",
        ],
    )
    add(
        "spanish_policy",
        ["¿Puedo usar eVPOE para decidir si contrato a un empleado?"],
        [
            "Spanish; report published employment prohibition with native citations and qualifiers.",
        ],
    )
    add(
        "scope_separation",
        [
            "What do VPOE and VBANK each verify? Explain the difference.",
            "Does VBANK verify where somebody works too?",
        ],
        [
            "VPOE employment; VBANK bank accounts. Each scope supported by its own evidence, not a shared combined claim.",
            "Do not attribute employment verification to VBANK; use supported distinction or precise limitation.",
        ],
    )
    add(
        "profanity_request",
        ["This is stupid, explain SampleMail Plus"],
        [
            "Answer valid product request despite frustration and no question mark; native citation.",
        ],
    )
    add(
        "trace_exits",
        ["hello", "My SSN is 123-45-6789", "Yes please", "More context for the human"],
        [
            "Greeting with final decision; provider/retrieval explicitly not used.",
            "PII refusal and consent offer with final decision, no repeated identifier in replies.",
            "Queued handoff; trace includes completed/persisted redacted summary and provider attempt.",
            "Queued visitor-only turn with final no-bot decision; no replayed bot reply.",
        ],
    )
    return dataset


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("eval_artifacts/quality"))
    args = parser.parse_args()
    asyncio.run(run(dataset=quality_cases(), output=args.output))
