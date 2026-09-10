import re

STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "am",
        "was",
        "were",
        "be",
        "how",
        "what",
        "when",
        "where",
        "why",
        "who",
        "of",
        "to",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "or",
        "and",
        "do",
        "does",
        "did",
        "our",
        "your",
        "this",
        "that",
        "it",
        "i",
        "we",
        "you",
    }
)
ALIASES = {
    "fast": "turnaround",
    "quick": "turnaround",
    "quickly": "turnaround",
    "result": "result",
    "results": "result",
    "employer": "employer",
    "employers": "employer",
    "clinic": "clinic",
    "clinics": "clinic",
    "location": "location",
    "locations": "location",
}
OVERVIEW_HINTS = (
    "what you guys do",
    "what do you guys do",
    "what do you do",
    "what you do",
    "who are you",
    "tell me about",
    "your services",
    "what services",
    "what does your company",
    "what does this company",
)
GENERIC_NOISE = frozenset(
    {
        "hour",
        "hours",
        "day",
        "days",
        "minute",
        "minutes",
    }
)
WEAK_OVERLAP = frozenset(
    {
        "drug",
        "drugs",
        "test",
        "testing",
        "screen",
        "screening",
        "result",
        "compliance",
    }
)
TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_query(value: str) -> str:
    return " ".join(value.casefold().split())


def tokenize(value: str) -> list[str]:
    text = normalize_query(value).replace("how long", "turnaround")
    tokens: list[str] = []
    for raw in TOKEN_RE.findall(text):
        if raw in STOP_WORDS or len(raw) < 2:
            continue
        tokens.append(ALIASES.get(raw, raw))
    return tokens


def search_tokens(value: str) -> list[str]:
    text = normalize_query(value).replace("how long", "turnaround")
    tokens: list[str] = []
    seen: set[str] = set()
    for raw in TOKEN_RE.findall(text):
        if raw in STOP_WORDS or len(raw) < 2:
            continue
        for token in (raw, ALIASES.get(raw, raw)):
            if token not in seen:
                seen.add(token)
                tokens.append(token)
    return tokens


def is_overview_query(value: str) -> bool:
    text = normalize_query(value)
    return any(hint in text for hint in OVERVIEW_HINTS)
