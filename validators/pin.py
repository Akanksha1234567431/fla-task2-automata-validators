"""Application 1 - ATM PIN verification.

Syntax rule (regular):   L_PIN = D^4      over   Σ = {D, X}
    D = an ASCII digit 0-9, X = any other character.

Whether the PIN *matches the card holder's PIN* is a semantic / business rule
that needs the bank's database.  A DFA cannot decide it.  What a DFA *can* model
is the session control flow around it (the retry limiter below), driven by the
event "ok"/"bad" that the bank back-end supplies.
"""
import re
import string

from automata import DEAD, DFA

ALPHABET = {"D", "X"}
LEGEND = {"D": "ASCII digit 0-9", "X": "any other character"}


def classify(ch: str) -> str:
    return "D" if ch in string.digits else "X"


def build_pin_dfa(length: int = 4) -> DFA:
    states = {f"q{i}" for i in range(length + 1)} | {DEAD}
    delta = {}
    for i in range(length):
        delta[(f"q{i}", "D")] = f"q{i + 1}"
        delta[(f"q{i}", "X")] = DEAD
    delta[(f"q{length}", "D")] = DEAD  # a 5th digit is one too many
    delta[(f"q{length}", "X")] = DEAD
    for a in ALPHABET:
        delta[(DEAD, a)] = DEAD
    return DFA(states, set(ALPHABET), delta, "q0", {f"q{length}"},
               name=f"ATM PIN DFA (exactly {length} digits)", classify=classify)


PIN_DFA = build_pin_dfa(4)
PIN6_DFA = build_pin_dfa(6)  # variant: banks that issue 6-digit PINs


def is_valid_pin(text: str) -> bool:
    return PIN_DFA.accepts(text)


def reference_pin(text: str) -> bool:
    """Independent oracle (Python regex) used only by the tests."""
    return re.fullmatch(r"[0-9]{4}", text) is not None


# --------------------------------------------------------------------------
# ATM session retry limiter: a DFA over *events*, not characters.
#   ok  = the back-end says the PIN matched      (semantic check, done outside)
#   bad = the back-end says the PIN did not match
# L = { bad^k ok w : k <= max_failures-1, w in {ok,bad}* }  - accepted = authenticated.
# --------------------------------------------------------------------------
RETRY_ALPHABET = {"ok", "bad"}
RETRY_LEGEND = {"ok": "PIN matched (bank said yes)", "bad": "PIN did not match (bank said no)"}


def build_retry_dfa(max_attempts: int = 3) -> DFA:
    fail = [f"fail{i}" for i in range(max_attempts)]
    states = set(fail) | {"AUTH", "LOCKED"}
    delta = {}
    for i, s in enumerate(fail):
        delta[(s, "ok")] = "AUTH"
        delta[(s, "bad")] = fail[i + 1] if i + 1 < max_attempts else "LOCKED"
    for a in RETRY_ALPHABET:
        delta[("AUTH", a)] = "AUTH"      # session proceeds; later events are irrelevant here
        delta[("LOCKED", a)] = "LOCKED"  # card retained, absorbing
    return DFA(states, set(RETRY_ALPHABET), delta, fail[0], {"AUTH"},
               name=f"ATM retry limiter ({max_attempts} attempts)")


RETRY_DFA = build_retry_dfa(3)
