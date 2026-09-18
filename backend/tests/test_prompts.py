from app.llm.prompts import system_rules_for, visitor_turn_text

SCREENING_CLARIFY = "What would you like to know about screening or compliance?"
PRODUCTS_CLARIFY = "What would you like to know about our products or services?"


def test_system_rules_include_site_name_and_contract_blocks() -> None:
    rules = system_rules_for("Test Brand")
    assert "Test Brand" in rules
    for tag in ("<role>", "<grounding>", "<conversation>", "<response_style>", "<safety>"):
        assert tag in rules
    assert "Never ask a question" not in rules


def test_system_rules_redirect_off_topic_using_site_scope() -> None:
    easy = system_rules_for("SampleSite")
    other = system_rules_for("Sample Data Services")
    assert SCREENING_CLARIFY in easy
    assert PRODUCTS_CLARIFY not in easy
    assert PRODUCTS_CLARIFY in other
    assert SCREENING_CLARIFY not in other
    assert "use the name that appears in the evidence" in other.casefold()
    assert "contact details" in other.casefold()


def test_internal_site_labels_are_not_sent_to_the_model() -> None:
    for label in ("Demo", "SupportChat demo", "test"):
        rules = system_rules_for(label)
        assert "speaking for this brand" in rules
        assert f"speaking for {label}" not in rules
        assert "Brand:" not in visitor_turn_text(label, "What is SampleMail?")
        assert visitor_turn_text(label, "What is SampleMail?") == "What is SampleMail?"


def test_samplesite_keeps_its_real_brand_in_the_prompt() -> None:
    rules = system_rules_for("SampleSite")
    assert "speaking for SampleSite" in rules
    assert "Brand: SampleSite" in visitor_turn_text("SampleSite", "How fast are results?")
