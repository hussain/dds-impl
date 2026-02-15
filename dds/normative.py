"""Normative operators, interaction rules, and Self-QC finding types.

Paper reference: Section 2.2 — DDS adopts RFC 2119 keywords as its normative
operator set: MUST, MUST NOT, SHOULD, SHOULD NOT, MAY.

Section 2.3 — Modality compatibility table, condition specificity (lex
specialis), and override annotations.

Section 6.2 — Self-QC algorithm with six finding types.

Each operator is a purely definitional signal; none produces runtime behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from .types import NormativeTarget


class NormativeOp(Enum):
    """The five normative operators from RFC 2119 / DDS Section 2.2."""
    MUST = "MUST"
    MUST_NOT = "MUST_NOT"
    SHOULD = "SHOULD"
    SHOULD_NOT = "SHOULD_NOT"
    MAY = "MAY"


@dataclass(frozen=True)
class NormativeRule:
    """A normative rule: r = (modality, target, constraint_L, condition_L, override_ref).

    Paper reference: Section 2.1 — normative rules as tuples.

    In the implementation:
    - modality → operator (NormativeOp)
    - target → target.element (vocabulary reference for Self-QC grouping)
    - constraint_L → implicit (delegated to execution layer)
    - condition_L → target.condition (callable or None for unconditional)
    - override_ref → override_ref (reference to overridden rule, or None)
    """
    operator: NormativeOp
    target: NormativeTarget
    override_ref: NormativeRule | None = None

    def __repr__(self) -> str:
        override = " [OVERRIDE]" if self.override_ref is not None else ""
        return f"{self.operator.value}({self.target.element}){override}"


# ---------------------------------------------------------------------------
# Self-QC Finding Types (Section 6.2)
# ---------------------------------------------------------------------------

class FindingType(Enum):
    """The six Self-QC finding types.

    Paper reference: Section 6.2 — Self-QC Finding Types.
    """
    CONFLICT = "conflict"      # Conflicting modalities, same specificity, no override
    EXCEPTION = "exception"    # Conflicting modalities, different specificity (lex specialis)
    OVERRIDE = "override"      # Conflicting modalities, same specificity, override present
    OVERLAP = "overlap"        # Compatible modality pair, overlapping conditions
    AMBIGUITY = "ambiguity"    # Conflicting modalities, condition relationship undeclared
    NO_DEFAULT = "no_default"  # Target has only conditional rules


class Severity(Enum):
    ERROR = "error"      # CONFLICT
    WARNING = "warning"  # AMBIGUITY, NO_DEFAULT
    INFO = "info"        # EXCEPTION, OVERRIDE, OVERLAP


# Finding type → severity mapping
_FINDING_SEVERITY: dict[FindingType, Severity] = {
    FindingType.CONFLICT: Severity.ERROR,
    FindingType.EXCEPTION: Severity.INFO,
    FindingType.OVERRIDE: Severity.INFO,
    FindingType.OVERLAP: Severity.INFO,
    FindingType.AMBIGUITY: Severity.WARNING,
    FindingType.NO_DEFAULT: Severity.WARNING,
}


@dataclass(frozen=True)
class InteractionDiagnostic:
    """Result of checking normative operator interactions (Self-QC finding)."""
    severity: Severity
    finding_type: FindingType
    rule_a: NormativeRule
    rule_b: NormativeRule
    message: str

    def __repr__(self) -> str:
        return f"[{self.severity.value.upper()}:{self.finding_type.value}] {self.message}"


# ---------------------------------------------------------------------------
# Modality Compatibility Table (Section 2.3.1)
# ---------------------------------------------------------------------------

# Compatible pairs: redundant but not invalid → OVERLAP
_COMPATIBLE_PAIRS: set[frozenset[NormativeOp]] = {
    frozenset({NormativeOp.MUST, NormativeOp.MUST}),
    frozenset({NormativeOp.MUST, NormativeOp.SHOULD}),
    frozenset({NormativeOp.MUST, NormativeOp.MAY}),
    frozenset({NormativeOp.SHOULD, NormativeOp.SHOULD}),
    frozenset({NormativeOp.SHOULD, NormativeOp.MAY}),
    frozenset({NormativeOp.MAY, NormativeOp.MAY}),
    frozenset({NormativeOp.MUST_NOT, NormativeOp.MUST_NOT}),
    frozenset({NormativeOp.MUST_NOT, NormativeOp.SHOULD_NOT}),
    frozenset({NormativeOp.SHOULD_NOT, NormativeOp.SHOULD_NOT}),
}

# Conflicting pairs: incoherent governance → CONFLICT (unless resolved)
_CONFLICTING_PAIRS: dict[frozenset[NormativeOp], str] = {
    frozenset({NormativeOp.MUST, NormativeOp.MUST_NOT}):
        "Requiring and prohibiting the same element",
    frozenset({NormativeOp.MUST, NormativeOp.SHOULD_NOT}):
        "Obligating a discouraged element",
    frozenset({NormativeOp.SHOULD, NormativeOp.MUST_NOT}):
        "Recommending a prohibited element",
    frozenset({NormativeOp.SHOULD, NormativeOp.SHOULD_NOT}):
        "Recommending and discouraging the same element",
    frozenset({NormativeOp.MAY, NormativeOp.MUST_NOT}):
        "Permitting a prohibited element",
    frozenset({NormativeOp.MAY, NormativeOp.SHOULD_NOT}):
        "Permitting a discouraged element",
}


def is_compatible_pair(a: NormativeOp, b: NormativeOp) -> bool:
    """Check if two modalities are compatible (overlap, not conflict)."""
    pair = frozenset({a, b})
    return pair in _COMPATIBLE_PAIRS or a == b


def _same_target(a: NormativeRule, b: NormativeRule) -> bool:
    """Step 1: Check if two rules target the same element (ignoring conditions)."""
    return a.target.element == b.target.element


def check_interaction(a: NormativeRule, b: NormativeRule) -> InteractionDiagnostic | None:
    """Self-QC decision table: check a pair of normative rules.

    Paper reference: Section 6.2 — Self-QC Decision Table.

    Implements Steps A through D of the decision table:
      A: Modality compatibility check
      B: Specificity check (lex specialis)
      C: Condition relationship check
      D: Override check

    Returns a diagnostic finding, or None if rules are unrelated.
    """
    # Rules with different targets are unrelated
    if not _same_target(a, b):
        return None

    ops = frozenset({a.operator, b.operator})
    target_repr = repr(a.target.element)

    # Step A: Modality compatibility check (§2.3.1)
    if is_compatible_pair(a.operator, b.operator):
        return InteractionDiagnostic(
            Severity.INFO, FindingType.OVERLAP, a, b,
            f"Overlap: {a.operator.value} and {b.operator.value} "
            f"on same target {target_repr}"
        )

    # Conflicting pair — proceed to Step B
    conflict_reason = _CONFLICTING_PAIRS.get(ops, "Conflicting modalities")

    # Step B: Specificity check (lex specialis, §2.3.2)
    a_conditional = a.target.condition is not None
    b_conditional = b.target.condition is not None

    if a_conditional != b_conditional:
        # Different specificity: conditional excepts unconditional → EXCEPTION
        specific = a if a_conditional else b
        general = b if a_conditional else a
        return InteractionDiagnostic(
            Severity.INFO, FindingType.EXCEPTION, specific, general,
            f"Exception (lex specialis): {specific.operator.value} "
            f"conditionally excepts {general.operator.value} on {target_repr}"
        )

    # Step C: Condition relationship check
    # Both unconditional or both conditional — at same specificity level
    # (Full condition relationship analysis via vocabulary declarations
    # is future work; for now, both-unconditional proceeds to Step D,
    # and both-conditional emits AMBIGUITY if no override.)
    if a_conditional and b_conditional:
        # Both conditional — check for override before flagging
        if (a.override_ref is not None and a.override_ref is b) or \
           (b.override_ref is not None and b.override_ref is a):
            return InteractionDiagnostic(
                Severity.INFO, FindingType.OVERRIDE, a, b,
                f"Override: intentional replacement on {target_repr}"
            )
        # Condition relationship not declared → AMBIGUITY
        return InteractionDiagnostic(
            Severity.WARNING, FindingType.AMBIGUITY, a, b,
            f"Ambiguity: {a.operator.value} and {b.operator.value} on "
            f"{target_repr} — condition relationship not declared"
        )

    # Step D: Override check (both unconditional, conflicting)
    if (a.override_ref is not None and a.override_ref is b) or \
       (b.override_ref is not None and b.override_ref is a):
        return InteractionDiagnostic(
            Severity.INFO, FindingType.OVERRIDE, a, b,
            f"Override: intentional replacement on {target_repr}"
        )

    # No override → CONFLICT
    return InteractionDiagnostic(
        Severity.ERROR, FindingType.CONFLICT, a, b,
        f"Conflict: {conflict_reason} on {target_repr}"
    )


def check_all_interactions(
    rules: Sequence[NormativeRule],
) -> list[InteractionDiagnostic]:
    """Run Self-QC pairwise comparison on all rules.

    Paper reference: Section 6.2 — Steps 1 and 3 of the Self-QC algorithm.

    Returns all findings (errors, warnings, and info).
    """
    diagnostics: list[InteractionDiagnostic] = []
    rules_list = list(rules)
    for i in range(len(rules_list)):
        for j in range(i + 1, len(rules_list)):
            diag = check_interaction(rules_list[i], rules_list[j])
            if diag is not None:
                diagnostics.append(diag)
    return diagnostics
