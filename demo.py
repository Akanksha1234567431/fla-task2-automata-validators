#!/usr/bin/env python3
"""Demonstration of the three DFA validators.

    python demo.py                 run every case in tests/cases.json and show the state trace
    python demo.py -i              interactive mode (type strings, see the trace)
    python demo.py --pin 4821      check one value
    python demo.py --email a@b.co
    python demo.py --password 'Passw0rd!'
    python demo.py --retry bad bad ok     ATM retry limiter (events, not characters)
"""
import argparse
import json
from pathlib import Path

from automata import DEAD
from validators import email, password, pin

CASES = Path(__file__).parent / "tests" / "cases.json"
APPS = {
    "pin": ("ATM PIN", pin.PIN_DFA),
    "email": ("E-mail", email.EMAIL_DFA),
    "password": ("Password", password.PASSWORD_DFA),
}


def explain(dfa, text):
    """Print the symbol classes, the state path and *why* the string was accepted/rejected."""
    symbols = dfa.symbols_of(text)
    accepted, path = dfa.trace(symbols)
    print(f"  input   : {text!r}  (length {len(text)})")
    print(f"  classes : {' '.join(symbols) if symbols else '(empty string)'}")
    print(f"  path    : {' -> '.join(map(str, path))}")
    if accepted:
        verdict = "ACCEPT  (ended in an accepting state)"
    elif DEAD in path:
        i = path.index(DEAD)
        verdict = f"REJECT  (entered the dead state at character {i}: {text[i - 1]!r} can never lead to a valid string)"
    else:
        verdict = f"REJECT  (input ended in non-accepting state {path[-1]}: the string is a valid prefix but incomplete)"
    print(f"  verdict : {verdict}")


def run_all():
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    for key, (title, dfa) in APPS.items():
        print("=" * 78)
        print(f"{title}: {dfa.name}  [{len(dfa.states)} states]")
        print("=" * 78)
        print(f"\n--- accepted examples ({len(cases[key]['accept'])}) ---")
        for s in cases[key]["accept"]:
            explain(dfa, s)
            print()
        print(f"--- rejected examples ({len(cases[key]['reject'])}) ---")
        for s, why in cases[key]["reject"]:
            print(f"  (why it is invalid: {why})")
            explain(dfa, s)
            print()
    print("=" * 78)
    print("ATM retry limiter (events from the bank back-end)")
    print("=" * 78)
    for events in (["ok"], ["bad", "ok"], ["bad", "bad", "ok"], ["bad", "bad", "bad", "ok"]):
        accepted, path = pin.RETRY_DFA.trace(events)
        print(f"  {' '.join(events):<16} {' -> '.join(path)}  => {'AUTHENTICATED' if accepted else 'NOT authenticated'}")


def interactive():
    print("Type a validator (pin / email / password), then strings to test. Empty line goes back; Ctrl-D quits.")
    try:
        while True:
            key = input("\nvalidator> ").strip().lower()
            if key not in APPS:
                print("choose pin, email or password")
                continue
            dfa = APPS[key][1]
            while True:
                text = input(f"{key}> ")
                if text == "":
                    break
                explain(dfa, text)
    except (EOFError, KeyboardInterrupt):
        print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--interactive", action="store_true")
    ap.add_argument("--pin")
    ap.add_argument("--email")
    ap.add_argument("--password")
    ap.add_argument("--retry", nargs="+", choices=["ok", "bad"])
    args = ap.parse_args()
    if args.interactive:
        interactive()
    elif args.pin is not None or args.email is not None or args.password is not None or args.retry:
        if args.pin is not None:
            explain(pin.PIN_DFA, args.pin)
        if args.email is not None:
            explain(email.EMAIL_DFA, args.email)
        if args.password is not None:
            explain(password.PASSWORD_DFA, args.password)
        if args.retry:
            accepted, path = pin.RETRY_DFA.trace(args.retry)
            print(" -> ".join(path), "=>", "AUTHENTICATED" if accepted else "NOT authenticated")
    else:
        run_all()


if __name__ == "__main__":
    main()
