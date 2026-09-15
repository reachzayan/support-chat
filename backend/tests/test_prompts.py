from app.llm.prompts import SYSTEM_RULES, system_rules_for


def test_system_rules_include_site_name_and_contract_blocks() -> None:
    rules = system_rules_for("Test Brand")
    assert "Test Brand" in rules
    for tag in ("<role>", "<grounding>", "<conversation>", "<response_style>", "<safety>"):
        assert tag in rules
    assert "Never ask a question" not in rules


def test_system_rules_forbids_uncited_assertions() -> None:
    assert (
        "Never state facts, numbers, prices, durations, regulations, or program names "
        "unless they come from a provided source and you cite that source using native citations"
    ) in SYSTEM_RULES
    assert (
        "If evidence is insufficient, ask a single clarifying question ending in `?` — do not guess"
    ) in SYSTEM_RULES


def test_system_rules_has_clarifier_example() -> None:
    examples = SYSTEM_RULES.split("<examples>", 1)[1].split("</examples>", 1)[0]
    answers = [
        line.removeprefix("Answer: ").strip()
        for line in examples.splitlines()
        if line.startswith("Answer: ")
    ]
    clarifiers = [
        answer
        for answer in answers
        if answer.endswith("?") and not any(ch in answer[:-1] for ch in ".!?")
    ]
    assert clarifiers, "expected a single-sentence clarifier example ending in ?"
