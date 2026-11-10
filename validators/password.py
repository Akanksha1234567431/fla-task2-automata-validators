"""Application 3 - password *policy* verification.

Alphabet classes  Σ = {U, L, D, S, X}
    U = A-Z   L = a-z   D = 0-9   S = ASCII punctuation   X = anything else (space, control, non-ASCII)

Policy (all regular, hence checkable by a DFA):
    * 8 <= length <= 16
    * at least one of each class U, L, D, S
    * no character from class X

Two designs are built and proved equivalent:
    Design A - one hand-designed DFA whose state is (length so far, set of classes seen).
    Design B - the product (intersection) of six tiny DFAs, one per rule.
A third, scaled-down instance (MINI) exists only so that a full diagram fits on a page.
"""
import re
import string
from collections import deque
from functools import reduce
from typing import Iterable, Tuple

from automata import DEAD, DFA

ALPHABET = {"U", "L", "D", "S", "X"}
LEGEND = {
    "U": "uppercase A-Z",
    "L": "lowercase a-z",
    "D": "digit 0-9",
    "S": "ASCII punctuation",
    "X": "any other character",
}
REQUIRED = ("U", "L", "D", "S")
FORBIDDEN = ("X",)
LO, HI = 8, 16
_SPECIALS = set(string.punctuation)


def classify(ch: str) -> str:
    if "A" <= ch <= "Z":
        return "U"
    if "a" <= ch <= "z":
        return "L"
    if "0" <= ch <= "9":
        return "D"
    if ch in _SPECIALS:
        return "S"
    return "X"


# ---------------------------------------------------------------- Design A
def build_direct_dfa(lo: int, hi: int, required: Tuple[str, ...], alphabet: Iterable[str],
                     forbidden: Tuple[str, ...] = (), name: str = "Password DFA (direct)", classify_fn=classify) -> DFA:
    """State = (n, seen): n symbols read so far (0..hi) and which required classes have appeared."""
    alphabet = set(alphabet)
    full = (1 << len(required)) - 1

    def label(n: int, mask: int) -> str:
        seen = "".join(c for i, c in enumerate(required) if mask >> i & 1) or "-"
        return f"({n},{seen})"

    delta = {}
    points = {(0, 0)}
    pending = deque([(0, 0)])
    while pending:
        n, mask = pending.popleft()
        for a in sorted(alphabet):
            if a in forbidden or n == hi:
                target = None
            else:
                m = mask | (1 << required.index(a)) if a in required else mask
                target = (n + 1, m)
            delta[(label(n, mask), a)] = DEAD if target is None else label(*target)
            if target is not None and target not in points:
                points.add(target)
                pending.append(target)
    for a in alphabet:
        delta[(DEAD, a)] = DEAD
    states = {label(*p) for p in points} | {DEAD}
    accepting = {label(n, m) for (n, m) in points if lo <= n <= hi and m == full}
    return DFA(states, alphabet, delta, label(0, 0), accepting, name=name, classify=classify_fn)


# ---------------------------------------------------------------- Design B
def length_dfa(lo: int, hi: int, alphabet: Iterable[str]) -> DFA:
    alphabet = set(alphabet)
    delta = {}
    for i in range(hi + 1):
        for a in alphabet:
            delta[(f"n{i}", a)] = f"n{i + 1}" if i < hi else DEAD
    for a in alphabet:
        delta[(DEAD, a)] = DEAD
    return DFA({f"n{i}" for i in range(hi + 1)} | {DEAD}, alphabet, delta, "n0",
               {f"n{i}" for i in range(lo, hi + 1)}, name=f"length {lo}..{hi}")


def contains_dfa(sym: str, alphabet: Iterable[str]) -> DFA:
    alphabet = set(alphabet)
    delta = {("no", a): ("yes" if a == sym else "no") for a in alphabet}
    delta.update({("yes", a): "yes" for a in alphabet})
    return DFA({"no", "yes"}, alphabet, delta, "no", {"yes"}, name=f"contains {sym}")


def forbid_dfa(forbidden: Iterable[str], alphabet: Iterable[str]) -> DFA:
    alphabet, forbidden = set(alphabet), set(forbidden)
    delta = {("ok", a): (DEAD if a in forbidden else "ok") for a in alphabet}
    delta.update({(DEAD, a): DEAD for a in alphabet})
    return DFA({"ok", DEAD}, alphabet, delta, "ok", {"ok"}, name="no forbidden")


def build_product_dfa(lo: int, hi: int, required: Tuple[str, ...], alphabet: Iterable[str],
                      forbidden: Tuple[str, ...] = (), classify_fn=classify) -> DFA:
    parts = [length_dfa(lo, hi, alphabet)]
    parts += [contains_dfa(c, alphabet) for c in required]
    if forbidden:
        parts.append(forbid_dfa(forbidden, alphabet))
    product = reduce(lambda x, y: x.intersect(y), parts)
    product.name = "Password DFA (product of rule automata)"
    product.classify = classify_fn
    return product


# ------------------------------------------------------------ concrete DFAs
PASSWORD_DFA_A = build_direct_dfa(LO, HI, REQUIRED, ALPHABET, FORBIDDEN)
PASSWORD_DFA_B = build_product_dfa(LO, HI, REQUIRED, ALPHABET, FORBIDDEN)
PASSWORD_DFA = PASSWORD_DFA_A.minimize(name="Password DFA (minimal)")

# Scaled-down instance for drawing: letters/digits only, length 3..4, need >=1 letter and >=1 digit.
MINI_ALPHABET = {"L", "D"}
MINI_LEGEND = {"L": "letter", "D": "digit"}


def mini_classify(ch: str) -> str:
    return "D" if ch in string.digits else "L"


MINI_DFA = build_direct_dfa(3, 4, ("L", "D"), MINI_ALPHABET, name="Mini policy", classify_fn=mini_classify).minimize(
    name="Mini password policy (length 3-4, >=1 letter, >=1 digit) - minimal DFA")


def is_valid_password(text: str) -> bool:
    return PASSWORD_DFA.accepts(text)


def reference_password(text: str) -> bool:
    """Independent oracle (plain predicate) used only by the tests."""
    if not (LO <= len(text) <= HI):
        return False
    if any(not (c in string.ascii_letters + string.digits or c in string.punctuation) for c in text):
        return False
    return (any(c in string.ascii_uppercase for c in text)
            and any(c in string.ascii_lowercase for c in text)
            and any(c in string.digits for c in text)
            and any(c in string.punctuation for c in text))
