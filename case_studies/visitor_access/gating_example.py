"""Visitor Access Control — Gating example.

Paper reference: Section 4 (Gating), Section 5.4 (Worked Example)

Demonstrates transforming the building's security manual (open-world knowledge)
into Domain Language definitions through explicit gating.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dds.gating import GatingAgent, GatingResult, SourceProposition, StructuredSource
from .domain import build_visitor_core, build_zone_policy


class VisitorAccessGatingAgent(GatingAgent):
    """Gating agent for the building security manual.

    Paper reference: Section 5.4 — "A domain analyst (the gating agent,
    treated as untrusted) translates this into the Domain Language"
    """

    def gate(self, source: StructuredSource) -> GatingResult:
        """Transform security manual propositions into Domain Language definitions.

        The security manual states:
        1. "All visitors must present valid ID"
        2. "Every visit must be linked to a host employee"
        3. "Secure zones require escort at all times"
        4. "Badge return is expected at checkout"

        The manual does NOT address restricted zones — this is surfaced as UNKNOWN.
        """
        provenance_map: dict[str, list[SourceProposition]] = {}
        unknowns: list[str] = []

        # Map each proposition to DomL elements
        for prop in source.propositions:
            text = prop.text.lower()

            if "valid id" in text or "present id" in text:
                provenance_map.setdefault("MUST(Visitor.idVerified)", []).append(prop)

            elif "linked to a host" in text or "host employee" in text:
                provenance_map.setdefault("MUST(VisitRecord→Host)", []).append(prop)

            elif "escort" in text and "secure" in text:
                provenance_map.setdefault(
                    "MUST_NOT(secure ∧ ¬escorted)", []
                ).append(prop)

            elif "badge return" in text:
                provenance_map.setdefault(
                    "SHOULD(CheckOut→badgeReturned)", []
                ).append(prop)

        # UNKNOWN-preserving: the manual does not address restricted zones
        unknowns.append(
            "Escort policy for restricted zones: source does not specify. "
            "VisitRecord.escorted is UNKNOWN-admissible for non-secure zones."
        )

        # Build the Domain Languages
        visitor_core = build_visitor_core()
        zone_policy = build_zone_policy()

        return GatingResult.accepted(
            domain_language=visitor_core,  # primary output
            provenance_map=provenance_map,
            unknowns=unknowns,
        )


def create_security_manual_source() -> StructuredSource:
    """Create the structured source K from the building's security manual."""
    source = StructuredSource(name="Building Security Manual v3.2")

    source.add(
        "All visitors must present valid ID.",
        source_document="Building Security Manual v3.2",
        source_section="Section 4.1: Visitor Identification",
    )
    source.add(
        "Every visit must be linked to a host employee.",
        source_document="Building Security Manual v3.2",
        source_section="Section 4.2: Host Requirements",
    )
    source.add(
        "Secure zones require escort at all times.",
        source_document="Building Security Manual v3.2",
        source_section="Section 5.1: Zone Access Control",
    )
    source.add(
        "Badge return is expected at checkout.",
        source_document="Building Security Manual v3.2",
        source_section="Section 6.3: Checkout Procedures",
    )

    return source
