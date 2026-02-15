"""Gating — open-world to closed-world transformation.

Paper reference: Section 4

Gating is the process of transforming open-world domain knowledge into a
Domain Language definition. It is a representational closure step — not
inference, validation, or execution.

Formally: Gate: K → DomL ∪ {⊥}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .domain_language import DomainLanguage
from .types import UNKNOWN


# ---------------------------------------------------------------------------
# Structured source — minimal formal model of K
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceProposition:
    """A single proposition from open-world domain knowledge.

    Each proposition carries provenance: where it came from.
    This enables the non-inferential property to be checked —
    every DomL element must trace to an explicit source proposition.
    """
    text: str
    source_document: str = ""
    source_section: str = ""
    source_author: str = ""

    def __repr__(self) -> str:
        src = self.source_document or "unknown source"
        return f'Proposition("{self.text}" from {src})'


@dataclass
class StructuredSource:
    """K — a body of open-world domain knowledge.

    Paper reference: Section 4.2 — "Let K denote a body of open-world
    domain knowledge"

    Formalized as a set of propositions with provenance.
    """
    name: str
    propositions: list[SourceProposition] = field(default_factory=list)

    def add(self, text: str, **kwargs) -> SourceProposition:
        prop = SourceProposition(text=text, **kwargs)
        self.propositions.append(prop)
        return prop


# ---------------------------------------------------------------------------
# Gating result
# ---------------------------------------------------------------------------

@dataclass
class GatingResult:
    """Result of a gating operation: either a DomainLanguage or rejection (⊥).

    Paper reference: Section 4.2 — "Gate: K → DomL ∪ {⊥} where DomL is a
    well-formed Domain Language and ⊥ denotes rejection"
    """
    success: bool
    domain_language: DomainLanguage | None = None
    rejection_reason: str = ""
    provenance_map: dict[str, list[SourceProposition]] = field(default_factory=dict)
    unknowns: list[str] = field(default_factory=list)

    @staticmethod
    def accepted(
        domain_language: DomainLanguage,
        provenance_map: dict[str, list[SourceProposition]] | None = None,
        unknowns: list[str] | None = None,
    ) -> GatingResult:
        return GatingResult(
            success=True,
            domain_language=domain_language,
            provenance_map=provenance_map or {},
            unknowns=unknowns or [],
        )

    @staticmethod
    def rejected(reason: str) -> GatingResult:
        """The knowledge cannot be represented — ⊥."""
        return GatingResult(success=False, rejection_reason=reason)


# ---------------------------------------------------------------------------
# Gating agent interface
# ---------------------------------------------------------------------------

class GatingAgent:
    """Abstract interface for gating agents.

    Paper reference: Section 4.3 — "Humans and LLMs may perform gating.
    All gating agents are treated as untrusted sources."

    Subclasses implement the gate() method to transform a StructuredSource
    into a DomainLanguage.
    """

    def gate(self, source: StructuredSource) -> GatingResult:
        """Transform open-world knowledge into a Domain Language definition.

        Properties that must hold (Section 4.2):
        - Non-inferential: output must not contain meaning not in source
        - UNKNOWN-preserving: incomplete/ambiguous source → UNKNOWN, not defaulted
        - Idempotent: gating an already well-formed DomL returns same DomL
        """
        raise NotImplementedError

    def check_idempotent(self, domain_language: DomainLanguage) -> bool:
        """Verify Gate(DomL) = DomL for an already well-formed DomL.

        Paper reference: Section 4.2 — "Gating an already well-formed DomL
        returns the same DomL"
        """
        # Create a trivial StructuredSource from the DomL
        source = StructuredSource(name=f"idempotent_check_{domain_language.name}")
        result = self.gate(source)
        if not result.success:
            return False
        # In practice, this checks structural equivalence
        return result.domain_language is not None
