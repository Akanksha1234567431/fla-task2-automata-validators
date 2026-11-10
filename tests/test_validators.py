"""Tests for the three validators.

Three layers of evidence:
  1. the hand-picked accepted / rejected strings in cases.json (shown in the README),
  2. exhaustive comparison with an independent oracle over *every* class string up to a length,
  3. seeded random / mutation testing on real characters.
"""
import itertools
import json
import random
import string
from pathlib import Path

import pytest

from validators import email, password, pin

CASES = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))

APPS = {
    "pin": (pin.is_valid_pin, pin.reference_pin),
    "email": (email.is_valid_email, email.reference_email),
    "password": (password.is_valid_password, password.reference_password),
}


# ------------------------------------------------------------ 1. listed cases
@pytest.mark.parametrize("app", APPS)
def test_minimum_number_of_cases(app):
    assert len(CASES[app]["accept"]) >= 5
    assert len(CASES[app]["reject"]) >= 5


@pytest.mark.parametrize("app", APPS)
def test_accepted_examples(app):
    dfa_check, oracle = APPS[app]
    for s in CASES[app]["accept"]:
        assert dfa_check(s), f"{app}: expected ACCEPT for {s!r}"
        assert oracle(s), f"{app}: oracle disagrees for {s!r}"


@pytest.mark.parametrize("app", APPS)
def test_rejected_examples(app):
    dfa_check, oracle = APPS[app]
    for s, why in CASES[app]["reject"]:
        assert not dfa_check(s), f"{app}: expected REJECT for {s!r} ({why})"
        assert not oracle(s), f"{app}: oracle disagrees for {s!r}"


# ------------------------------------- 2. exhaustive check over class strings
REPRESENTATIVE = {
    "pin": {"D": "7", "X": "#"},
    "email": {"L": "a", "N": "7", "P": "+", "H": "-", ".": ".", "@": "@", "X": "#"},
    "password": {"U": "A", "L": "a", "D": "5", "S": "$", "X": " "},
}
DFAS = {"pin": pin.PIN_DFA, "email": email.EMAIL_DFA, "password": password.PASSWORD_DFA}
MAX_LEN = {"pin": 7, "email": 7, "password": 8}


@pytest.mark.parametrize("app", APPS)
def test_exhaustive_against_oracle(app):
    dfa, rep, oracle = DFAS[app], REPRESENTATIVE[app], APPS[app][1]
    symbols = sorted(rep)
    checked = 0
    for n in range(MAX_LEN[app] + 1):
        for word in itertools.product(symbols, repeat=n):
            text = "".join(rep[a] for a in word)
            assert dfa.accepts_symbols(word) == oracle(text), f"{app}: mismatch on {text!r}"
            checked += 1
    assert checked > 100


def test_class_representatives_classify_correctly():
    for app, mod in (("pin", pin), ("email", email), ("password", password)):
        for sym, ch in REPRESENTATIVE[app].items():
            assert mod.classify(ch) == sym


# ------------------------------------------------------ 3. random / mutation
def _mutate(rng, s, pool):
    s = list(s)
    for _ in range(rng.randint(0, 2)):
        op = rng.choice("ids") if s else "i"
        pos = rng.randrange(len(s) + 1) if op == "i" else (rng.randrange(len(s)) if s else 0)
        if op == "i":
            s.insert(pos, rng.choice(pool))
        elif op == "d" and s:
            del s[pos]
        elif s:
            s[pos] = rng.choice(pool)
    return "".join(s)


def test_random_pin():
    rng = random.Random(1)
    pool = string.digits * 3 + " a.-\n٣"
    for _ in range(20000):
        s = "".join(rng.choice(pool) for _ in range(rng.randint(0, 6)))
        assert pin.is_valid_pin(s) == pin.reference_pin(s), repr(s)


def test_random_email_valid_by_construction_then_mutated():
    rng = random.Random(2)
    word_pool = string.ascii_letters + string.digits + "_+-"
    label_pool = string.ascii_letters + string.digits
    mut_pool = list(string.ascii_letters + string.digits + "_+-.@# é")
    accepted = rejected = 0
    for _ in range(20000):
        local = ".".join("".join(rng.choice(word_pool) for _ in range(rng.randint(1, 5)))
                         for _ in range(rng.randint(1, 3)))
        labels = []
        for _ in range(rng.randint(1, 3)):
            lab = "".join(rng.choice(label_pool) for _ in range(rng.randint(1, 5)))
            if rng.random() < 0.3 and len(lab) > 2:
                lab = lab[0] + "-" + lab[2:]
            labels.append(lab)
        tld = "".join(rng.choice(string.ascii_letters) for _ in range(rng.randint(2, 4)))
        s = f"{local}@{'.'.join(labels)}.{tld}"
        for cand in (s, _mutate(rng, s, mut_pool)):
            got, want = email.is_valid_email(cand), email.reference_email(cand)
            assert got == want, repr(cand)
            accepted += want
            rejected += not want
    assert accepted > 1000 and rejected > 1000  # the sample really exercised both outcomes


