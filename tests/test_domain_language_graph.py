"""Tests for Domain Language Graph construction and structural validation."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from dds.domain_language import DomainLanguage
from dds.domain_language_graph import DomainLanguageGraph, EdgeLabel


def _make_lang(name: str, imports: list[str] | None = None) -> DomainLanguage:
    lang = DomainLanguage(name=name)
    lang.add_entity(f"{name}_Entity")
    for imp in (imports or []):
        lang.add_import(imp)
    return lang


class TestGraphConstruction:
    def test_empty_graph(self):
        g = DomainLanguageGraph()
        assert len(g.languages) == 0
        assert len(g.edges) == 0

    def test_add_language(self):
        g = DomainLanguageGraph()
        lang = _make_lang("Core")
        g.add_language(lang)
        assert "Core" in g.languages

    def test_duplicate_language_raises(self):
        g = DomainLanguageGraph()
        g.add_language(_make_lang("Core"))
        with pytest.raises(ValueError, match="already exists"):
            g.add_language(_make_lang("Core"))

    def test_add_edge(self):
        g = DomainLanguageGraph()
        g.add_language(_make_lang("A"))
        g.add_language(_make_lang("B"))
        edge = g.add_edge("A", "B", EdgeLabel.IMPORTS)
        assert edge.source == "A"
        assert edge.target == "B"
        assert edge.label == EdgeLabel.IMPORTS

    def test_edge_nonexistent_source_raises(self):
        g = DomainLanguageGraph()
        g.add_language(_make_lang("B"))
        with pytest.raises(ValueError, match="Source"):
            g.add_edge("Missing", "B", EdgeLabel.IMPORTS)


class TestComposedVocab:
    def test_union_of_vocabs(self):
        g = DomainLanguageGraph()
        a = DomainLanguage(name="A")
        a.add_entity("X")
        b = DomainLanguage(name="B")
        b.add_entity("Y")
        g.add_language(a)
        g.add_language(b)
        vocab = g.composed_vocab()
        names = {item.name for item in vocab}
        assert "X" in names
        assert "Y" in names


class TestCycleDetection:
    def test_no_cycle(self):
        g = DomainLanguageGraph()
        g.add_language(_make_lang("A"))
        g.add_language(_make_lang("B"))
        g.add_edge("A", "B", EdgeLabel.IMPORTS)
        assert g.detect_import_cycles() == []

    def test_direct_cycle(self):
        g = DomainLanguageGraph()
        g.add_language(_make_lang("A"))
        g.add_language(_make_lang("B"))
        g.add_edge("A", "B", EdgeLabel.IMPORTS)
        g.add_edge("B", "A", EdgeLabel.IMPORTS)
        cycles = g.detect_import_cycles()
        assert len(cycles) > 0

    def test_transitive_cycle(self):
        g = DomainLanguageGraph()
        g.add_language(_make_lang("A"))
        g.add_language(_make_lang("B"))
        g.add_language(_make_lang("C"))
        g.add_edge("A", "B", EdgeLabel.IMPORTS)
        g.add_edge("B", "C", EdgeLabel.IMPORTS)
        g.add_edge("C", "A", EdgeLabel.IMPORTS)
        cycles = g.detect_import_cycles()
        assert len(cycles) > 0

    def test_single_edge_type(self):
        """All edges are imports — verify default label."""
        g = DomainLanguageGraph()
        g.add_language(_make_lang("A"))
        g.add_language(_make_lang("B"))
        edge = g.add_edge("A", "B")
        assert edge.label == EdgeLabel.IMPORTS


class TestCrossReferences:
    def test_valid_cross_reference(self):
        g = DomainLanguageGraph()
        g.add_language(_make_lang("A", imports=["B"]))
        g.add_language(_make_lang("B"))
        g.add_edge("A", "B", EdgeLabel.IMPORTS)
        errors = g.check_cross_references()
        assert len(errors) == 0

    def test_missing_edge_for_import(self):
        g = DomainLanguageGraph()
        g.add_language(_make_lang("A", imports=["B"]))
        g.add_language(_make_lang("B"))
        # No edge added
        errors = g.check_cross_references()
        assert len(errors) > 0

    def test_import_nonexistent_language(self):
        g = DomainLanguageGraph()
        g.add_language(_make_lang("A", imports=["Missing"]))
        errors = g.check_cross_references()
        assert any("not in the graph" in e for e in errors)


class TestTopologicalOrder:
    def test_linear_chain(self):
        """A→B→C (A imports B, B imports C).
        Kahn's: in-degree(A)=0, in-degree(B)=1, in-degree(C)=1.
        Order: A, B, C (sources first)."""
        g = DomainLanguageGraph()
        g.add_language(_make_lang("A"))
        g.add_language(_make_lang("B"))
        g.add_language(_make_lang("C"))
        g.add_edge("A", "B", EdgeLabel.IMPORTS)
        g.add_edge("B", "C", EdgeLabel.IMPORTS)
        order = g.topological_order()
        assert order is not None
        assert set(order) == {"A", "B", "C"}
        assert order.index("A") < order.index("B") < order.index("C")

    def test_cycle_returns_none(self):
        g = DomainLanguageGraph()
        g.add_language(_make_lang("A"))
        g.add_language(_make_lang("B"))
        g.add_edge("A", "B", EdgeLabel.IMPORTS)
        g.add_edge("B", "A", EdgeLabel.IMPORTS)
        assert g.topological_order() is None


class TestStructuralValidation:
    def test_valid_graph(self):
        g = DomainLanguageGraph()
        g.add_language(_make_lang("A", imports=["B"]))
        g.add_language(_make_lang("B"))
        g.add_edge("A", "B", EdgeLabel.IMPORTS)
        errors = g.structural_validation()
        assert len(errors) == 0

    def test_collects_all_errors(self):
        g = DomainLanguageGraph()
        g.add_language(_make_lang("A", imports=["Missing"]))
        g.add_language(_make_lang("B", imports=["A"]))
        g.add_edge("A", "B", EdgeLabel.IMPORTS)
        g.add_edge("B", "A", EdgeLabel.IMPORTS)
        errors = g.structural_validation()
        # Should find: cycle + missing import reference
        assert len(errors) >= 2
