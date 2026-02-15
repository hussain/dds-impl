"""Tests for normative operators and Self-QC interaction rules.

Tests the modality compatibility table (Section 2.3.1), condition specificity
(lex specialis, Section 2.3.2), override annotation (Section 2.3.3), and
the six Self-QC finding types (Section 6.2).
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from dds.normative import (
    NormativeOp, NormativeRule, Severity, FindingType,
    check_interaction, check_all_interactions, is_compatible_pair,
)
from dds.types import EntityType, Attribute, NormativeTarget, Optionality


def _make_rule(op: NormativeOp, name: str = "target",
               condition=None, description: str = "",
               override_ref=None) -> NormativeRule:
    entity = EntityType(name)
    target = NormativeTarget(element=entity, condition=condition,
                             description=description)
    return NormativeRule(operator=op, target=target, override_ref=override_ref)


def _make_attr_rule(op: NormativeOp, entity_name: str = "Entity",
                    attr_name: str = "attr",
                    condition=None, override_ref=None) -> NormativeRule:
    entity = EntityType(entity_name)
    attr = Attribute(name=attr_name, entity=entity)
    target = NormativeTarget(element=attr, condition=condition)
    return NormativeRule(operator=op, target=target, override_ref=override_ref)


# ---------------------------------------------------------------------------
# Modality Compatibility Table (Section 2.3.1)
# ---------------------------------------------------------------------------

class TestCompatiblePairs:
    """Compatible modality pairs → OVERLAP (INFO).

    Section 2.3.1: Compatible pairs are redundant but not invalid.
    """

    def test_must_must(self):
        a = _make_rule(NormativeOp.MUST)
        b = _make_rule(NormativeOp.MUST)
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.OVERLAP
        assert diag.severity == Severity.INFO

    def test_must_should(self):
        a = _make_rule(NormativeOp.MUST)
        b = _make_rule(NormativeOp.SHOULD)
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.OVERLAP
        assert diag.severity == Severity.INFO

    def test_must_may(self):
        a = _make_rule(NormativeOp.MUST)
        b = _make_rule(NormativeOp.MAY)
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.OVERLAP
        assert diag.severity == Severity.INFO

    def test_should_should(self):
        a = _make_rule(NormativeOp.SHOULD)
        b = _make_rule(NormativeOp.SHOULD)
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.OVERLAP
        assert diag.severity == Severity.INFO

    def test_should_may(self):
        a = _make_rule(NormativeOp.SHOULD)
        b = _make_rule(NormativeOp.MAY)
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.OVERLAP
        assert diag.severity == Severity.INFO

    def test_may_may(self):
        a = _make_rule(NormativeOp.MAY)
        b = _make_rule(NormativeOp.MAY)
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.OVERLAP
        assert diag.severity == Severity.INFO

    def test_must_not_must_not(self):
        a = _make_rule(NormativeOp.MUST_NOT)
        b = _make_rule(NormativeOp.MUST_NOT)
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.OVERLAP
        assert diag.severity == Severity.INFO

    def test_must_not_should_not(self):
        a = _make_rule(NormativeOp.MUST_NOT)
        b = _make_rule(NormativeOp.SHOULD_NOT)
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.OVERLAP
        assert diag.severity == Severity.INFO

    def test_should_not_should_not(self):
        a = _make_rule(NormativeOp.SHOULD_NOT)
        b = _make_rule(NormativeOp.SHOULD_NOT)
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.OVERLAP
        assert diag.severity == Severity.INFO

    def test_is_compatible_pair_helper(self):
        assert is_compatible_pair(NormativeOp.MUST, NormativeOp.SHOULD)
        assert is_compatible_pair(NormativeOp.MUST_NOT, NormativeOp.SHOULD_NOT)
        assert not is_compatible_pair(NormativeOp.MUST, NormativeOp.MUST_NOT)


# ---------------------------------------------------------------------------
# Conflicting Pairs → CONFLICT (Section 2.3.1)
# ---------------------------------------------------------------------------

class TestConflictingPairs:
    """Conflicting modality pairs (both unconditional, no override) → CONFLICT (ERROR).

    Section 2.3.1: Six conflicting pairs.
    """

    def test_must_vs_must_not(self):
        a = _make_rule(NormativeOp.MUST)
        b = _make_rule(NormativeOp.MUST_NOT)
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.CONFLICT
        assert diag.severity == Severity.ERROR
        assert "Conflict" in diag.message

    def test_must_vs_should_not(self):
        a = _make_rule(NormativeOp.MUST)
        b = _make_rule(NormativeOp.SHOULD_NOT)
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.CONFLICT
        assert diag.severity == Severity.ERROR

    def test_should_vs_must_not(self):
        a = _make_rule(NormativeOp.SHOULD)
        b = _make_rule(NormativeOp.MUST_NOT)
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.CONFLICT
        assert diag.severity == Severity.ERROR

    def test_should_vs_should_not(self):
        a = _make_rule(NormativeOp.SHOULD)
        b = _make_rule(NormativeOp.SHOULD_NOT)
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.CONFLICT
        assert diag.severity == Severity.ERROR

    def test_may_vs_must_not(self):
        a = _make_rule(NormativeOp.MAY)
        b = _make_rule(NormativeOp.MUST_NOT)
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.CONFLICT
        assert diag.severity == Severity.ERROR

    def test_may_vs_should_not(self):
        a = _make_rule(NormativeOp.MAY)
        b = _make_rule(NormativeOp.SHOULD_NOT)
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.CONFLICT
        assert diag.severity == Severity.ERROR

    def test_different_targets_no_finding(self):
        a = _make_rule(NormativeOp.MUST, "target_a")
        b = _make_rule(NormativeOp.MUST_NOT, "target_b")
        assert check_interaction(a, b) is None


# ---------------------------------------------------------------------------
# Condition Specificity — Lex Specialis (Section 2.3.2)
# ---------------------------------------------------------------------------

class TestLexSpecialis:
    """Conditional rule excepts unconditional rule → EXCEPTION (INFO).

    Section 2.3.2: When a conditional rule conflicts with an unconditional
    rule on the same target, lex specialis applies — the conditional rule
    is the specific provision that excepts the general unconditional one.
    """

    def test_conditional_must_not_excepts_unconditional_must(self):
        must = _make_rule(NormativeOp.MUST)
        must_not_cond = _make_rule(
            NormativeOp.MUST_NOT, condition=lambda w: True,
            description="when emergency"
        )
        diag = check_interaction(must, must_not_cond)
        assert diag is not None
        assert diag.finding_type == FindingType.EXCEPTION
        assert diag.severity == Severity.INFO
        assert "lex specialis" in diag.message.lower() or "Exception" in diag.message

    def test_conditional_may_excepts_unconditional_must_not(self):
        must_not = _make_rule(NormativeOp.MUST_NOT)
        may_cond = _make_rule(
            NormativeOp.MAY, condition=lambda w: True,
            description="when authorized"
        )
        diag = check_interaction(must_not, may_cond)
        assert diag is not None
        assert diag.finding_type == FindingType.EXCEPTION
        assert diag.severity == Severity.INFO

    def test_lex_specialis_identifies_specific_rule(self):
        """The more specific (conditional) rule is rule_a in the diagnostic."""
        general = _make_rule(NormativeOp.MUST)
        specific = _make_rule(
            NormativeOp.MUST_NOT, condition=lambda w: True,
            description="when emergency"
        )
        diag = check_interaction(general, specific)
        assert diag is not None
        assert diag.finding_type == FindingType.EXCEPTION
        # rule_a should be the specific (conditional) rule
        assert diag.rule_a.target.condition is not None
        assert diag.rule_b.target.condition is None

    def test_compatible_conditional_unconditional_is_overlap(self):
        """Compatible pair with different specificity is still OVERLAP, not EXCEPTION."""
        must = _make_rule(NormativeOp.MUST)
        should_cond = _make_rule(
            NormativeOp.SHOULD, condition=lambda w: True,
            description="when preferred"
        )
        diag = check_interaction(must, should_cond)
        assert diag is not None
        assert diag.finding_type == FindingType.OVERLAP


# ---------------------------------------------------------------------------
# Override Annotation (Section 2.3.3)
# ---------------------------------------------------------------------------

class TestOverride:
    """Explicit override_ref resolves same-specificity conflict → OVERRIDE (INFO).

    Section 2.3.3: When two conflicting rules at the same specificity level
    have an override annotation, the result is OVERRIDE rather than CONFLICT.
    """

    def test_unconditional_override(self):
        """Both unconditional, conflicting, with override → OVERRIDE."""
        original = _make_rule(NormativeOp.MUST)
        overrider = _make_rule(NormativeOp.MUST_NOT, override_ref=original)
        diag = check_interaction(original, overrider)
        assert diag is not None
        assert diag.finding_type == FindingType.OVERRIDE
        assert diag.severity == Severity.INFO

    def test_conditional_override(self):
        """Both conditional, conflicting, with override → OVERRIDE."""
        cond_a = _make_rule(
            NormativeOp.MUST, condition=lambda w: True,
            description="when X"
        )
        cond_b = _make_rule(
            NormativeOp.MUST_NOT, condition=lambda w: True,
            description="when Y", override_ref=cond_a
        )
        diag = check_interaction(cond_a, cond_b)
        assert diag is not None
        assert diag.finding_type == FindingType.OVERRIDE
        assert diag.severity == Severity.INFO

    def test_without_override_is_conflict(self):
        """Same pair without override_ref → CONFLICT."""
        a = _make_rule(NormativeOp.MUST)
        b = _make_rule(NormativeOp.MUST_NOT)
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.CONFLICT


# ---------------------------------------------------------------------------
# Ambiguity (Section 6.2)
# ---------------------------------------------------------------------------

class TestAmbiguity:
    """Both conditional, conflicting, no override → AMBIGUITY (WARNING).

    Section 6.2: When two conditional rules conflict at the same specificity
    level and no override is declared, the condition relationship is
    undeclared — this is a definition completeness issue.
    """

    def test_both_conditional_conflicting_no_override(self):
        a = _make_rule(
            NormativeOp.MUST, condition=lambda w: True,
            description="when X"
        )
        b = _make_rule(
            NormativeOp.MUST_NOT, condition=lambda w: True,
            description="when Y"
        )
        diag = check_interaction(a, b)
        assert diag is not None
        assert diag.finding_type == FindingType.AMBIGUITY
        assert diag.severity == Severity.WARNING
        assert "Ambiguity" in diag.message


# ---------------------------------------------------------------------------
# check_all_interactions
# ---------------------------------------------------------------------------

class TestCheckAllInteractions:
    def test_no_rules(self):
        assert check_all_interactions([]) == []

    def test_single_rule(self):
        assert check_all_interactions([_make_rule(NormativeOp.MUST)]) == []

    def test_multiple_findings(self):
        """MUST, MUST_NOT, SHOULD on same target (all unconditional):
        - MUST vs MUST_NOT → CONFLICT
        - SHOULD vs MUST_NOT → CONFLICT
        - MUST vs SHOULD → OVERLAP
        """
        rules = [
            _make_attr_rule(NormativeOp.MUST, "E", "a"),
            _make_attr_rule(NormativeOp.MUST_NOT, "E", "a"),
            _make_attr_rule(NormativeOp.SHOULD, "E", "a"),
        ]
        diags = check_all_interactions(rules)
        assert len(diags) == 3
        errors = [d for d in diags if d.finding_type == FindingType.CONFLICT]
        overlaps = [d for d in diags if d.finding_type == FindingType.OVERLAP]
        assert len(errors) == 2
        assert len(overlaps) == 1

    def test_mixed_findings_with_exception(self):
        """MUST (unconditional) + MUST_NOT (conditional) → EXCEPTION."""
        rules = [
            _make_attr_rule(NormativeOp.MUST, "E", "a"),
            _make_attr_rule(NormativeOp.MUST_NOT, "E", "a",
                            condition=lambda w: True),
        ]
        diags = check_all_interactions(rules)
        assert len(diags) == 1
        assert diags[0].finding_type == FindingType.EXCEPTION


# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------

class TestSeverityMapping:
    """Each finding type maps to exactly one severity level."""

    def test_conflict_is_error(self):
        a = _make_rule(NormativeOp.MUST)
        b = _make_rule(NormativeOp.MUST_NOT)
        diag = check_interaction(a, b)
        assert diag.severity == Severity.ERROR

    def test_exception_is_info(self):
        a = _make_rule(NormativeOp.MUST)
        b = _make_rule(NormativeOp.MUST_NOT, condition=lambda w: True)
        diag = check_interaction(a, b)
        assert diag.severity == Severity.INFO

    def test_override_is_info(self):
        a = _make_rule(NormativeOp.MUST)
        b = _make_rule(NormativeOp.MUST_NOT, override_ref=a)
        diag = check_interaction(a, b)
        assert diag.severity == Severity.INFO

    def test_overlap_is_info(self):
        a = _make_rule(NormativeOp.MUST)
        b = _make_rule(NormativeOp.SHOULD)
        diag = check_interaction(a, b)
        assert diag.severity == Severity.INFO

    def test_ambiguity_is_warning(self):
        a = _make_rule(NormativeOp.MUST, condition=lambda w: True)
        b = _make_rule(NormativeOp.MUST_NOT, condition=lambda w: True)
        diag = check_interaction(a, b)
        assert diag.severity == Severity.WARNING
