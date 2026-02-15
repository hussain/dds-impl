"""Domain Language — the core DDS abstraction.

Paper reference: Section 2.1

A Domain Language is a formal, closed, and modular specification of admissible
meaning within a bounded domain. It defines what can exist, what can happen,
and what is valid or invalid — without executing those semantics.

Formally: DomL = (E, A, O, N, C, I)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .types import (
    Attribute,
    Constraint,
    EntityType,
    ImportDecl,
    NormativeTarget,
    OperationType,
    Optionality,
    Relation,
)
from .normative import NormativeOp, NormativeRule, check_all_interactions, InteractionDiagnostic, Severity


@dataclass
class DomainLanguage:
    """A Domain Language — DomL = (E, A, O, N, C, I).

    Paper reference: Section 2.1 — "A Domain Language is a formal, closed,
    and modular specification of admissible meaning within a bounded domain."
    """

    name: str

    # E — finite set of entity symbols
    entities: set[EntityType] = field(default_factory=set)

    # A — typed attribute map: E → P(Attr)
    attributes: dict[EntityType, list[Attribute]] = field(default_factory=dict)

    # O — finite set of operation symbols
    operations: set[OperationType] = field(default_factory=set)

    # N — normative operator applications
    normative_rules: list[NormativeRule] = field(default_factory=list)

    # C — invariant predicates
    constraints: list[Constraint] = field(default_factory=list)

    # I — import declarations
    imports: set[ImportDecl] = field(default_factory=set)

    # Declared relations (used by validation and semantic worlds)
    relations: set[Relation] = field(default_factory=set)

    # -----------------------------------------------------------------------
    # Builder API
    # -----------------------------------------------------------------------

    def add_entity(self, name: str) -> EntityType:
        """Declare an entity type in this Domain Language."""
        entity = EntityType(name)
        self.entities.add(entity)
        return entity

    def add_attribute(
        self,
        entity: EntityType,
        name: str,
        value_type: type | None = None,
        optionality: Optionality = Optionality.REQUIRED,
    ) -> Attribute:
        """Declare a typed attribute on an entity."""
        attr = Attribute(name=name, entity=entity, value_type=value_type, optionality=optionality)
        self.attributes.setdefault(entity, []).append(attr)
        return attr

    def add_operation(self, name: str) -> OperationType:
        """Declare an admissible operation."""
        op = OperationType(name)
        self.operations.add(op)
        return op

    def add_relation(self, name: str, source: EntityType, target: EntityType) -> Relation:
        """Declare an admissible relation between entity types."""
        rel = Relation(name=name, source=source, target=target)
        self.relations.add(rel)
        return rel

    def add_normative_rule(
        self,
        operator: NormativeOp,
        element: EntityType | Attribute | OperationType | Relation,
        condition: object = None,
        description: str = "",
    ) -> NormativeRule:
        """Apply a normative operator to a target."""
        target = NormativeTarget(element=element, condition=condition, description=description)
        rule = NormativeRule(operator=operator, target=target)
        self.normative_rules.append(rule)
        return rule

    def must(self, element, **kwargs) -> NormativeRule:
        return self.add_normative_rule(NormativeOp.MUST, element, **kwargs)

    def must_not(self, element, **kwargs) -> NormativeRule:
        return self.add_normative_rule(NormativeOp.MUST_NOT, element, **kwargs)

    def should(self, element, **kwargs) -> NormativeRule:
        return self.add_normative_rule(NormativeOp.SHOULD, element, **kwargs)

    def should_not(self, element, **kwargs) -> NormativeRule:
        return self.add_normative_rule(NormativeOp.SHOULD_NOT, element, **kwargs)

    def may(self, element, **kwargs) -> NormativeRule:
        return self.add_normative_rule(NormativeOp.MAY, element, **kwargs)

    def add_constraint(
        self,
        name: str,
        description: str,
        predicate,
        references: frozenset | None = None,
    ) -> Constraint:
        """Declare an invariant predicate."""
        c = Constraint(
            name=name,
            description=description,
            predicate=predicate,
            references=references or frozenset(),
        )
        self.constraints.append(c)
        return c

    def add_import(self, target_name: str) -> ImportDecl:
        """Declare a dependency on another Domain Language."""
        imp = ImportDecl(target_name)
        self.imports.add(imp)
        return imp

    # -----------------------------------------------------------------------
    # Vocabulary
    # -----------------------------------------------------------------------

    def vocab(self) -> set:
        """Return Vocab(DomL) = E ∪ range(A) ∪ O.

        Paper reference: Section 2.1 — "The vocabulary of a Domain Language
        is Vocab(DomL) = E ∪ range(A) ∪ O"
        """
        v: set = set()
        v.update(self.entities)
        for attrs in self.attributes.values():
            v.update(attrs)
        v.update(self.operations)
        return v

    def get_attribute(self, entity: EntityType, attr_name: str) -> Attribute | None:
        """Look up an attribute by entity and name."""
        for attr in self.attributes.get(entity, []):
            if attr.name == attr_name:
                return attr
        return None

    # -----------------------------------------------------------------------
    # Internal coherence checks
    # -----------------------------------------------------------------------

    def check_normative_interactions(self) -> list[InteractionDiagnostic]:
        """Check all normative rules for interaction issues (Section 2.5)."""
        return check_all_interactions(self.normative_rules)

    def check_closure(self, resolved_imports: dict[str, DomainLanguage] | None = None) -> list[str]:
        """Check that every symbol in N, C, I is resolvable.

        Paper reference: Section 2.1 — "every symbol referenced in N, C, or I
        is resolvable within Vocab(DomL) or transitively through I"
        """
        errors: list[str] = []
        local_vocab = self.vocab()

        # Build extended vocab including imports
        extended_vocab = set(local_vocab)
        if resolved_imports is not None:
            for imp in self.imports:
                imported = resolved_imports.get(imp.target_name)
                if imported is None:
                    errors.append(f"Unresolved import: {imp.target_name}")
                else:
                    extended_vocab.update(imported.vocab())

        # Check normative rule targets reference known elements
        all_elements = extended_vocab | set(self.relations)
        for rule in self.normative_rules:
            if rule.target.element not in all_elements:
                errors.append(
                    f"Normative rule {rule} references unknown element: {rule.target.element}"
                )

        return errors

    def __repr__(self) -> str:
        return (
            f"DomainLanguage({self.name}: "
            f"{len(self.entities)} entities, "
            f"{sum(len(v) for v in self.attributes.values())} attributes, "
            f"{len(self.operations)} operations, "
            f"{len(self.normative_rules)} rules, "
            f"{len(self.constraints)} constraints, "
            f"{len(self.imports)} imports)"
        )
