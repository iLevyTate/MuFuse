"""The crisis path (constitution III; 007 decisions 1-2).

What the person writes is checked before anything else. On a match the reply below is sent as it
is: no model sees the words, and no model can change the reply. The lines are those of the United
States (the owner's country) with the international directory for everyone else.
"""

from __future__ import annotations

import re

_PATTERNS = (
    r"\bsuicid\w*",
    r"\bkill(?:ing)?\s+my\s*self\b",
    r"\bend(?:ing)?\s+(?:my\s+(?:own\s+)?life|it\s+all)\b",
    r"\b(?:want|wanna|going)\s+to\s+die\b",
    r"\bdon'?t\s+want\s+to\s+(?:live|be\s+alive|be\s+here)\b",
    r"\bno\s+(?:reason|point)\s+(?:to|in)\s+(?:live|living|go\s+on)\b",
    r"\bbetter\s+off\s+(?:dead|without\s+me)\b",
    r"\bself[\s-]?harm\w*",
    r"\b(?:hurt|hurting|cut|cutting)\s+my\s*self\b",
    r"\boverdos\w*",
    r"\btoo\s+many\s+pills\b",
)
_CRISIS = re.compile("|".join(_PATTERNS), re.IGNORECASE)

CRISIS_REPLY = (
    "It sounds like things are very hard right now, and I'm glad you said it. MuFuse can't help "
    "with this, but people can, right now:\n"
    "- In the United States: call or text 988 (Suicide & Crisis Lifeline), any time.\n"
    "- If there is immediate danger: call 911.\n"
    "- Anywhere else: findahelpline.com lists free, confidential lines by country.\n"
    "If you can, tell someone near you how you're doing."
)


def is_crisis(text: str) -> bool:
    return _CRISIS.search(text) is not None
