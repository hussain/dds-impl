"""Validation — DDS admissibility and rule evaluation.

This module cleanly separates two layers:

  LAYER 1 — DDS Self-QC (self_validate):
    Validates the domain definition itself, independent of any instance data.
    Checks structural coherence, normative contradictions, cycle detection.

  LAYER 2 — DDS Admissibility (check_admissibility):
    Checks whether a semantic world W is structurally admissible under
    domain D. Four conditions from Section 5.1:
      1. Vocabulary Closure
      2. Relation Admissibility
      3. Completeness with Explicit Gaps
      4. No Implicit Inference

  LAYER 3 — Execution (evaluate_rules):
    NOT part of DDS itself. Demonstrates how an execution layer consumes
    DDS-defined normative rules to evaluate concrete records. Evaluates:
      - MUST_NOT violations (hard failures)
      - SHOULD / SHOULD_NOT advisories (soft flags)
      - Domain constraint predicates

  Combined — validate():
    Composes Layers 2 + 3 into a single five-condition result for
    backward compatibility. Condition 5 (Consistency) is the execution
    layer's rule evaluation folded into the DDS-valid predicate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .domain_language import DomainLanguage
from .domain_language_graph import DomainLanguageGraph, EdgeLabel
from .normative import NormativeOp, Severity, check_all_interactions
from .types import (
    UNKNOWN,
    Attribute,
    Constraint,
    EntityType,
    NormativeTarget,
    OperationType,
    Optionality,
    Relation,
)


# ---------------------------------------------------------------------------
# Semantic World — W = (S, R)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SemanticElement:
    """An asserted semantic element in the world W.

    Represents an entity instance with its attribute values.
    Values may be concrete or UNKNOWN.
    """
    entity_type: EntityType
    identity: str  # unique identifier for this element
    attribute_values: dict[str, Any] = field(default_factory=dict)
    provenance: str = ""  # traces to gating source

    def __hash__(self) -> int:
        return hash((self.entity_type, self.identity))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemanticElement):
            return NotImplemented
        return self.entity_type == other.entity_type and self.identity == other.identity


@dataclass(frozen=True)
class SemanticRelation:
    """An asserted relation in the world W."""
    relation: Relation
    source_id: str
    target_id: str
    provenance: str = ""

    def __hash__(self) -> int:
        return hash((self.relation, self.source_id, self.target_id))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemanticRelation):
            return NotImplemented
        return (
            self.relation == other.relation
            and self.source_id == other.source_id
            and self.target_id == other.target_id
        )


@dataclass
class SemanticWorld:
    """W = (S, R) — a candidate semantic world.

    Paper reference: Section 5.1 — "Let W = (S, R) where S is a set of
    asserted semantic elements and R is a set of asserted relations."
    """
    elements: list[SemanticElement] = field(default_factory=list)
    relations: list[SemanticRelation] = field(default_factory=list)

    def add_element(
        self,
        entity_type: EntityType,
        identity: str,
        attribute_values: dict[str, Any] | None = None,
        provenance: str = "",
    ) -> SemanticElement:
        elem = SemanticElement(
            entity_type=entity_type,
            identity=identity,
            attribute_values=attribute_values or {},
            provenance=provenance,
        )
        self.elements.append(elem)
        return elem

    def add_relation(
        self,
        relation: Relation,
        source_id: str,
        target_id: str,
        provenance: str = "",
    ) -> SemanticRelation:
        rel = SemanticRelation(
            relation=relation,
            source_id=source_id,
            target_id=target_id,
            provenance=provenance,
        )
        self.relations.append(rel)
        return rel

    def get_elements_by_type(self, entity_type: EntityType) -> list[SemanticElement]:
        return [e for e in self.elements if e.entity_type == entity_type]

    def get_element_by_id(self, identity: str) -> SemanticElement | None:
        for e in self.elements:
            if e.identity == identity:
                return e
        return None


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class ConditionStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN_PRESENT = "UNKNOWN_PRESENT"  # passed but with UNKNOWN gaps


@dataclass
class ConditionResult:
    """Result of checking one of the DDS-valid conditions."""
    condition_number: int
    condition_name: str
    status: ConditionStatus
    details: list[str] = field(default_factory=list)

    def passed(self) -> bool:
        return self.status in (ConditionStatus.PASS, ConditionStatus.UNKNOWN_PRESENT)


@dataclass
class AdmissibilityResult:
    """Result of DDS admissibility check (Section 5.1, conditions 1-4).

    DDS scope: validates structural admissibility of a semantic world
    under the domain definition. This is what DDS guarantees — the
    boundary between D and W.
    """
    conditions: list[ConditionResult] = field(default_factory=list)

    @property
    def is_admissible(self) -> bool:
        return all(c.passed() for c in self.conditions)

    @property
    def has_unknowns(self) -> bool:
        return any(c.status == ConditionStatus.UNKNOWN_PRESENT for c in self.conditions)

    def summary(self) -> str:
        lines = []
        status = "ADMISSIBLE" if self.is_admissible else "NOT ADMISSIBLE"
        if self.is_admissible and self.has_unknowns:
            status = "ADMISSIBLE (with UNKNOWN gaps)"
        lines.append(f"DDS Admissibility: {status}")
        lines.append("-" * 50)
        for c in self.conditions:
            mark = {
                ConditionStatus.PASS: "PASS",
                ConditionStatus.FAIL: "FAIL",
                ConditionStatus.UNKNOWN_PRESENT: "PASS (UNKNOWN)",
            }[c.status]
            lines.append(f"  {c.condition_number}. {c.condition_name}: {mark}")
            for detail in c.details:
                lines.append(f"     - {detail}")
        return "\n".join(lines)


@dataclass
class RuleEvaluationResult:
    """Result of normative rule evaluation (execution layer).

    This is NOT part of DDS itself. It demonstrates how an execution
    layer consumes DDS-defined normative rules to evaluate concrete
    records against domain constraints.
    """
    violations: list[str] = field(default_factory=list)
    advisories: list[str] = field(default_factory=list)
    constraint_failures: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.violations) == 0 and len(self.constraint_failures) == 0

    def summary(self) -> str:
        lines = []
        status = "PASS" if self.is_valid else "FAIL"
        lines.append(f"Rule Evaluation: {status}")
        lines.append("-" * 50)
        if self.violations:
            lines.append(f"  Violations ({len(self.violations)}):")
            for v in self.violations:
                lines.append(f"    - {v}")
        if self.advisories:
            lines.append(f"  Advisories ({len(self.advisories)}):")
            for a in self.advisories:
                lines.append(f"    - {a}")
        if self.constraint_failures:
            lines.append(f"  Constraint failures ({len(self.constraint_failures)}):")
            for cf in self.constraint_failures:
                lines.append(f"    - {cf}")
        if not self.violations and not self.advisories and not self.constraint_failures:
            lines.append("  No issues found.")
        return "\n".join(lines)


@dataclass
class ValidationResult:
    """Complete result of DDS-valid(D, W) evaluation.

    Paper reference: Section 5.1 — "A semantic world W is DDS-valid under
    domain D if and only if all of the following conditions hold"

    Composes admissibility (conditions 1-4) and consistency (condition 5).
    """
    conditions: list[ConditionResult] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return all(c.passed() for c in self.conditions)

    @property
    def has_unknowns(self) -> bool:
        return any(c.status == ConditionStatus.UNKNOWN_PRESENT for c in self.conditions)

    def summary(self) -> str:
        lines = []
        status = "VALID" if self.is_valid else "INVALID"
        if self.is_valid and self.has_unknowns:
            status = "VALID (with UNKNOWN gaps)"
        lines.append(f"DDS-valid: {status}")
        lines.append("-" * 50)
        for c in self.conditions:
            mark = {
                ConditionStatus.PASS: "PASS",
                ConditionStatus.FAIL: "FAIL",
                ConditionStatus.UNKNOWN_PRESENT: "PASS (UNKNOWN)",
            }[c.status]
            lines.append(f"  {c.condition_number}. {c.condition_name}: {mark}")
            for detail in c.details:
                lines.append(f"     - {detail}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Self-validation result
# ---------------------------------------------------------------------------

@dataclass
class SelfValidationResult:
    """Result of DDS self-validation (Section 5.2).

    Validates the domain definition itself, independent of any instance data.
    """
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = []
        status = "VALID" if self.is_valid else "INVALID"
        lines.append(f"DDS Self-Validation: {status}")
        lines.append("-" * 50)
        if self.errors:
            lines.append(f"  Errors ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"    - {e}")
        if self.warnings:
            lines.append(f"  Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"    - {w}")
        if not self.errors and not self.warnings:
            lines.append("  No issues found.")
        return "\n".join(lines)


# ===========================================================================
# LAYER 1: DDS Self-Validation (Section 5.2)
# ===========================================================================

def self_validate(graph: DomainLanguageGraph) -> SelfValidationResult:
    """Validate the domain definition itself.

    DDS Layer 1: Self-QC — validates domain definition coherence
    independent of any instance data.

    Checks:
    - Structural issues (cycles, missing targets, unresolved references)
    - Normative operator contradictions within each Domain Language
    - Closure (undefined symbols)
    - Orphaned definitions (unreachable from any other)
    """
    result = SelfValidationResult()

    # 1. Structural validation of the graph
    structural_errors = graph.structural_validation()
    result.errors.extend(structural_errors)

    # 2. Normative interaction checks within each language
    for lang in graph.languages.values():
        diagnostics = lang.check_normative_interactions()
        for diag in diagnostics:
            msg = f"[{lang.name}] {diag.message}"
            if diag.severity == Severity.ERROR:
                result.errors.append(msg)
            else:
                result.warnings.append(msg)

    # 3. Closure checks
    for lang in graph.languages.values():
        closure_errors = lang.check_closure(resolved_imports=graph.languages)
        result.errors.extend(f"[{lang.name}] {e}" for e in closure_errors)

    # 4. Orphan detection (languages not imported by any other)
    imported_by: dict[str, set[str]] = {name: set() for name in graph.languages}
    for edge in graph.edges:
        imported_by[edge.target].add(edge.source)

    if len(graph.languages) > 1:
        for name in graph.languages:
            has_outgoing = any(e.source == name for e in graph.edges)
            has_incoming = bool(imported_by[name])
            if not has_outgoing and not has_incoming:
                result.warnings.append(
                    f"Orphaned language: '{name}' has no edges in the graph"
                )

    return result


# ===========================================================================
# LAYER 2: DDS Admissibility (Section 5.1, conditions 1-4)
# ===========================================================================

def check_admissibility(
    graph: DomainLanguageGraph, world: SemanticWorld
) -> AdmissibilityResult:
    """Check DDS admissibility — conditions 1-4.

    DDS Layer 2: Validates structural admissibility of a semantic world
    under the domain definition. This is what DDS guarantees: the
    semantic boundary between D and W.

    Conditions checked:
      1. Vocabulary Closure — S subset of Vocab(DomLG)
      2. Relation Admissibility — relations resolve through DomLG edges
      3. Completeness with Explicit Gaps — MUST requirements satisfied or UNKNOWN
      4. No Implicit Inference — every element traceable to gated input
    """
    result = AdmissibilityResult()
    result.conditions.append(_check_vocabulary_closure(graph, world))
    result.conditions.append(_check_relation_admissibility(graph, world))
    result.conditions.append(_check_completeness(graph, world))
    result.conditions.append(_check_no_inference(world))
    return result


# ===========================================================================
# LAYER 3: Execution — Rule Evaluation (NOT part of DDS)
# ===========================================================================

def evaluate_rules(
    graph: DomainLanguageGraph, world: SemanticWorld
) -> RuleEvaluationResult:
    """Evaluate normative rules against concrete records.

    EXECUTION LAYER — NOT part of DDS itself. This demonstrates how an
    execution layer (e.g., a DDG runtime or application framework)
    consumes DDS-defined normative rules to validate concrete records.

    DDS defines WHAT the rules are and ensures the domain is well-formed.
    This function APPLIES those rules to a specific semantic world.

    Evaluates:
      - MUST_NOT rules (conditional): hard failures
      - SHOULD rules (conditional): soft advisories
      - SHOULD_NOT rules (conditional): soft advisories
      - Constraint predicates: hard failures
    """
    result = RuleEvaluationResult()

    for lang in graph.languages.values():
        # --- MUST_NOT rules ---
        for rule in lang.normative_rules:
            if rule.operator != NormativeOp.MUST_NOT:
                continue
            target = rule.target
            if target.condition is not None:
                try:
                    violation = target.condition(world)
                    if violation:
                        desc = target.description or repr(target.element)
                        result.violations.append(
                            f"MUST_NOT violation: {desc}"
                        )
                        if isinstance(violation, list):
                            for v in violation:
                                result.violations.append(f"  -> {v}")
                except Exception as e:
                    result.violations.append(
                        f"Error evaluating MUST_NOT condition: {e}"
                    )
            elif isinstance(target.element, EntityType):
                elements = world.get_elements_by_type(target.element)
                if elements:
                    result.violations.append(
                        f"MUST_NOT({target.element}): "
                        f"forbidden entity type found ({len(elements)} instances)"
                    )

        # --- SHOULD rules ---
        for rule in lang.normative_rules:
            if rule.operator != NormativeOp.SHOULD:
                continue
            target = rule.target
            if target.condition is not None:
                try:
                    issue = target.condition(world)
                    if issue:
                        desc = target.description or repr(target.element)
                        result.advisories.append(f"SHOULD advisory: {desc}")
                        if isinstance(issue, list):
                            for v in issue:
                                result.advisories.append(f"  -> {v}")
                except Exception:
                    pass

        # --- SHOULD_NOT rules ---
        for rule in lang.normative_rules:
            if rule.operator != NormativeOp.SHOULD_NOT:
                continue
            target = rule.target
            if target.condition is not None:
                try:
                    issue = target.condition(world)
                    if issue:
                        desc = target.description or repr(target.element)
                        result.advisories.append(
                            f"SHOULD_NOT advisory: {desc}"
                        )
                        if isinstance(issue, list):
                            for v in issue:
                                result.advisories.append(f"  -> {v}")
                except Exception:
                    pass

        # --- Constraint predicates ---
        for constraint in lang.constraints:
            try:
                satisfied = constraint.predicate(world)
                if not satisfied:
                    result.constraint_failures.append(
                        f"[{lang.name}] {constraint.name}: "
                        f"{constraint.description}"
                    )
            except Exception as e:
                result.constraint_failures.append(
                    f"Error evaluating constraint '{constraint.name}': {e}"
                )

    return result


# ===========================================================================
# Combined: DDS-valid(D, W) — five-condition predicate
# ===========================================================================

def validate(
    graph: DomainLanguageGraph, world: SemanticWorld
) -> ValidationResult:
    """Evaluate DDS-valid(D, W).

    Paper reference: Section 5.1 — The admissibility predicate.

    Composes Layer 2 (admissibility, conditions 1-4) and Layer 3
    (rule evaluation, folded into condition 5 as "Consistency").

    Conditions:
      1. Vocabulary Closure        [DDS Layer 2]
      2. Relation Admissibility    [DDS Layer 2]
      3. Completeness with Gaps    [DDS Layer 2]
      4. No Implicit Inference     [DDS Layer 2]
      5. Consistency               [Execution Layer 3]
    """
    result = ValidationResult()

    # Conditions 1-4: DDS admissibility
    result.conditions.append(_check_vocabulary_closure(graph, world))
    result.conditions.append(_check_relation_admissibility(graph, world))
    result.conditions.append(_check_completeness(graph, world))
    result.conditions.append(_check_no_inference(world))

    # Condition 5: Consistency (execution-layer rule evaluation)
    result.conditions.append(_check_consistency(graph, world))

    return result


# ---------------------------------------------------------------------------
# Condition 1: Vocabulary Closure
# ---------------------------------------------------------------------------

def _check_vocabulary_closure(
    graph: DomainLanguageGraph, world: SemanticWorld
) -> ConditionResult:
    """S subset of Vocab(DomLG) and R subset of Rel(DomLG).

    Paper reference: Section 5.1, condition 1 — "Every semantic element
    referenced in W belongs to the closed vocabulary defined by D"
    """
    composed = graph.composed_vocab()
    entity_types = {item for item in composed if isinstance(item, EntityType)}
    composed_rels = graph.composed_relations()

    details: list[str] = []
    failed = False

    for elem in world.elements:
        if elem.entity_type not in entity_types:
            details.append(
                f"Entity type '{elem.entity_type.name}' (element '{elem.identity}') "
                f"not in Vocab(DomLG)"
            )
            failed = True

    for rel in world.relations:
        if rel.relation not in composed_rels:
            details.append(
                f"Relation '{rel.relation.name}' not declared in any Domain Language"
            )
            failed = True

    return ConditionResult(
        condition_number=1,
        condition_name="Vocabulary Closure",
        status=ConditionStatus.FAIL if failed else ConditionStatus.PASS,
        details=details,
    )


# ---------------------------------------------------------------------------
# Condition 2: Relation Admissibility
# ---------------------------------------------------------------------------

def _check_relation_admissibility(
    graph: DomainLanguageGraph, world: SemanticWorld
) -> ConditionResult:
    """Every relation resolves through DomLG edges.

    Paper reference: Section 5.1, condition 2 — "the relation r is declared
    admissible between the Domain Languages containing s1 and s2"
    """
    details: list[str] = []
    failed = False

    # Build map: entity_type -> which language(s) define it
    type_to_lang: dict[EntityType, set[str]] = {}
    for lang_name, lang in graph.languages.items():
        for entity in lang.entities:
            type_to_lang.setdefault(entity, set()).add(lang_name)

    # Build map: relation -> which language defines it
    rel_to_lang: dict[Relation, str] = {}
    for lang_name, lang in graph.languages.items():
        for rel in lang.relations:
            rel_to_lang[rel] = lang_name

    # Check each asserted relation
    for sem_rel in world.relations:
        rel = sem_rel.relation

        if rel not in rel_to_lang:
            details.append(f"Relation '{rel.name}' not declared in any Domain Language")
            failed = True
            continue

        # Find the elements involved
        source_elem = world.get_element_by_id(sem_rel.source_id)
        target_elem = world.get_element_by_id(sem_rel.target_id)

        if source_elem is None or target_elem is None:
            details.append(
                f"Relation '{rel.name}' references unknown element(s): "
                f"source={sem_rel.source_id}, target={sem_rel.target_id}"
            )
            failed = True
            continue

        # Check that the source and target types match the relation declaration
        if source_elem.entity_type != rel.source:
            details.append(
                f"Relation '{rel.name}': source '{source_elem.identity}' has type "
                f"'{source_elem.entity_type.name}', expected '{rel.source.name}'"
            )
            failed = True

        if target_elem.entity_type != rel.target:
            details.append(
                f"Relation '{rel.name}': target '{target_elem.identity}' has type "
                f"'{target_elem.entity_type.name}', expected '{rel.target.name}'"
            )
            failed = True

        # If source and target are in different languages, check that
        # a DomLG edge connects them
        source_langs = type_to_lang.get(source_elem.entity_type, set())
        target_langs = type_to_lang.get(target_elem.entity_type, set())

        if source_langs and target_langs and not source_langs & target_langs:
            # Cross-language relation — need a DomLG edge
            has_edge = False
            for edge in graph.edges:
                if edge.source in source_langs and edge.target in target_langs:
                    has_edge = True
                    break
                if edge.source in target_langs and edge.target in source_langs:
                    has_edge = True
                    break
            if not has_edge:
                details.append(
                    f"Cross-language relation '{rel.name}' between "
                    f"{source_langs} and {target_langs} has no DomLG edge"
                )
                failed = True

    return ConditionResult(
        condition_number=2,
        condition_name="Relation Admissibility",
        status=ConditionStatus.FAIL if failed else ConditionStatus.PASS,
        details=details,
    )


# ---------------------------------------------------------------------------
# Condition 3: Completeness with Explicit Gaps
# ---------------------------------------------------------------------------

def _check_completeness(
    graph: DomainLanguageGraph, world: SemanticWorld
) -> ConditionResult:
    """MUST elements satisfied or explicitly marked UNKNOWN.

    Paper reference: Section 5.1, condition 3 — "For every semantic
    requirement imposed by D, W either satisfies the requirement or
    explicitly marks it as UNKNOWN. Silent omission is forbidden."
    """
    details: list[str] = []
    failed = False
    has_unknowns = False

    for lang in graph.languages.values():
        for rule in lang.normative_rules:
            if rule.operator != NormativeOp.MUST:
                continue

            target = rule.target.element

            # MUST on an attribute — check all elements of the entity type
            if isinstance(target, Attribute):
                elements = world.get_elements_by_type(target.entity)
                for elem in elements:
                    val = elem.attribute_values.get(target.name)
                    if val is None:
                        details.append(
                            f"MUST({target}): element '{elem.identity}' "
                            f"silently omits required attribute"
                        )
                        failed = True
                    elif val is UNKNOWN or val == UNKNOWN:
                        details.append(
                            f"MUST({target}): element '{elem.identity}' "
                            f"has UNKNOWN value (explicit gap)"
                        )
                        has_unknowns = True

            # MUST on a relation — check all elements of the source type have it
            elif isinstance(target, Relation):
                elements = world.get_elements_by_type(target.source)
                for elem in elements:
                    has_relation = any(
                        sr.relation == target and sr.source_id == elem.identity
                        for sr in world.relations
                    )
                    if not has_relation:
                        details.append(
                            f"MUST({target}): element '{elem.identity}' "
                            f"missing required relation"
                        )
                        failed = True

    if failed:
        status = ConditionStatus.FAIL
    elif has_unknowns:
        status = ConditionStatus.UNKNOWN_PRESENT
    else:
        status = ConditionStatus.PASS

    return ConditionResult(
        condition_number=3,
        condition_name="Completeness with Explicit Gaps",
        status=status,
        details=details,
    )


# ---------------------------------------------------------------------------
# Condition 4: No Implicit Inference
# ---------------------------------------------------------------------------

def _check_no_inference(world: SemanticWorld) -> ConditionResult:
    """Every element directly traceable to gated input.

    Paper reference: Section 5.1, condition 4 — "No semantic fact may exist
    in W unless it is directly stated in the gated domain definition"

    We check that every element and relation has a provenance field.
    Empty provenance is flagged as a warning (may indicate inferred content).
    """
    details: list[str] = []

    for elem in world.elements:
        if not elem.provenance:
            details.append(
                f"Element '{elem.identity}' ({elem.entity_type.name}) "
                f"has no provenance — may be inferred"
            )

    for rel in world.relations:
        if not rel.provenance:
            details.append(
                f"Relation '{rel.relation.name}' ({rel.source_id} -> {rel.target_id}) "
                f"has no provenance — may be inferred"
            )

    # For this reference implementation, we pass but report missing provenance.
    # A stricter implementation could fail on missing provenance.
    return ConditionResult(
        condition_number=4,
        condition_name="No Implicit Inference",
        status=ConditionStatus.PASS,
        details=details,
    )


# ---------------------------------------------------------------------------
# Condition 5: Consistency (wraps execution-layer rule evaluation)
# ---------------------------------------------------------------------------

def _check_consistency(
    graph: DomainLanguageGraph, world: SemanticWorld
) -> ConditionResult:
    """No constraint violations.

    Paper reference: Section 5.1, condition 5 — "No pair of semantic facts
    in W may jointly violate constraints or invariants defined by D"

    This condition wraps the execution-layer rule evaluation into the
    five-condition DDS-valid predicate for completeness.

    Checks:
    - MUST_NOT normative rules (conditional)
    - SHOULD / SHOULD_NOT rules (advisories, do not fail)
    - Constraint predicates from all Domain Languages
    """
    # Delegate to the execution-layer evaluate_rules function
    rule_result = evaluate_rules(graph, world)

    details: list[str] = []
    failed = False

    # Map violations to details
    for v in rule_result.violations:
        details.append(v)
        failed = True

    # Map advisories to details (don't fail)
    for a in rule_result.advisories:
        details.append(a)

    # Map constraint failures to details
    for cf in rule_result.constraint_failures:
        details.append(f"Constraint violation: {cf}")
        failed = True

    return ConditionResult(
        condition_number=5,
        condition_name="Consistency",
        status=ConditionStatus.FAIL if failed else ConditionStatus.PASS,
        details=details,
    )
