"""The output filter (constitution II; 007 decision 3): what a model wrote, checked before it is
shown. Descriptions of signals pass; statements about the person, conditions, diagnosis,
treatment advice, accuracy claims and mind reading do not. Drawn from the FDA general-wellness
guidance (United States). A blocked reply is replaced by the template answer, never repaired.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_STATES = (
    "anxious|stressed|calm|relaxed|focused|unfocused|distracted|tired|exhausted|sleepy|sad|happy|"
    "angry|bored|overwhelmed|frustrated|nervous|lonely|depressed|worried|upset|restless|agitated|"
    "content|excited|scared|afraid|fine|ok|okay|zoned out|mind[- ]wandering|daydreaming|"
    "drifting|struggling|burn(?:ed|t) out|in the zone|in flow|irritable|panicking|uneasy"
)
_ABOUT_YOU = (
    r"\byou(?:'re|\s+are|\s+seem|\s+sound|\s+look|\s+feel|\s+must\s+be|\s+might\s+be|"
    r"\s+may\s+be|\s+were|'ve\s+been|\s+have\s+been|\s+appear)\s+(?:\w+\s+){0,2}?(?:"
    + _STATES
    + r")\b"
)
_RULES: tuple[tuple[str, str], ...] = (
    ("about the person", _ABOUT_YOU),
    (
        "condition",
        r"\b(?:depression|adhd|add|ptsd|ocd|bipolar|autis\w*|schizophreni\w*|dementia|"
        r"epilep\w*|seizure\w*|concussion|insomnia|burnout|disorder\w*|syndrome\w*)\b",
    ),
    ("diagnosis", r"\b(?:diagnos\w*|abnormal\w*|pathologic\w*|symptom\w*|clinical\w*)\b"),
    (
        "treatment",
        r"\b(?:medication\w*|dosage|prescri\w*|see\s+a\s+(?:doctor|therapist|psychiatrist)|"
        r"talk(?:ing)?\s+to\s+a\s+(?:doctor|therapist|psychiatrist)|treatment)\b",
    ),
    (
        "accuracy claim",
        r"\b(?:accurately\s+(?:detects?|measures?|reads?|shows?)|medical[- ]grade|"
        r"proven|guarantee\w*|100\s*%)\b",
    ),
    (
        "mind reading",
        r"\b(?:you(?:'re|\s+are|\s+were)\s+thinking|your\s+thoughts\s+(?:are|were)|"
        r"i\s+can\s+(?:tell|see|read)\s+(?:what|that|how)\s+you)\b",
    ),
)
_COMPILED = tuple((name, re.compile(pattern, re.IGNORECASE)) for name, pattern in _RULES)


@dataclass(frozen=True)
class FilterResult:
    ok: bool
    reasons: tuple[str, ...]


def check(text: str) -> FilterResult:
    reasons = tuple(name for name, rule in _COMPILED if rule.search(text))
    return FilterResult(not reasons, reasons)
