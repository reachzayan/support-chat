import re

from app.llm.safety_markers import SensitiveCategory, contains_injection_marker, strip_invisible
from app.services.kb_embedder import cosine
from app.services.kb_tokens import GENERIC_NOISE, is_overview_query, tokenize

CHITCHAT_TOKENS = frozenset(
    {
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank",
        "ok",
        "okay",
        "yes",
        "no",
        "yo",
        "bye",
        "goodbye",
        "cya",
        "later",
        "please",
        "sure",
        "yeah",
        "yep",
        "yup",
        "nah",
        "nope",
        "hiya",
        "howdy",
        "cheers",
        "goodnight",
        "morning",
        "afternoon",
        "evening",
        "welcome",
        "np",
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
IN_SCOPE_TOKENS = frozenset(
    {
        "background",
        "clinic",
        "collection",
        "compliance",
        "consortium",
        "cost",
        "dot",
        "drug",
        "drugs",
        "samplesite",
        "ecup",
        "employer",
        "fcra",
        "hiring",
        "location",
        "marijuana",
        "mro",
        "nationwide",
        "network",
        "occupational",
        "offer",
        "offering",
        "oral",
        "panel",
        "physical",
        "portal",
        "preemployment",
        "price",
        "pricing",
        "quote",
        "random",
        "result",
        "screen",
        "screening",
        "service",
        "services",
        "specimen",
        "test",
        "testing",
        "thc",
        "turnaround",
        "urine",
        "vaccine",
        "trucking",
        "truck",
        "fleet",
        "driver",
        "drivers",
        "company",
        "partner",
        "setup",
        "onboard",
        "onboarding",
        "hire",
        "hr",
        "employee",
        "employees",
        "account",
        "coverage",
        "program",
        "programs",
        "start",
        "started",
        "workplace",
        "lab",
        "labs",
        "package",
        "packages",
        "state",
        "states",
        "alcohol",
        "fmcsa",
        "clearinghouse",
    }
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
    "real person",
)
ESCALATE_WORDS = ("human", "agent", "specialist")
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
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b")
DL_RE = re.compile(r"\b[A-Z]\d{7,9}\b")
ISO_DOB_RE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")
WORD_RE = re.compile(r"[a-z0-9]+")
DIGITS_NEARBY_RE = re.compile(r"\d{2,}")
MRN_DIGITS_RE = re.compile(r"\d{5,}")

_DL_LEX = re.compile(r"driver'?s?\s+licen[cs]e\s+number")
_PLATE_LEX = re.compile(r"license\s+plate|plate\s+number")
_DOB_LEX = re.compile(r"date\s+of\s+birth|\bdob\b")
_MRN_LEX = re.compile(r"medical\s+record|\bmrn\b")
_SPECIMEN_LEX = re.compile(r"specimen\s+id|specimen\s+number|test\s+id|case\s+number")
_INDIVIDUAL_LEX = re.compile(
    r"\bmy\s+(?:(?:drug|alcohol|lab|screen(?:ing)?|test)\s+){0,3}"
    r"(?:result|report|status|screen|test)\b"
    r"|\bcase\s+(?:number|id)\b"
)
_MEDICAL_LEX = re.compile(r"medication|prescription|diagnosis|condition")
_SHOW_UP_LEX = re.compile(r"show\s+up|test\s+positive|on\s+(?:my|the)\s+(?:panel|screen|test)")
_LEGAL_CASE_LEX = re.compile(
    r"can\s+i\s+sue|is\s+this\s+legal|adverse\s+action|dispute\s+my\s+report|legal\s+advice"
)
_FIRST_PERSON = re.compile(r"\b(?:my|i|i'm|im|me)\b")


def normalize_text(value: str) -> str:
    cleaned = strip_invisible(value or "")
    collapsed = " ".join(cleaned.casefold().split())
    return collapsed


def is_escalate_request(value: str) -> bool:
    text = normalize_text(value)
    if any(phrase in text for phrase in ESCALATE_PHRASES):
        return True
    tokens = set(WORD_RE.findall(text))
    return any(word in tokens for word in ESCALATE_WORDS)


def is_chitchat(value: str) -> bool:
    tokens = tokenize(value)
    if tokens:
        return all(token in CHITCHAT_TOKENS for token in tokens)
    raw = set(WORD_RE.findall(normalize_text(value)))
    return not raw


def is_unrelated_request(value: str, evidence_tokens: set[str] | None = None) -> bool:
    if is_chitchat(value) or is_escalate_request(value) or is_disengage_request(value):
        return False
    if is_sensitive_request(value):
        return False
    if is_overview_query(value):
        return False
    tokens = set(tokenize(value))
    if not tokens:
        return True
    domain = set(IN_SCOPE_TOKENS)
    if evidence_tokens:
        domain |= set(evidence_tokens)
    overlap = (tokens - GENERIC_NOISE) & (domain - GENERIC_NOISE)
    return not bool(overlap)


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
    if any(phrase in text for phrase in DISENGAGE_PHRASES):
        return True
    tokens = set(WORD_RE.findall(text))
    return bool(tokens & ABUSE_TOKENS)


def classify_sensitive(text: str) -> SensitiveCategory:  # noqa: C901
    raw = strip_invisible(text or "")
    lowered = normalize_text(raw)
    if not lowered:
        return SensitiveCategory.NONE
    if SSN_RE.search(raw) or SSN_RE.search(lowered):
        return SensitiveCategory.SSN
    if DL_RE.search(raw) or _DL_LEX.search(lowered):
        return SensitiveCategory.DL
    if _PLATE_LEX.search(lowered) and DIGITS_NEARBY_RE.search(lowered):
        return SensitiveCategory.PLATE
    if ISO_DOB_RE.search(raw) or (_DOB_LEX.search(lowered) and DIGITS_NEARBY_RE.search(lowered)):
        return SensitiveCategory.DOB
    if _MRN_LEX.search(lowered) and MRN_DIGITS_RE.search(lowered):
        return SensitiveCategory.MRN
    if _SPECIMEN_LEX.search(lowered):
        return SensitiveCategory.SPECIMEN
    if _INDIVIDUAL_LEX.search(lowered):
        return SensitiveCategory.INDIVIDUAL_RESULT
    if _FIRST_PERSON.search(lowered) and _SHOW_UP_LEX.search(lowered):
        return SensitiveCategory.MEDICAL_DETAIL
    if _MEDICAL_LEX.search(lowered) and _FIRST_PERSON.search(lowered):
        return SensitiveCategory.MEDICAL_DETAIL
    if _LEGAL_CASE_LEX.search(lowered):
        return SensitiveCategory.LEGAL_CASE
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
