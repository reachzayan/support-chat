from app.llm.intent import is_contact_request


def test_direct_contact_questions_are_detected() -> None:
    assert is_contact_request("how can I contact you") is True
    assert is_contact_request("How do I contact you?") is True
    assert is_contact_request("what's your phone number") is True
    assert is_contact_request("can I get your email address") is True
    assert is_contact_request("how do I reach you") is True
    assert is_contact_request("how can I get in touch") is True


def test_unrelated_questions_are_not_contact_requests() -> None:
    assert is_contact_request("how fast are results") is False
    assert is_contact_request("do you offer drug screening") is False
    # Contains "email" but is a real product question, not a request for our
    # contact details — bare word matches would false-positive here.
    assert is_contact_request("do you support email verification for employment") is False
