"""Application 2 - e-mail *format* validation (a deliberately simplified subset of RFC 5322).

Alphabet classes  Σ = {L, N, P, H, ., @, X}
    L = ASCII letter   N = ASCII digit   P = '_' or '+'   H = '-'   X = anything else

Language (as a regular expression over characters):

    word   = [A-Za-z0-9_+-]+
    local  = word ( . word )*                       no leading / trailing / double dot
    label  = alnum ( [alnum-]* alnum )?             may not start or end with '-'
    domain = ( label . )+ [A-Za-z]{2,}              at least one dot, TLD = 2+ letters
    email  = local @ domain

The natural machine is an NFA: after a '.' in the domain, a letter may be the start of
another ordinary label *or* the first letter of the final TLD, and the machine only learns
which at the end.  We write that NFA directly, then derive a DFA by subset construction
and minimise it.
"""
import re
import string

from automata import NFA

ALPHABET = {"L", "N", "P", "H", ".", "@", "X"}
LEGEND = {
    "L": "ASCII letter A-Z a-z",
    "N": "ASCII digit 0-9",
    "P": "underscore or plus ( _ + )",
    "H": "hyphen ( - )",
    ".": "dot",
    "@": "at sign",
    "X": "any other character",
}

_LETTERS = set(string.ascii_letters)


def classify(ch: str) -> str:
    if ch in _LETTERS:
        return "L"
    if ch in string.digits:
        return "N"
    if ch in "_+":
        return "P"
    if ch == "-":
        return "H"
    if ch == ".":
        return "."
    if ch == "@":
        return "@"
    return "X"


def build_email_nfa() -> NFA:
    d = {}

    def add(src, syms, dst):
        for a in syms:
            d.setdefault((src, a), set()).update(dst if isinstance(dst, set) else {dst})

    local_chars = "LNPH"
    add("s0", local_chars, "loc")            # first char of the local part
    add("loc", local_chars, "loc")           # more local characters
    add("loc", ".", "ldot")                  # a dot inside the local part ...
    add("ldot", local_chars, "loc")          # ... must be followed by a character
    add("loc", "@", "at")                    # local part ends (so it cannot end in '.')
    add("at", "LN", "lab")                   # domain label must start alphanumeric
    add("lab", "LN", "lab")
    add("lab", "H", "hyp")                   # hyphen inside a label ...
    add("hyp", "H", "hyp")
    add("hyp", "LN", "lab")                  # ... must be followed by alphanumeric (so no trailing '-')
    add("lab", ".", "ddot")                  # label done, dot seen
    add("ddot", "L", {"lab", "tld1"})        # NONDETERMINISM: ordinary label OR first TLD letter
    add("ddot", "N", "lab")                  # digits cannot start a TLD
    add("tld1", "L", "tld2")
    add("tld2", "L", "tld2")                 # TLD = 2+ letters, accepting
    states = {"s0", "loc", "ldot", "at", "lab", "hyp", "ddot", "tld1", "tld2"}
    return NFA(states, set(ALPHABET), d, "s0", {"tld2"}, name="E-mail NFA", classify=classify)


EMAIL_NFA = build_email_nfa()
EMAIL_DFA_RAW = EMAIL_NFA.to_dfa(name="E-mail DFA (subset construction)")
EMAIL_DFA = EMAIL_DFA_RAW.minimize(name="E-mail DFA (minimal)")

_REGEX = re.compile(
    r"[A-Za-z0-9_+-]+(\.[A-Za-z0-9_+-]+)*"
    r"@"
    r"([A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}"
)


def is_valid_email(text: str) -> bool:
    return EMAIL_DFA.accepts(text)


def reference_email(text: str) -> bool:
    """Independent oracle (Python regex) used only by the tests."""
    return _REGEX.fullmatch(text) is not None
