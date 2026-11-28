"""The two parts of 007 no model can change: the crisis path and the output filter."""

from __future__ import annotations

import pytest

from mufuse.chat.crisis import CRISIS_REPLY, is_crisis
from mufuse.chat.filter import check

# The crisis path ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "I want to kill myself",
        "i keep thinking about suicide",
        "Sometimes I think everyone would be better off dead without me",
        "I don't want to live anymore",
        "I've been self-harming again",
        "thinking about hurting myself",
        "I want to end my life",
        "took too many pills, overdose",
        "there's no reason to live",
        "I want to die",
    ],
)
def test_crisis_words_are_caught(text: str) -> None:
    assert is_crisis(text)


@pytest.mark.parametrize(
    "text",
    [
        "what are you seeing?",
        "this meeting is killing me",  # a figure of speech, not about the self
        "my phone died",
        "I was daydreaming about the weekend",
        "deadline is tomorrow",
    ],
)
def test_ordinary_words_are_not_caught(text: str) -> None:
    assert not is_crisis(text)


def test_the_crisis_reply_is_fixed_and_names_real_lines() -> None:
    lines = CRISIS_REPLY.splitlines()
    assert (
        "- In the United States: call or text 988 (Suicide & Crisis Lifeline), any time." in lines
    )
    assert "- If there is immediate danger: call 911." in lines
    assert "- Anywhere else: findahelpline.com lists free, confidential lines by country." in lines
    assert check(CRISIS_REPLY).ok  # it passes its own filter


# The output filter ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "You are anxious right now.",
        "You're clearly stressed.",
        "You seem distracted.",
        "you sound tired",
        "You must be bored.",
        "This pattern is typical of ADHD.",
        "Your signals suggest depression.",
        "This could be an anxiety disorder.",
        "I can't diagnose you, but this looks abnormal.",
        "You should see a doctor about this.",
        "Consider talking to a therapist about your medication.",
        "MuFuse accurately detects mind wandering.",
        "This is clinically validated.",
        "You are thinking about work.",
        "I can tell what you are feeling.",
        "Medical-grade readings show this.",
        "These are symptoms of burnout.",
    ],
)
def test_banned_phrasings_are_blocked(text: str) -> None:
    result = check(text)
    assert not result.ok
    assert result.reasons


@pytest.mark.parametrize(
    "text",
    [
        "Blink rate is about double your baseline for four minutes. Heart rate is steady.",
        "Good signal on both forehead sensors.",
        "What was going on for you just then?",
        "Alpha is a little lower than usual.",
        "You have good signal on AF7 and AF8.",
        "You answered 'planning' at the last check-in.",
    ],
)
def test_descriptions_pass(text: str) -> None:
    assert check(text).ok, check(text).reasons
