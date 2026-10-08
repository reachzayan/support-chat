import re

from app.llm.safety_markers import SensitiveCategory, contains_injection_marker, strip_invisible
from app.services.kb_embedder import cosine
from app.services.kb_tokens import tokenize

CHITCHAT_TOKENS = frozenset(
    {
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank",
        "yo",
        "bye",
        "goodbye",
        "cya",
        "later",
        "please",
        "hiya",
        "howdy",
        "cheers",
        "goodnight",
        "morning",
        "afternoon",
        "evening",
        "welcome",
    }
)
CONSENT_TOKENS = frozenset({"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "please", "yea"})
DECLINE_TOKENS = frozenset({"no", "nope", "nah"})
CONSENT_PHRASES = ("go ahead", "transfer me", "please transfer", "yes please")
DECLINE_PHRASES = ("no thanks", "no thank", "never mind", "nevermind")
DISENGAGE_PHRASES = (
    "your secrets",
    "give me your secret",
    "show me your secret",
    "system prompt",
)
ABUSE_TOKENS = frozenset(
    {
        "fuck",
        "fucking",
        "fucker",
        "shit",
        "asshole",
        "bastard",
        "bitch",
        "cunt",
        "whore",
        "slut",
        "dickhead",
        "motherfucker",
        "retard",
        "stfu",
    }
)

ESCALATE_PHRASES = (
    "talk to a person",
    "speak to a person",
    "speak with a person",
    "real person",
)
ESCALATE_WORDS = ("human", "agent", "specialist")
CONTACT_PHRASES = (
    "contact you",
    "contact us",
    "your contact",
    "get in touch",
    "reach you",
    "reach out to you",
    "call you",
    "your email",
    "your phone",
    "your number",
    "how do i contact",
    "how can i contact",
    "how do i reach",
    "how can i reach",
)
INTENT_FLOOR = 0.75
PROTOTYPE_PHRASES: dict[str, str] = {
    "pricing": "how much does a screening cost",
    "turnaround": "how long until results",
    "dot": "DOT drug testing requirements",
    "fcra": "Fair Credit Reporting Act adverse action",
    "portal": "client portal login",
}
INTENT_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pricing", ("pricing", "price", "cost", "quote")),
    ("turnaround", ("turnaround", "how long", "fast", "quick", "quickly")),
    ("dot", ("dot",)),
    ("fcra", ("fcra",)),
    ("portal", ("portal",)),
)
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
NINE_DIGITS_RE = re.compile(r"\b\d{9}\b")
_SSN_LEX = re.compile(r"\bssn\b|social\s+security")
_SSN_SHARE_LEX = re.compile(
    r"\b(?:my|his|her|their)\s+(?:ssn|social\s+security)\b|\bssn\s*(?:is|:|#)"
)
DL_RE = re.compile(r"\b[A-Z]\d{7,9}\b")
ISO_DOB_RE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")
WORD_RE = re.compile(r"[a-z0-9]+")
DIGITS_NEARBY_RE = re.compile(r"\d{2,}")
MRN_DIGITS_RE = re.compile(r"\d{5,}")

_DL_LEX = re.compile(r"driver'?s?\s+licen[cs]e(?:\s+number)?|\bdl\s+number")
_VALUE_DIGITS_RE = re.compile(r"\d{5,}")
_PLATE_LEX = re.compile(r"license\s+plate|plate\s+number")
_DOB_LEX = re.compile(r"date\s+of\s+birth|\bdob\b")
_MRN_LEX = re.compile(r"medical\s+record|\bmrn\b")
_SPECIMEN_LEX = re.compile(r"specimen\s+id|specimen\s+number|test\s+id|case\s+(?:number|id)")
_INDIVIDUAL_LEX = re.compile(
    r"\bmy\s+(?:(?:drug|alcohol|lab|screen(?:ing)?|test|background)\s+){0,3}results?\b"
    r"|\b(?:did|will|can)\s+i\s+(?:pass|fail)\b"
)
_HOW_TO_VIEW_LEX = re.compile(
    r"\b(?:how|where)\b[^?]*\b(?:view|find|see|access|get|check|download)\b"
)
_MEDICAL_LEX = re.compile(r"medication|prescription|diagnosis|(?:medical|health)\s+condition")
_TAKING_LEX = re.compile(
    r"\bi(?:'m|\s+am)?\s+(?:take|taking|on|use|using)\b|medication|prescription"
)
_MEDICAL_ADVICE_LEX = re.compile(
    r"chest\s+pain|\ber\b|emergency\s+room|\bdiagnos(?:e|is)\b|\bsymptoms?\b"
)
_SHOW_UP_LEX = re.compile(r"show\s+up|test\s+positive")
_LEGAL_CASE_LEX = re.compile(
    r"can\s+i\s+sue|is\s+this\s+legal|adverse\s+action\s+(?:against|on|toward)\s+me"
    r"|dispute\s+my\s+report|legal\s+advice"
)
_LOOKUP_LEX = re.compile(r"\b(?:look\s*up|pull|retrieve|access)\b")
_FIRST_PERSON = re.compile(r"\b(?:my|i|i'm|im|me)\b")


def normalize_text(value: str) -> str:
    cleaned = strip_invisible(value or "")
    collapsed = " ".join(cleaned.casefold().split())
    return collapsed


def is_escalate_request(value: str) -> bool:
    text = normalize_text(value)
    target = r"(?:human(?: agent)?|agent|specialist|(?:real )?person|representative)"
    for clause in re.split(r"[.!?;]|\b(?:but|instead)\b", text):
        clause = clause.strip()
        if re.fullmatch(rf"(?:please )?(?:a )?{target}(?: please)?", clause):
            return True
        request = re.search(
            rf"\b(?:i (?:want|need|would like)|i['\u2019]d like|"
            rf"connect(?: me)?(?: (?:to|with))?|transfer(?: me)?(?: (?:to|with))?|"
            rf"speak (?:to|with)|talk (?:to|with)|get me|give me)"
            rf"\s+(?:(?:a|an|the|your|our|live|real)\s+){{0,2}}{target}\b"
            rf"(?!(?:'s)?\s+(?:e-?mail|phone|number|contact|extension|address)\b)",
            clause,
        )
        if request and not re.search(
            r"\b(?:not|never|don't|dont|no)\b[^.!?;]*$", clause[: request.start()]
        ):
            return True
    return False


def is_handoff_declined(value: str) -> bool:
    return bool(
        re.search(
            r"\b(?:don't|do not|dont|not|no|never)\b[^.!?;]{0,45}"
            r"\b(?:human|agent|specialist|person|representative)\b",
            normalize_text(value),
        )
    ) and not is_escalate_request(value)


def is_contact_request(value: str) -> bool:
    text = normalize_text(value)
    if not text:
        return False
    return any(phrase in text for phrase in CONTACT_PHRASES)


def is_chitchat(value: str) -> bool:
    tokens = tokenize(value)
    if tokens:
        return all(token in CHITCHAT_TOKENS for token in tokens)
    raw = set(WORD_RE.findall(normalize_text(value)))
    return not raw


def is_transfer_consent(value: str) -> bool:
    text = normalize_text(value)
    if not text:
        return False
    if any(phrase in text for phrase in CONSENT_PHRASES):
        return True
    tokens = set(WORD_RE.findall(text))
    return bool(tokens) and tokens <= CONSENT_TOKENS


def is_transfer_decline(value: str) -> bool:
    text = normalize_text(value)
    if not text:
        return False
    if any(phrase in text for phrase in DECLINE_PHRASES):
        return True
    tokens = set(WORD_RE.findall(text))
    return bool(tokens) and tokens <= DECLINE_TOKENS


def is_disengage_request(value: str) -> bool:
    if contains_injection_marker(value):
        return True
    text = normalize_text(value)
    if not text:
        return False
    return any(phrase in text for phrase in DISENGAGE_PHRASES)


def classify_sensitive(text: str) -> SensitiveCategory:  # noqa: C901
    raw = strip_invisible(text or "")
    lowered = normalize_text(raw)
    if not lowered:
        return SensitiveCategory.NONE
    if (
        SSN_RE.search(raw)
        or SSN_RE.search(lowered)
        or _SSN_SHARE_LEX.search(lowered)
        or (_SSN_LEX.search(lowered) and NINE_DIGITS_RE.search(lowered))
    ):
        return SensitiveCategory.SSN
    if DL_RE.search(raw) or (_DL_LEX.search(lowered) and _VALUE_DIGITS_RE.search(lowered)):
        return SensitiveCategory.DL
    if _PLATE_LEX.search(lowered) and DIGITS_NEARBY_RE.search(lowered):
        return SensitiveCategory.PLATE
    if ISO_DOB_RE.search(raw) or (_DOB_LEX.search(lowered) and DIGITS_NEARBY_RE.search(lowered)):
        return SensitiveCategory.DOB
    if _MRN_LEX.search(lowered):
        if MRN_DIGITS_RE.search(lowered):
            return SensitiveCategory.MRN
        if _FIRST_PERSON.search(lowered) or _LOOKUP_LEX.search(lowered):
            return SensitiveCategory.MEDICAL_DETAIL
    if _SPECIMEN_LEX.search(lowered) and _VALUE_DIGITS_RE.search(lowered.replace("-", "")):
        return SensitiveCategory.SPECIMEN
    if (
        _SHOW_UP_LEX.search(lowered)
        and _FIRST_PERSON.search(lowered)
        and _TAKING_LEX.search(lowered)
    ):
        return SensitiveCategory.MEDICAL_DETAIL
    if _LEGAL_CASE_LEX.search(lowered):
        return SensitiveCategory.LEGAL_CASE
    if _INDIVIDUAL_LEX.search(lowered) and not _HOW_TO_VIEW_LEX.search(lowered):
        return SensitiveCategory.INDIVIDUAL_RESULT
    if _MEDICAL_ADVICE_LEX.search(lowered):
        return SensitiveCategory.MEDICAL_DETAIL
    if _MEDICAL_LEX.search(lowered) and _FIRST_PERSON.search(lowered):
        return SensitiveCategory.MEDICAL_DETAIL
    return SensitiveCategory.NONE


def is_sensitive_request(value: str) -> bool:
    return classify_sensitive(value) is not SensitiveCategory.NONE


def classify_intent(value: str) -> str:
    if is_escalate_request(value):
        return "escalate"
    category = classify_sensitive(value)
    if category is not SensitiveCategory.NONE:
        return "other"
    text = normalize_text(value)
    for intent, terms in INTENT_TERMS:
        if any(term in text for term in terms):
            return intent
    return "other"


def intent_from_query_vector(query_vector: list[float], prototypes: dict[str, list[float]]) -> str:
    best_name = "other"
    best = -1.0
    for name, proto in prototypes.items():
        score = cosine(query_vector, proto)
        if score > best:
            best = score
            best_name = name
    if best >= INTENT_FLOOR:
        return best_name
    return "other"


async def embed_intent_prototypes(embedder) -> dict[str, list[float]]:
    names = list(PROTOTYPE_PHRASES.keys())
    vectors = await embedder.embed_documents([PROTOTYPE_PHRASES[name] for name in names])
    return dict(zip(names, vectors, strict=True))
