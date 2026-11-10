"""NFA (without ε-moves) and the subset construction."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from .dfa import DEAD, DFA, build_dot


@dataclass
class NFA:
    states: Set[str]
    alphabet: Set[str]
    delta: Dict[Tuple[str, str], Set[str]]
    start: str
    accepting: Set[str]
    name: str = "NFA"
    classify: Optional[Callable[[str], str]] = None

    def symbols_of(self, text: str) -> List[str]:
        if self.classify is None:
            return list(text)
        return [self.classify(ch) for ch in text]

    def accepts_symbols(self, symbols: Iterable[str]) -> bool:
        current = {self.start}
        for a in symbols:
            nxt: Set[str] = set()
            for s in current:
                nxt |= self.delta.get((s, a), set())
            current = nxt
            if not current:
                return False
        return bool(current & self.accepting)

    def accepts(self, text: str) -> bool:
        return self.accepts_symbols(self.symbols_of(text))

    # ----------------------------------------------------- subset construction
    @staticmethod
    def _label(subset: frozenset) -> str:
        return DEAD if not subset else "{" + ",".join(sorted(subset)) + "}"

    def to_dfa(self, name: Optional[str] = None) -> DFA:
        """Subset construction. DFA states are labelled by the NFA-state set they stand for."""
        sigma = sorted(self.alphabet)
        start = frozenset([self.start])
        seen = {start}
        dq = deque([start])
        delta: Dict[Tuple[str, str], str] = {}
        while dq:
            cur = dq.popleft()
            for a in sigma:
                nxt = frozenset(t for s in cur for t in self.delta.get((s, a), set()))
                delta[(self._label(cur), a)] = self._label(nxt)
                if nxt not in seen:
                    seen.add(nxt)
                    dq.append(nxt)
        if frozenset() not in seen:  # keep the DFA total even if the trap was never reached
            seen.add(frozenset())
            for a in sigma:
                delta[(DEAD, a)] = DEAD
        states = {self._label(s) for s in seen}
        accepting = {self._label(s) for s in seen if s & self.accepting}
        return DFA(states, set(self.alphabet), delta, self._label(start), accepting,
                   name or f"{self.name} → DFA (subset construction)", self.classify)

    # --------------------------------------------------------------- export
    def _bfs_order(self) -> List[str]:
        sigma = sorted(self.alphabet)
        order = [self.start]
        seen = {self.start}
        dq = deque([self.start])
        while dq:
            s = dq.popleft()
            for a in sigma:
                for t in sorted(self.delta.get((s, a), set())):
                    if t not in seen:
                        seen.add(t)
                        order.append(t)
                        dq.append(t)
        return order

    def to_dot(self, title: Optional[str] = None, legend: Optional[Dict[str, str]] = None) -> str:
        nodes = self._bfs_order()
        edges: Dict[Tuple[str, str], List[str]] = {}
        for s in nodes:
            for a in sorted(self.alphabet):
                for t in sorted(self.delta.get((s, a), set())):
                    edges.setdefault((s, t), []).append(a)
        note = "Missing moves mean the run dies (no transition)."
        return build_dot(nodes, self.start, self.accepting, edges, title, legend, note)

    def transition_table_md(self) -> str:
        sigma = sorted(self.alphabet)
        rows = ["| State | " + " | ".join(f"`{a}`" for a in sigma) + " |", "|---|" + "---|" * len(sigma)]
        for s in self._bfs_order():
            mark = ("→" if s == self.start else "") + ("*" if s in self.accepting else "")
            cells = []
            for a in sigma:
                t = self.delta.get((s, a), set())
                cells.append("{" + ",".join(sorted(t)) + "}" if t else "–")
            rows.append(f"| {(mark + ' ' + s).strip()} | " + " | ".join(cells) + " |")
        return "\n".join(rows) + "\n"
