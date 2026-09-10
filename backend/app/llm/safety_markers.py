"""Injection and output-leak markers for Plan 12 guardrails."""

from __future__ import annotations

import re
from enum import StrEnum


class SensitiveCategory(StrEnum):
    NONE = "none"
    SSN = "ssn"
    DL = "driver_license"
    PLATE = "plate"
    DOB = "dob"
    MRN = "mrn"
    SPECIMEN = "specimen_id"
    INDIVIDUAL_RESULT = "individual_result"
    MEDICAL_DETAIL = "medical_detail"
    LEGAL_CASE = "legal_case"


# Applied to visitor text and every retrieved document body BEFORE generation.
INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore prior instructions",
    "disregard the system",
    "reveal the system prompt",
    "reveal your prompt",
    "act as admin",
    "act as supportchat admin",
    "developer mode",
    "you are now",
    "jailbreak",
)

# Applied to the reply body only.
OUTPUT_LEAK_MARKERS = (
    "system prompt",
    "reveal your prompt",
    "here are my rules",
    "my instructions are",
    "i was told to",
    "supportchat assistant",
    "<script",
    "javascript:",
    "onerror=",
)

# Applied to the reply body: PII patterns.
OUTPUT_PII_PATTERNS = (
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b\d{9}\b"),  # SSN no dashes
    re.compile(r"\b[A-Z]\d{7,9}\b"),  # US driver's license shape
    re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b"),  # ISO DOB
    # Plate: require at least one letter so "24-48" / dates are not false positives.
    re.compile(r"\b(?=[A-Z0-9-]*[A-Z])[A-Z0-9]{2,3}-?[A-Z0-9]{2,4}\b"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),  # email
    re.compile(
        r"(?<!\d)(?:"
        r"(?:\+?1[-.\s]?)?(?:\(\d{3}\)\s*|\d{3}[-.\s])\d{3}[-.\s]?\d{4}"
        r"|\d{10}"
        r")(?!\d)"
    ),  # US phone
)

ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff\u00ad]")


def contains_injection_marker(text: str) -> bool:
    lowered = (text or "").casefold()
    return any(marker in lowered for marker in INJECTION_MARKERS)


def strip_invisible(text: str) -> str:
    return ZERO_WIDTH_RE.sub("", text or "")
