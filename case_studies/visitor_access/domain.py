"""Visitor Access Control — Domain Language definitions.

Paper reference: Section 5.4 (Worked Example)

Two Domain Languages compose this domain:
- VisitorCore: entities, attributes, operations
- ZonePolicy: zone clearance rules, escort requirements (imports VisitorCore)
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dds.domain_language import DomainLanguage
from dds.domain_language_graph import DomainLanguageGraph, EdgeLabel
from dds.normative import NormativeOp
from dds.types import UNKNOWN, Optionality
from dds.validation import SemanticWorld


def build_visitor_core() -> DomainLanguage:
    """Build the VisitorCore Domain Language.

    Entities: Visitor, Host, VisitRecord
    Operations: CheckIn, CheckOut
    """
    lang = DomainLanguage(name="VisitorCore")

    # Entities (E)
    visitor = lang.add_entity("Visitor")
    host = lang.add_entity("Host")
    visit_record = lang.add_entity("VisitRecord")

    # Attributes (A)
    lang.add_attribute(visitor, "name", value_type=str)
    visitor_id_verified = lang.add_attribute(visitor, "idVerified", value_type=bool)
    lang.add_attribute(host, "department", value_type=str)
    lang.add_attribute(visit_record, "purpose", value_type=str)
    lang.add_attribute(
        visit_record, "escorted", value_type=bool,
        optionality=Optionality.UNKNOWN_ADMISSIBLE,
    )

    # Operations (O)
    lang.add_operation("CheckIn")
    lang.add_operation("CheckOut")

    # Relations
    vr_visitor = lang.add_relation("visitor", source=visit_record, target=visitor)
    vr_host = lang.add_relation("host", source=visit_record, target=host)

    # Normative rules (N) — from the security manual
    # "All visitors must present valid ID"
    lang.must(visitor_id_verified, description="Every visitor must have verified identity")

    # "Every visit must be linked to a host"
    lang.must(vr_host, description="Every visit record must reference a host")

    # Constraints (C)
    lang.add_constraint(
        name="vr_single_visitor",
        description="A VisitRecord must reference exactly one Visitor",
        predicate=lambda w: _check_single_relation(w, "visitor", visit_record),
        references=frozenset({visit_record, visitor}),
    )

    return lang


def build_zone_policy() -> DomainLanguage:
    """Build the ZonePolicy Domain Language.

    Imports VisitorCore. Adds Zone entity and clearance rules.
    """
    lang = DomainLanguage(name="ZonePolicy")
    lang.add_import("VisitorCore")

    # Entities
    zone = lang.add_entity("Zone")
    # Re-declare VisitRecord to add zone relation
    visit_record = lang.add_entity("VisitRecord")

    # Attributes
    lang.add_attribute(zone, "clearanceLevel", value_type=str)

    # Relations
    vr_zone = lang.add_relation("zone", source=visit_record, target=zone)

    # Normative rules
    # "Secure zones require escort at all times"
    lang.must_not(
        vr_zone,
        condition=_check_unescorted_secure,
        description="Unescorted access to secure zones is forbidden",
    )

    # "Badge return is expected at checkout"
    lang.should(
        visit_record,
        condition=_check_badge_return,
        description="Badge return at checkout is expected",
    )

    return lang


def build_domain() -> DomainLanguageGraph:
    """Build the complete Visitor Access Control domain.

    DomLG = ({VisitorCore, ZonePolicy}, {(ZonePolicy, VisitorCore)}, λ)
    where λ(ZonePolicy, VisitorCore) = imports
    """
    visitor_core = build_visitor_core()
    zone_policy = build_zone_policy()

    graph = DomainLanguageGraph()
    graph.add_language(visitor_core)
    graph.add_language(zone_policy)
    graph.add_edge("ZonePolicy", "VisitorCore", EdgeLabel.IMPORTS)

    return graph


# ---------------------------------------------------------------------------
# Constraint / condition helpers
# ---------------------------------------------------------------------------

def _check_single_relation(
    world: SemanticWorld,
    rel_name: str,
    source_type,
) -> bool:
    """Check that each element of source_type has exactly one relation of rel_name."""
    for elem in world.get_elements_by_type(source_type):
        count = sum(
            1 for r in world.relations
            if r.relation.name == rel_name and r.source_id == elem.identity
        )
        if count != 1:
            return False
    return True


def _check_unescorted_secure(world: SemanticWorld):
    """MUST NOT condition: unescorted access to secure zones.

    Returns list of violations if any, or False if none.
    """
    violations = []
    from dds.types import UNKNOWN as _UNKNOWN

    for elem in world.elements:
        if elem.entity_type.name == "VisitRecord":
            escorted = elem.attribute_values.get("escorted")
            # Find the zone for this visit record
            zone_id = None
            for r in world.relations:
                if r.relation.name == "zone" and r.source_id == elem.identity:
                    zone_id = r.target_id
                    break
            if zone_id:
                zone_elem = world.get_element_by_id(zone_id)
                if zone_elem and zone_elem.attribute_values.get("clearanceLevel") == "secure":
                    if escorted is False:
                        violations.append(
                            f"VisitRecord '{elem.identity}': unescorted access "
                            f"to secure zone '{zone_id}'"
                        )
    return violations if violations else False


def _check_badge_return(world: SemanticWorld):
    """SHOULD condition: badge return at checkout.

    Returns list of advisories if any, or False if none.
    """
    advisories = []
    for elem in world.elements:
        if elem.entity_type.name == "VisitRecord":
            badge = elem.attribute_values.get("badgeReturned")
            if badge is False:
                advisories.append(
                    f"VisitRecord '{elem.identity}': badge not returned at checkout"
                )
    return advisories if advisories else False
