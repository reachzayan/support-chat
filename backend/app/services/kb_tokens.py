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
        "my",
        "us",
        "they",
        "them",
        "their",
        "will",
        "would",
        "should",
        "could",
        "have",
        "has",
        "had",
        "been",
        "provide",
        "provides",
        "providing",
        "help",
        "need",
        "please",
        "tell",
        "give",
        "list",
        "looking",
        "can",
        "me",
        "offer",
        "offering",
        "offers",
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
    "cost": "pricing",
    "costs": "pricing",
    "price": "pricing",
    "prices": "pricing",
    "interpret": "interpretation",
    "interpreting": "interpretation",
    "interpreted": "interpretation",
}
OVERVIEW_HINTS = (
    "what you guys do",
    "what do you guys do",
    "what do you do",
    "what you do",
    "who are you",
    "tell me about your company",
    "tell me about this company",
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
        "report",
    }
)
TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_query(value: str) -> str:
    return " ".join(value.casefold().split())


def _rewrite_phrases(value: str) -> str:
    return (
        normalize_query(value)
        .replace("how long", "turnaround")
        .replace("how much", "pricing")
        .replace("pending charges", "interpretation")
        .replace("pending charge", "interpretation")
        .replace("set up", "setup")
        .replace("sign up", "setup")
    )


def tokenize(value: str) -> list[str]:
    tokens: list[str] = []
    for raw in TOKEN_RE.findall(_rewrite_phrases(value)):
        if raw in STOP_WORDS or len(raw) < 2:
            continue
        tokens.append(ALIASES.get(raw, raw))
    return tokens


def search_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for raw in TOKEN_RE.findall(_rewrite_phrases(value)):
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