def test_random_password():
    rng = random.Random(3)
    pools = {"U": string.ascii_uppercase, "L": string.ascii_lowercase, "D": string.digits,
             "S": string.punctuation, "X": " é\t"}
    accepted = rejected = 0
    for _ in range(30000):
        n = rng.randint(4, 20)
        weights = rng.choice([(1, 1, 1, 1, 0), (3, 3, 2, 1, 0), (1, 1, 1, 1, 1), (4, 4, 4, 0, 0)])
        kinds = rng.choices("ULDSX", weights=weights, k=n)
        s = "".join(rng.choice(pools[k]) for k in kinds)
        got, want = password.is_valid_password(s), password.reference_password(s)
        assert got == want, repr(s)
        accepted += want
        rejected += not want
    assert accepted > 1000 and rejected > 1000


# -------------------------------------------------------- structure & design
def test_pin_dfa_shape():
    assert len(pin.PIN_DFA.states) == 6          # q0..q4 + dead
    assert pin.PIN_DFA.accepting == {"q4"}
    assert len(pin.PIN_DFA.minimize().states) == 6  # already minimal
    assert pin.PIN6_DFA.accepts("123456") and not pin.PIN6_DFA.accepts("1234")


def test_shortest_accepted_strings():
    assert pin.PIN_DFA.shortest_accepted() == ["D"] * 4
    assert email.EMAIL_DFA.shortest_accepted() is not None
    assert len(email.EMAIL_DFA.shortest_accepted()) == 6        # e.g. a@b.cc
    assert len(password.PASSWORD_DFA.shortest_accepted()) == 8


def test_retry_limiter():
    d = pin.RETRY_DFA
    assert d.accepts_symbols(["ok"])
    assert d.accepts_symbols(["bad", "ok"])
    assert d.accepts_symbols(["bad", "bad", "ok"])
    assert not d.accepts_symbols(["bad", "bad", "bad", "ok"])     # card locked after 3 failures
    assert not d.accepts_symbols(["bad", "bad"])
    assert not d.accepts_symbols([])


def test_email_nfa_dfa_and_minimal_agree():
    symbols = sorted(email.ALPHABET)
    for n in range(7):
        for word in itertools.product(symbols, repeat=n):
            a = email.EMAIL_NFA.accepts_symbols(word)
            assert a == email.EMAIL_DFA_RAW.accepts_symbols(word) == email.EMAIL_DFA.accepts_symbols(word)
    assert email.EMAIL_DFA_RAW.counterexample(email.EMAIL_DFA) is None


def test_email_state_counts():
    assert len(email.EMAIL_NFA.states) == 9
    assert len(email.EMAIL_DFA_RAW.states) == 10
    assert len(email.EMAIL_DFA.states) == 9


def test_password_two_designs_are_equivalent():
    a, b = password.PASSWORD_DFA_A, password.PASSWORD_DFA_B
    assert a.counterexample(b) is None
    assert a.counterexample(password.PASSWORD_DFA) is None
    assert len(a.states) == 225
    assert len(b.states) == 479
    assert len(password.PASSWORD_DFA.states) == 197
    assert len(b.minimize().states) == 197          # both designs minimise to the same machine


def test_password_boundaries():
    base = "Aa1$"
    assert not password.is_valid_password(base + "x" * 3)    # 7 chars
    assert password.is_valid_password(base + "x" * 4)        # 8 chars
    assert password.is_valid_password(base + "x" * 12)       # 16 chars
    assert not password.is_valid_password(base + "x" * 13)   # 17 chars


def test_readme_lists_every_case():
    """The design note must show every test string that the suite runs."""
    readme = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")
    for app, groups in CASES.items():
        for s in groups["accept"] + [r[0] for r in groups["reject"]]:
            if s and "\n" not in s:
                assert s in readme, f"{app}: {s!r} is missing from README.md"


def test_doomed_state_count_explains_225_to_197():
    """28 'doomed' (n, seen) pairs behave like dead: 14 + 10 + 4 at n = 16, 15, 14."""
    doomed = 0
    for n in range(1, 17):
        for mask in range(1, 16):
            if bin(mask).count("1") <= n and (4 - bin(mask).count("1")) > (16 - n):
                doomed += 1
    assert doomed == 28 == len(password.PASSWORD_DFA_A.states) - len(password.PASSWORD_DFA.states)


def test_mini_policy():
    m = password.MINI_DFA
    assert len(m.states) == 11
    assert m.accepts("ab1") and m.accepts("a1b2") and not m.accepts("abc") and not m.accepts("a1bcd")
