"""Core types for DDS — maps directly to the paper's formalization.

Paper reference: Section 2.1 (Domain Language tuple components)

DomL = (E, A, O, N, I) where:
  E = finite set of entity symbols
  A = typed attribute map
  O = finite set of operation symbols
  N = normative rules: r = (modality, target, constraint_L, condition_L, override_ref)
  I = import declarations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


# ---------------------------------------------------------------------------
# UNKNOWN — first-class semantic marker (not None, not Optional)
# ---------------------------------------------------------------------------

class _UnknownType:
    """Sentinel representing explicitly unknown domain knowledge.

    Paper reference: Section 2.2 — "Absence is represented explicitly as
    UNKNOWN or as a validation error."
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNKNOWN"

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _UnknownType)

    def __hash__(self) -> int:
        return hash("UNKNOWN")


UNKNOWN = _UnknownType()


# ---------------------------------------------------------------------------
# Optionality — attribute presence requirements
# ---------------------------------------------------------------------------

class Optionality(Enum):
    """How an attribute's presence is constrained."""
    REQUIRED = "required"
    OPTIONAL = "optional"
    UNKNOWN_ADMISSIBLE = "unknown_admissible"


# ---------------------------------------------------------------------------
# EntityType — element of E
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EntityType:
    """A named entity type admitted by the domain.

    Paper reference: Section 2.1 — "E is a finite set of entity symbols
    (the domain vocabulary)"
    """
    name: str

    def __repr__(self) -> str:
        return f"Entity({self.name})"


# ---------------------------------------------------------------------------
# Attribute — element of A(e) for some entity e
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Attribute:
    """A typed property of an entity.

    Paper reference: Section 2.1 — "A: E → P(Attr) is a typed attribute map,
    where each attribute carries a type and an optionality flag"
    """
    name: str
    entity: EntityType
    value_type: type | None = None
    optionality: Optionality = Optionality.REQUIRED

    def __repr__(self) -> str:
        opt = f", {self.optionality.value}" if self.optionality != Optionality.REQUIRED else ""
        return f"Attr({self.entity.name}.{self.name}{opt})"


# ---------------------------------------------------------------------------
# OperationType — element of O
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OperationType:
    """An admissible transition or event.

    Paper reference: Section 2.1 — "O is a finite set of operation symbols
    representing admissible transitions or events"
    """
    name: str

    def __repr__(self) -> str:
        return f"Op({self.name})"


# ---------------------------------------------------------------------------
# Relation — declared relation between entity types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Relation:
    """A declared, admissible relation between entity types.

    Not part of the DomL tuple directly, but used in constraints and
    in the semantic world W = (S, R).
    """
    name: str
    source: EntityType
    target: EntityType

    def __repr__(self) -> str:
        return f"Rel({self.source.name} --{self.name}--> {self.target.name})"


# ---------------------------------------------------------------------------
# NormativeTarget — what a normative operator applies to
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NormativeTarget:
    """The target of a normative operator application.

    Can target an entity, attribute, operation, relation, or a conditional
    expression (predicate that must hold for the rule to fire).
    """
    element: EntityType | Attribute | OperationType | Relation
    condition: Callable[..., bool] | None = field(default=None, hash=False, compare=False)
    description: str = ""

    def __repr__(self) -> str:
        cond = f" WHERE {self.description}" if self.description else ""
        return f"Target({self.element}{cond})"


# ---------------------------------------------------------------------------
# Constraint — element of C
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Constraint:
    """An invariant predicate over entities, attributes, and operations.

    Paper reference: Section 2.1 — "C is a finite set of invariant predicates
    over E, A, and O"

    The predicate is a callable that receives a semantic world and returns
    True (satisfied) or False (violated). The description is for human
    readability and validation reports.
    """
    name: str
    description: str
    predicate: Callable[..., bool] = field(hash=False, compare=False)
    references: frozenset[EntityType | Attribute | OperationType | Relation] = field(
        default_factory=frozenset
    )

    def __repr__(self) -> str:
        return f"Constraint({self.name})"


# ---------------------------------------------------------------------------
# ImportDecl — element of I
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImportDecl:
    """A declaration that this Domain Language depends on another.

    Paper reference: Section 2.1 — "I is a set of import declarations,
    each referencing another Domain Language by identity"
    """
    target_name: str

    def __repr__(self) -> str:
        return f"Import({self.target_name})"
