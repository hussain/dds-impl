"""Domain Language Graph — semantic composition boundary.

Paper reference: Section 4.1

A Domain Language Graph is the dependency and composition graph formed
by multiple Domain Languages.

Formally: DomLG = (V, E) where:
  V = finite set of nodes (Domain Languages)
  E ⊆ V × V = directed edges (import dependencies)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

from .domain_language import DomainLanguage
from .types import Relation


class EdgeLabel(Enum):
    """Edge label in the Domain Language Graph.

    Paper reference: Section 4.1 — DomLG has a single edge type: imports.
    """
    IMPORTS = "imports"


@dataclass(frozen=True)
class DomLGEdge:
    """A directed import edge in the Domain Language Graph."""
    source: str  # name of source DomainLanguage
    target: str  # name of target DomainLanguage
    label: EdgeLabel = EdgeLabel.IMPORTS


@dataclass
class DomainLanguageGraph:
    """DomLG = (V, E) — the semantic composition boundary.

    Paper reference: Section 4.1 — "A Domain Language Graph is a directed
    import graph"
    """

    # V — nodes (Domain Languages indexed by name)
    languages: dict[str, DomainLanguage] = field(default_factory=dict)

    # E — directed import edges
    edges: list[DomLGEdge] = field(default_factory=list)

    # -----------------------------------------------------------------------
    # Builder API
    # -----------------------------------------------------------------------

    def add_language(self, lang: DomainLanguage) -> None:
        """Add a Domain Language as a node in the graph."""
        if lang.name in self.languages:
            raise ValueError(f"Domain Language '{lang.name}' already exists in graph")
        self.languages[lang.name] = lang

    def add_edge(self, source: str, target: str, label: EdgeLabel = EdgeLabel.IMPORTS) -> DomLGEdge:
        """Add an import edge between two Domain Languages.

        Paper reference: Section 4.1 — each edge (u, v) signifies that
        DomL u imports DomL v.
        """
        if source not in self.languages:
            raise ValueError(f"Source '{source}' not in graph")
        if target not in self.languages:
            raise ValueError(f"Target '{target}' not in graph")
        edge = DomLGEdge(source=source, target=target, label=label)
        self.edges.append(edge)
        return edge

    # -----------------------------------------------------------------------
    # Vocabulary composition
    # -----------------------------------------------------------------------

    def composed_vocab(self) -> set:
        """Return Vocab(DomLG) = ⋃{Vocab(DomL) | DomL ∈ V}.

        Paper reference: Section 3.1
        """
        vocab: set = set()
        for lang in self.languages.values():
            vocab.update(lang.vocab())
        return vocab

    def composed_relations(self) -> set[Relation]:
        """Return all declared relations across all Domain Languages."""
        rels: set[Relation] = set()
        for lang in self.languages.values():
            rels.update(lang.relations)
        return rels

    # -----------------------------------------------------------------------
    # Structural validation
    # -----------------------------------------------------------------------

    def detect_import_cycles(self) -> list[list[str]]:
        """Detect cycles in the import graph.

        Paper reference: Section 4.1 — "The import graph must be acyclic.
        There is no directed path from any node back to itself."

        Returns list of cycles found (empty if acyclic).
        """
        # Build adjacency list from all edges (all edges are imports)
        adj: dict[str, list[str]] = defaultdict(list)
        for edge in self.edges:
            adj[edge.source].append(edge.target)

        cycles: list[list[str]] = []
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {name: WHITE for name in self.languages}
        path: list[str] = []

        def dfs(node: str) -> None:
            color[node] = GRAY
            path.append(node)
            for neighbor in adj.get(node, []):
                if color.get(neighbor) == GRAY:
                    # Found cycle: extract it from path
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                elif color.get(neighbor) == WHITE:
                    dfs(neighbor)
            path.pop()
            color[node] = BLACK

        for node in self.languages:
            if color[node] == WHITE:
                dfs(node)

        return cycles

    def check_cross_references(self) -> list[str]:
        """Check that cross-language references resolve through declared edges.

        Paper reference: Section 4.1 — "Every cross-language reference in a
        Domain Language must resolve through a declared import edge."
        """
        errors: list[str] = []

        # Build reachability map: for each language, what other languages
        # can it reference through declared edges?
        reachable: dict[str, set[str]] = {name: set() for name in self.languages}
        for edge in self.edges:
            reachable[edge.source].add(edge.target)

        # Check each language's imports
        for lang in self.languages.values():
            for imp in lang.imports:
                if imp.target_name not in self.languages:
                    errors.append(
                        f"'{lang.name}' imports '{imp.target_name}' "
                        f"which is not in the graph"
                    )
                elif imp.target_name not in reachable[lang.name]:
                    errors.append(
                        f"'{lang.name}' imports '{imp.target_name}' "
                        f"but no edge exists in the graph"
                    )

        return errors

    def topological_order(self) -> list[str] | None:
        """Return a topological ordering of languages by import edges.

        Returns None if a cycle exists.
        """
        if self.detect_import_cycles():
            return None

        adj: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {name: 0 for name in self.languages}
        for edge in self.edges:
            adj[edge.source].append(edge.target)
            in_degree.setdefault(edge.target, 0)

        # Kahn's algorithm
        queue = [n for n in self.languages if in_degree.get(n, 0) == 0]
        order: list[str] = []
        while queue:
            queue.sort()  # deterministic ordering
            node = queue.pop(0)
            order.append(node)
            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.languages):
            return None
        return order

    def structural_validation(self) -> list[str]:
        """Run all structural validation checks.

        Returns list of errors (empty if valid).
        """
        errors: list[str] = []

        cycles = self.detect_import_cycles()
        for cycle in cycles:
            errors.append(f"Import cycle detected: {' → '.join(cycle)}")

        errors.extend(self.check_cross_references())

        return errors

    def __repr__(self) -> str:
        return (
            f"DomainLanguageGraph("
            f"{len(self.languages)} languages, "
            f"{len(self.edges)} edges)"
        )
