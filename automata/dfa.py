"""A small, dependency-free DFA toolkit used by the Task 2 validators.

Design notes
------------
* Every DFA here is *total*: each (state, symbol) pair has a transition.  A
  non-accepting trap state called "dead" absorbs every input that can no
  longer be completed into a valid string.  Diagrams hide it by convention.
* The alphabet is a set of *symbol classes* (for example "D" = any ASCII
  digit).  Real characters are mapped to a class by ``classify``.  Keeping the
  formal alphabet small is what makes the diagrams readable.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Dict, Hashable, Iterable, List, Optional, Set, Tuple

State = Hashable
Symbol = str
DEAD = "dead"


def _esc(text: object) -> str:
    return str(text).replace("\\", "\\\\").replace('"', '\\"')


def build_dot(
    nodes: List[State],
    start: State,
    accepting: Set[State],
    edges: Dict[Tuple[State, State], List[str]],
    title: Optional[str] = None,
    legend: Optional[Dict[str, str]] = None,
    note: Optional[str] = None,
) -> str:
    """Render a Graphviz DOT description (shared by DFA and NFA)."""
    ids = {s: f"n{i}" for i, s in enumerate(nodes)}
    lines = [
        "digraph G {",
        "  rankdir=LR;",
        "  bgcolor=white;",
        '  node [shape=circle, fontname="Helvetica", fontsize=12];',
        '  edge [fontname="Helvetica", fontsize=11];',
    ]
    label_lines: List[str] = []
    if title:
        label_lines.append(_esc(title))
    if legend:
        label_lines.append("Alphabet classes:")
        label_lines.extend(f"  {_esc(k)} = {_esc(v)}" for k, v in legend.items())
    if note:
        label_lines.append(_esc(note))
    if label_lines:
        label = "\\l".join(label_lines) + "\\l"
        lines.append(f'  labelloc=b; labeljust=l; fontname="Helvetica"; fontsize=11; label="{label}";')
    lines.append("  __start [shape=point, width=0.15, label=\"\"];")
    for s in nodes:
        shape = "doublecircle" if s in accepting else "circle"
        lines.append(f'  {ids[s]} [label="{_esc(s)}", shape={shape}];')
    lines.append(f"  __start -> {ids[start]};")
    for (src, dst), labels in edges.items():
        lines.append(f'  {ids[src]} -> {ids[dst]} [label="{_esc(", ".join(labels))}"];')
    lines.append("}")
    return "\n".join(lines) + "\n"


@dataclass
class DFA:
    states: Set[State]
    alphabet: Set[Symbol]
    delta: Dict[Tuple[State, Symbol], State]
    start: State
    accepting: Set[State]
    name: str = "DFA"
    classify: Optional[Callable[[str], Symbol]] = None

    # ------------------------------------------------------------------ run
    def symbols_of(self, text: str) -> List[Symbol]:
        """Map raw characters to alphabet classes."""
        if self.classify is None:
            return list(text)
        return [self.classify(ch) for ch in text]

    def accepts_symbols(self, symbols: Iterable[Symbol]) -> bool:
        state = self.start
        for a in symbols:
            if a not in self.alphabet:
                return False
            state = self.delta[(state, a)]
        return state in self.accepting

    def accepts(self, text: str) -> bool:
        return self.accepts_symbols(self.symbols_of(text))

    def trace(self, symbols: Iterable[Symbol]) -> Tuple[bool, List[State]]:
        """Return (accepted, visited states including the start state)."""
        state = self.start
        path = [state]
        for a in symbols:
            state = self.delta[(state, a)]
            path.append(state)
        return state in self.accepting, path

    # ------------------------------------------------------------ structure
    def _bfs_order(self) -> List[State]:
        sigma = sorted(self.alphabet)
        order = [self.start]
        seen = {self.start}
        dq = deque([self.start])
        while dq:
            s = dq.popleft()
            for a in sigma:
                t = self.delta[(s, a)]
                if t not in seen:
                    seen.add(t)
                    order.append(t)
                    dq.append(t)
        return order

    def reachable(self) -> Set[State]:
        return set(self._bfs_order())

    def trap_states(self) -> Set[State]:
        """Reachable non-accepting states whose every move is a self-loop."""
        return {
            s
            for s in self.reachable()
            if s not in self.accepting and all(self.delta[(s, a)] == s for a in self.alphabet)
        }

    # ------------------------------------------------------------ algorithms
    def minimize(self, name: Optional[str] = None) -> "DFA":
        """Moore partition refinement; states are renamed q0, q1, ... (and 'dead')."""
        live = self.reachable()
        sigma = sorted(self.alphabet)
        part = {s: int(s in self.accepting) for s in live}
        n_blocks = len(set(part.values()))
        ordered = sorted(live, key=repr)
        while True:
            sig = {s: (part[s], tuple(part[self.delta[(s, a)]] for a in sigma)) for s in live}
            ids: Dict[Tuple, int] = {}
            new = {s: ids.setdefault(sig[s], len(ids)) for s in ordered}
            part = new
            if len(ids) == n_blocks:
                break
            n_blocks = len(ids)

        rep: Dict[int, State] = {}
        for s in ordered:
            rep.setdefault(part[s], s)
        start_b = part[self.start]

        def block_next(b: int, a: Symbol) -> int:
            return part[self.delta[(rep[b], a)]]

        order = [start_b]
        seen = {start_b}
        dq = deque([start_b])
        while dq:
            b = dq.popleft()
            for a in sigma:
                nb = block_next(b, a)
                if nb not in seen:
                    seen.add(nb)
                    order.append(nb)
                    dq.append(nb)

        def is_trap(b: int) -> bool:
            return rep[b] not in self.accepting and all(block_next(b, a) == b for a in sigma)

        names: Dict[int, str] = {}
        counter = 0
        for b in order:
            if is_trap(b) and b != start_b:
                names[b] = DEAD
            else:
                names[b] = f"q{counter}"
                counter += 1
        delta = {(names[b], a): names[block_next(b, a)] for b in order for a in sigma}
        accepting = {names[b] for b in order if rep[b] in self.accepting}
        return DFA(
            states=set(names.values()),
            alphabet=set(self.alphabet),
            delta=delta,
            start=names[start_b],
            accepting=accepting,
            name=name or f"{self.name} (minimal)",
            classify=self.classify,
        )

    def intersect(self, other: "DFA", name: Optional[str] = None) -> "DFA":
        """Product construction for L(self) ∩ L(other) (reachable pairs only)."""
        if self.alphabet != other.alphabet:
            raise ValueError("alphabets differ")
        sigma = sorted(self.alphabet)
        start = (self.start, other.start)
        states = {start}
        delta: Dict[Tuple[State, Symbol], State] = {}
        dq = deque([start])
        while dq:
            p = dq.popleft()
            for a in sigma:
                t = (self.delta[(p[0], a)], other.delta[(p[1], a)])
                delta[(p, a)] = t
                if t not in states:
                    states.add(t)
                    dq.append(t)
        accepting = {s for s in states if s[0] in self.accepting and s[1] in other.accepting}
        return DFA(states, set(self.alphabet), delta, start, accepting,
                   name or f"({self.name} ∩ {other.name})", self.classify)

    def counterexample(self, other: "DFA") -> Optional[List[Symbol]]:
        """Shortest symbol string accepted by exactly one DFA, or None if equivalent."""
        if self.alphabet != other.alphabet:
            raise ValueError("alphabets differ")
        sigma = sorted(self.alphabet)
        start = (self.start, other.start)
        seen = {start}
        dq = deque([(start, [])])
        while dq:
            (p, q), word = dq.popleft()
            if (p in self.accepting) != (q in other.accepting):
                return word
            for a in sigma:
                nxt = (self.delta[(p, a)], other.delta[(q, a)])
                if nxt not in seen:
                    seen.add(nxt)
                    dq.append((nxt, word + [a]))
        return None

    def shortest_accepted(self) -> Optional[List[Symbol]]:
        sigma = sorted(self.alphabet)
        seen = {self.start}
        dq = deque([(self.start, [])])
        while dq:
            s, word = dq.popleft()
            if s in self.accepting:
                return word
            for a in sigma:
                t = self.delta[(s, a)]
                if t not in seen:
                    seen.add(t)
                    dq.append((t, word + [a]))
        return None

    # --------------------------------------------------------------- export
    def to_dot(self, title: Optional[str] = None, legend: Optional[Dict[str, str]] = None,
               hide_dead: bool = True) -> str:
        traps = self.trap_states() - {self.start} if hide_dead else set()
        nodes = [s for s in self._bfs_order() if s not in traps]
        edges: Dict[Tuple[State, State], List[str]] = {}
        for s in nodes:
            for a in sorted(self.alphabet):
                t = self.delta[(s, a)]
                if t in traps:
                    continue
                edges.setdefault((s, t), []).append(a)
        note = "Moves into the dead (trap) state are omitted." if traps else None
        return build_dot(nodes, self.start, self.accepting, edges, title, legend, note)

    def transition_table_md(self) -> str:
        sigma = sorted(self.alphabet)
        header = "| State | " + " | ".join(f"`{a}`" for a in sigma) + " |"
        rule = "|---|" + "---|" * len(sigma)
        rows = [header, rule]
        for s in self._bfs_order():
            mark = ("→" if s == self.start else "") + ("*" if s in self.accepting else "")
            label = f"{mark} {s}".strip()
            rows.append(f"| {label} | " + " | ".join(str(self.delta[(s, a)]) for a in sigma) + " |")
        return "\n".join(rows) + "\n"
