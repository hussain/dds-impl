"""Tests for the DDS-valid admissibility predicate and self-validation.

Tests each of the five conditions (Section 5.1) in both pass and fail cases.
Also tests the layered API: check_admissibility (Layer 2) and
evaluate_rules (Layer 3).
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from dds.domain_language import DomainLanguage
from dds.domain_language_graph import DomainLanguageGraph, EdgeLabel
from dds.normative import NormativeOp
from dds.types import UNKNOWN, EntityType, Optionality
from dds.validation import (
    ConditionStatus,
    SemanticWorld,
    self_validate,
    validate,
    check_admissibility,
    evaluate_rules,
)


def _simple_domain() -> DomainLanguageGraph:
    """Build a minimal domain for testing."""
    lang = DomainLanguage(name="TestDomain")
    person = lang.add_entity("Person")
    name_attr = lang.add_attribute(person, "name", value_type=str)
    verified = lang.add_attribute(person, "verified", value_type=bool)
    lang.must(verified, description="Person must be verified")

    item = lang.add_entity("Item")
    lang.add_attribute(item, "label", value_type=str)

    owns = lang.add_relation("owns", source=person, target=item)

    graph = DomainLanguageGraph()
    graph.add_language(lang)
    return graph


# ---------------------------------------------------------------------------
# Self-Validation Tests
# ---------------------------------------------------------------------------

class TestSelfValidation:
    def test_valid_single_language(self):
        graph = _simple_domain()
        result = self_validate(graph)
        assert result.is_valid

    def test_contradiction_detected(self):
        lang = DomainLanguage(name="Broken")
        e = lang.add_entity("Thing")
        a = lang.add_attribute(e, "x", value_type=bool)
        lang.must(a)
        lang.must_not(a)

        graph = DomainLanguageGraph()
        graph.add_language(lang)
        result = self_validate(graph)
        assert not result.is_valid
        assert any("Conflict" in e for e in result.errors)

    def test_cycle_detected(self):
        a = DomainLanguage(name="A")
        a.add_entity("X")
        a.add_import("B")
        b = DomainLanguage(name="B")
        b.add_entity("Y")
        b.add_import("A")

        graph = DomainLanguageGraph()
        graph.add_language(a)
        graph.add_language(b)
        graph.add_edge("A", "B", EdgeLabel.IMPORTS)
        graph.add_edge("B", "A", EdgeLabel.IMPORTS)

        result = self_validate(graph)
        assert not result.is_valid
        assert any("cycle" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# Condition 1: Vocabulary Closure
# ---------------------------------------------------------------------------

class TestVocabularyClosure:
    def test_pass(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(EntityType("Person"), "p1", {"name": "Alice", "verified": True})
        result = validate(graph, world)
        c1 = result.conditions[0]
        assert c1.condition_name == "Vocabulary Closure"
        assert c1.status == ConditionStatus.PASS

    def test_fail_unknown_entity(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(EntityType("Alien"), "a1", {"name": "Zog"})
        result = validate(graph, world)
        c1 = result.conditions[0]
        assert c1.status == ConditionStatus.FAIL
        assert any("Alien" in d for d in c1.details)

    def test_fail_unknown_relation(self):
        graph = _simple_domain()
        lang = graph.languages["TestDomain"]
        person = EntityType("Person")
        item = EntityType("Item")
        from dds.types import Relation
        fake_rel = Relation("steals", source=person, target=item)

        world = SemanticWorld()
        world.add_element(person, "p1", {"name": "Bob", "verified": True})
        world.add_element(item, "i1", {"label": "Book"})
        world.add_relation(fake_rel, "p1", "i1")

        result = validate(graph, world)
        c1 = result.conditions[0]
        assert c1.status == ConditionStatus.FAIL


# ---------------------------------------------------------------------------
# Condition 2: Relation Admissibility
# ---------------------------------------------------------------------------

class TestRelationAdmissibility:
    def test_pass(self):
        graph = _simple_domain()
        lang = graph.languages["TestDomain"]
        owns = [r for r in lang.relations if r.name == "owns"][0]

        world = SemanticWorld()
        world.add_element(EntityType("Person"), "p1", {"name": "Alice", "verified": True})
        world.add_element(EntityType("Item"), "i1", {"label": "Book"})
        world.add_relation(owns, "p1", "i1")

        result = validate(graph, world)
        c2 = result.conditions[1]
        assert c2.condition_name == "Relation Admissibility"
        assert c2.status == ConditionStatus.PASS

    def test_fail_type_mismatch(self):
        graph = _simple_domain()
        lang = graph.languages["TestDomain"]
        owns = [r for r in lang.relations if r.name == "owns"][0]

        world = SemanticWorld()
        # owns goes Person→Item, but we put Item→Person
        world.add_element(EntityType("Item"), "i1", {"label": "Book"})
        world.add_element(EntityType("Person"), "p1", {"name": "Alice", "verified": True})
        world.add_relation(owns, "i1", "p1")  # wrong direction

        result = validate(graph, world)
        c2 = result.conditions[1]
        assert c2.status == ConditionStatus.FAIL


# ---------------------------------------------------------------------------
# Condition 3: Completeness with Explicit Gaps
# ---------------------------------------------------------------------------

class TestCompleteness:
    def test_pass_all_must_satisfied(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(EntityType("Person"), "p1", {"name": "Alice", "verified": True})
        result = validate(graph, world)
        c3 = result.conditions[2]
        assert c3.passed()

    def test_fail_must_attribute_missing(self):
        graph = _simple_domain()
        world = SemanticWorld()
        # 'verified' is MUST but not provided at all
        world.add_element(EntityType("Person"), "p1", {"name": "Alice"})
        result = validate(graph, world)
        c3 = result.conditions[2]
        assert c3.status == ConditionStatus.FAIL

    def test_unknown_surfaced(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(EntityType("Person"), "p1", {"name": "Alice", "verified": UNKNOWN})
        result = validate(graph, world)
        c3 = result.conditions[2]
        assert c3.status == ConditionStatus.UNKNOWN_PRESENT
        assert c3.passed()  # UNKNOWN is valid but flagged


# ---------------------------------------------------------------------------
# Condition 4: No Implicit Inference
# ---------------------------------------------------------------------------

class TestNoInference:
    def test_pass_with_provenance(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(
            EntityType("Person"), "p1",
            {"name": "Alice", "verified": True},
            provenance="input_form",
        )
        result = validate(graph, world)
        c4 = result.conditions[3]
        assert c4.status == ConditionStatus.PASS
        assert len(c4.details) == 0

    def test_missing_provenance_noted(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(EntityType("Person"), "p1", {"name": "Alice", "verified": True})
        result = validate(graph, world)
        c4 = result.conditions[3]
        # Still passes but notes missing provenance
        assert c4.status == ConditionStatus.PASS
        assert any("no provenance" in d for d in c4.details)


# ---------------------------------------------------------------------------
# Condition 5: Consistency
# ---------------------------------------------------------------------------

class TestConsistency:
    def test_pass(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(EntityType("Person"), "p1", {"name": "Alice", "verified": True})
        result = validate(graph, world)
        c5 = result.conditions[4]
        assert c5.status == ConditionStatus.PASS

    def test_fail_constraint_violation(self):
        lang = DomainLanguage(name="Constrained")
        thing = lang.add_entity("Thing")
        lang.add_attribute(thing, "value", value_type=int)
        lang.add_constraint(
            name="positive_value",
            description="Value must be positive",
            predicate=lambda w: all(
                e.attribute_values.get("value", 1) > 0
                for e in w.get_elements_by_type(EntityType("Thing"))
            ),
        )

        graph = DomainLanguageGraph()
        graph.add_language(lang)

        world = SemanticWorld()
        world.add_element(EntityType("Thing"), "t1", {"value": -5})

        result = validate(graph, world)
        c5 = result.conditions[4]
        assert c5.status == ConditionStatus.FAIL
        assert any("positive_value" in d for d in c5.details)


# ---------------------------------------------------------------------------
# Full DDS-valid predicate
# ---------------------------------------------------------------------------

class TestDDSValid:
    def test_fully_valid(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(
            EntityType("Person"), "p1",
            {"name": "Alice", "verified": True},
            provenance="input",
        )
        result = validate(graph, world)
        assert result.is_valid

    def test_invalid_propagates(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(EntityType("Alien"), "a1", {"name": "Zog"})
        result = validate(graph, world)
        assert not result.is_valid

    def test_deterministic(self):
        """Same D and W must always produce the same result."""
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(
            EntityType("Person"), "p1",
            {"name": "Alice", "verified": True},
            provenance="input",
        )
        r1 = validate(graph, world)
        r2 = validate(graph, world)
        assert r1.is_valid == r2.is_valid
        assert len(r1.conditions) == len(r2.conditions)
        for c1, c2 in zip(r1.conditions, r2.conditions):
            assert c1.status == c2.status


# ---------------------------------------------------------------------------
# Layer 2: check_admissibility (DDS scope — conditions 1-4)
# ---------------------------------------------------------------------------

class TestCheckAdmissibility:
    def test_admissible(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(
            EntityType("Person"), "p1",
            {"name": "Alice", "verified": True},
            provenance="input",
        )
        result = check_admissibility(graph, world)
        assert result.is_admissible
        assert len(result.conditions) == 4  # conditions 1-4 only

    def test_not_admissible_unknown_entity(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(EntityType("Alien"), "a1", {"name": "Zog"})
        result = check_admissibility(graph, world)
        assert not result.is_admissible

    def test_admissible_with_unknowns(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(
            EntityType("Person"), "p1",
            {"name": "Alice", "verified": UNKNOWN},
            provenance="input",
        )
        result = check_admissibility(graph, world)
        assert result.is_admissible  # UNKNOWN is admissible
        assert result.has_unknowns

    def test_not_admissible_missing_must(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(EntityType("Person"), "p1", {"name": "Alice"})
        result = check_admissibility(graph, world)
        assert not result.is_admissible

    def test_four_conditions_returned(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(
            EntityType("Person"), "p1",
            {"name": "Alice", "verified": True},
            provenance="input",
        )
        result = check_admissibility(graph, world)
        names = [c.condition_name for c in result.conditions]
        assert names == [
            "Vocabulary Closure",
            "Relation Admissibility",
            "Completeness with Explicit Gaps",
            "No Implicit Inference",
        ]


# ---------------------------------------------------------------------------
# Layer 3: evaluate_rules (execution layer — NOT part of DDS)
# ---------------------------------------------------------------------------

class TestEvaluateRules:
    def test_no_violations(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(EntityType("Person"), "p1", {"name": "Alice", "verified": True})
        result = evaluate_rules(graph, world)
        assert result.is_valid
        assert len(result.violations) == 0
        assert len(result.advisories) == 0
        assert len(result.constraint_failures) == 0

    def test_constraint_violation(self):
        lang = DomainLanguage(name="Constrained")
        thing = lang.add_entity("Thing")
        lang.add_attribute(thing, "value", value_type=int)
        lang.add_constraint(
            name="positive_value",
            description="Value must be positive",
            predicate=lambda w: all(
                e.attribute_values.get("value", 1) > 0
                for e in w.get_elements_by_type(EntityType("Thing"))
            ),
        )

        graph = DomainLanguageGraph()
        graph.add_language(lang)

        world = SemanticWorld()
        world.add_element(EntityType("Thing"), "t1", {"value": -5})

        result = evaluate_rules(graph, world)
        assert not result.is_valid
        assert len(result.constraint_failures) > 0
        assert any("positive_value" in cf for cf in result.constraint_failures)

    def test_must_not_violation(self):
        """MUST_NOT with condition should produce a violation."""
        lang = DomainLanguage(name="Restricted")
        thing = lang.add_entity("Thing")
        flag = lang.add_attribute(thing, "forbidden", value_type=bool)
        lang.must_not(
            thing,
            condition=lambda w: [
                f"thing '{e.identity}' is forbidden"
                for e in w.get_elements_by_type(EntityType("Thing"))
                if e.attribute_values.get("forbidden") is True
            ] or False,
            description="Forbidden things must not appear",
        )

        graph = DomainLanguageGraph()
        graph.add_language(lang)

        world = SemanticWorld()
        world.add_element(EntityType("Thing"), "t1", {"forbidden": True})

        result = evaluate_rules(graph, world)
        assert not result.is_valid
        assert len(result.violations) > 0

    def test_should_advisory(self):
        """SHOULD with condition should produce an advisory."""
        lang = DomainLanguage(name="Advisory")
        thing = lang.add_entity("Thing")
        lang.add_attribute(thing, "reviewed", value_type=bool)
        lang.should(
            thing,
            condition=lambda w: [
                f"thing '{e.identity}' not reviewed"
                for e in w.get_elements_by_type(EntityType("Thing"))
                if e.attribute_values.get("reviewed") is False
            ] or False,
            description="Things should be reviewed",
        )

        graph = DomainLanguageGraph()
        graph.add_language(lang)

        world = SemanticWorld()
        world.add_element(EntityType("Thing"), "t1", {"reviewed": False})

        result = evaluate_rules(graph, world)
        assert result.is_valid  # advisories don't fail
        assert len(result.advisories) > 0

    def test_layers_compose(self):
        """check_admissibility + evaluate_rules should cover same ground as validate."""
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(
            EntityType("Person"), "p1",
            {"name": "Alice", "verified": True},
            provenance="input",
        )

        admissibility = check_admissibility(graph, world)
        rules = evaluate_rules(graph, world)
        combined = validate(graph, world)

        # Both should agree on validity
        assert admissibility.is_admissible
        assert rules.is_valid
        assert combined.is_valid
