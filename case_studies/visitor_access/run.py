"""Visitor Access Control — End-to-end DDS demonstration.

Paper reference: Section 5.4

Demonstrates three DDS layers plus SHACL bridge:

  LAYER 1 — DDS Self-QC
    Gating: K (security manual) -> Gate -> DomL
    Self-validation: domain definition coherence checks

  LAYER 2 — DDS Admissibility
    Structural admissibility of semantic worlds under the domain.
    Checks vocabulary closure, relation types, completeness, provenance.

  LAYER 3 — Execution (NOT part of DDS)
    Consuming DDS-defined normative rules to evaluate concrete records.
    Evaluates MUST_NOT violations, SHOULD/SHOULD_NOT advisories.

  SHACL Bridge — DDS→SHACL complementarity
    Translates DDS domain → SHACL shapes, world → RDF, validates via pySHACL.
    Shows where DDS and SHACL agree and where DDS provides coverage SHACL lacks.

Each scenario shows how the layers compose: admissibility is checked
first (DDS scope), and only if admissible does rule evaluation proceed
(execution scope). This demonstrates the clean separation between
what DDS guarantees and what an execution framework adds.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dds.domain_language import DomainLanguage
from dds.domain_language_graph import DomainLanguageGraph, EdgeLabel
from dds.normative import NormativeOp
from dds.types import UNKNOWN, EntityType, Optionality
from dds.validation import (
    SemanticWorld,
    self_validate,
    check_admissibility,
    evaluate_rules,
)
from dds.shacl_bridge import shacl_validate

from .domain import build_domain, build_visitor_core, build_zone_policy
from .gating_example import VisitorAccessGatingAgent, create_security_manual_source


def print_header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_layer(number: int, name: str, scope: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  LAYER {number}: {name}")
    print(f"  Scope: {scope}")
    print(f"{'─' * 60}")


# ===========================================================================
# LAYER 1: DDS Self-QC
# ===========================================================================

def run_gating_demo():
    """Demonstrate the gating step: K -> Gate -> DomL."""
    print_header("LAYER 1: DDS Self-QC")
    print_layer(1, "DDS Self-QC", "Domain definition coherence")

    print("\n  Step 1a: Gating (open-world to closed-world)")
    print("  " + "-" * 46)

    source = create_security_manual_source()
    print(f"\n  Source: {source.name}")
    print(f"  Propositions ({len(source.propositions)}):")
    for prop in source.propositions:
        print(f"    - \"{prop.text}\"")
        print(f"      [from: {prop.source_section}]")

    agent = VisitorAccessGatingAgent()
    result = agent.gate(source)

    print(f"\n  Gating result: {'ACCEPTED' if result.success else 'REJECTED'}")

    if result.provenance_map:
        print("\n  Provenance map (source -> DomL element):")
        for doml_element, props in result.provenance_map.items():
            print(f"    {doml_element}")
            for p in props:
                print(f"      <- \"{p.text}\"")

    if result.unknowns:
        print("\n  UNKNOWN gaps surfaced by gating:")
        for u in result.unknowns:
            print(f"    - {u}")


def run_self_validation(graph: DomainLanguageGraph):
    """Demonstrate DDS self-validation."""
    print(f"\n  Step 1b: Self-Validation")
    print("  " + "-" * 46)
    result = self_validate(graph)
    for line in result.summary().split("\n"):
        print(f"  {line}")
    return result


def run_self_validation_failure():
    """Demonstrate self-validation catching contradictory normative operators."""
    print(f"\n  Step 1c: Self-Validation Failure (Contradictory Rules)")
    print("  " + "-" * 46)

    lang = DomainLanguage(name="BrokenPolicy")
    visitor = lang.add_entity("Visitor")
    id_attr = lang.add_attribute(visitor, "idVerified", value_type=bool)
    lang.must(id_attr, description="ID must be verified")
    lang.must_not(id_attr, description="ID must NOT be verified")

    graph = DomainLanguageGraph()
    graph.add_language(lang)

    result = self_validate(graph)
    for line in result.summary().split("\n"):
        print(f"  {line}")

    print("\n  NOTE: DDS Self-QC detects contradictions in the domain")
    print("  definition BEFORE any records are evaluated. This is a")
    print("  property of the domain, not of any specific record.")


# ===========================================================================
# LAYER 2 + 3: Scenarios
# ===========================================================================

def _build_world_valid(graph):
    """Build a valid semantic world."""
    vc = graph.languages["VisitorCore"]
    zp = graph.languages["ZonePolicy"]

    world = SemanticWorld()
    world.add_element(EntityType("Visitor"), "v1",
                      {"name": "A. Karim", "idVerified": True}, provenance="input")
    world.add_element(EntityType("Host"), "h1",
                      {"department": "Engineering"}, provenance="input")
    world.add_element(EntityType("Zone"), "z1",
                      {"clearanceLevel": "public"}, provenance="input")
    world.add_element(EntityType("VisitRecord"), "vr1",
                      {"purpose": "meeting", "escorted": True}, provenance="input")

    vr_visitor = [r for r in vc.relations if r.name == "visitor"][0]
    vr_host = [r for r in vc.relations if r.name == "host"][0]
    vr_zone = [r for r in zp.relations if r.name == "zone"][0]
    world.add_relation(vr_visitor, "vr1", "v1", provenance="input")
    world.add_relation(vr_host, "vr1", "h1", provenance="input")
    world.add_relation(vr_zone, "vr1", "z1", provenance="input")

    return world


def _build_world_unknown_escort(graph):
    """Build a world with UNKNOWN escort status."""
    vc = graph.languages["VisitorCore"]
    zp = graph.languages["ZonePolicy"]

    world = SemanticWorld()
    world.add_element(EntityType("Visitor"), "v1",
                      {"name": "S. Noor", "idVerified": True}, provenance="input")
    world.add_element(EntityType("Host"), "h1",
                      {"department": "Legal"}, provenance="input")
    world.add_element(EntityType("Zone"), "z1",
                      {"clearanceLevel": "restricted"}, provenance="input")
    world.add_element(EntityType("VisitRecord"), "vr1",
                      {"purpose": "meeting", "escorted": UNKNOWN}, provenance="input")

    vr_visitor = [r for r in vc.relations if r.name == "visitor"][0]
    vr_host = [r for r in vc.relations if r.name == "host"][0]
    vr_zone = [r for r in zp.relations if r.name == "zone"][0]
    world.add_relation(vr_visitor, "vr1", "v1", provenance="input")
    world.add_relation(vr_host, "vr1", "h1", provenance="input")
    world.add_relation(vr_zone, "vr1", "z1", provenance="input")

    return world


def _build_world_unescorted_secure(graph):
    """Build a world with unescorted access to secure zone."""
    vc = graph.languages["VisitorCore"]
    zp = graph.languages["ZonePolicy"]

    world = SemanticWorld()
    world.add_element(EntityType("Visitor"), "v1",
                      {"name": "R. Fahed", "idVerified": True}, provenance="input")
    world.add_element(EntityType("Host"), "h1",
                      {"department": "Engineering"}, provenance="input")
    world.add_element(EntityType("Zone"), "z2",
                      {"clearanceLevel": "secure"}, provenance="input")
    world.add_element(EntityType("VisitRecord"), "vr1",
                      {"purpose": "maintenance", "escorted": False}, provenance="input")

    vr_visitor = [r for r in vc.relations if r.name == "visitor"][0]
    vr_host = [r for r in vc.relations if r.name == "host"][0]
    vr_zone = [r for r in zp.relations if r.name == "zone"][0]
    world.add_relation(vr_visitor, "vr1", "v1", provenance="input")
    world.add_relation(vr_host, "vr1", "h1", provenance="input")
    world.add_relation(vr_zone, "vr1", "z2", provenance="input")

    return world


def run_scenario(
    title: str,
    graph: DomainLanguageGraph,
    world: SemanticWorld,
    note: str = "",
):
    """Run a scenario showing Layer 2 (admissibility) then Layer 3 (rules)."""
    print(f"\n  {title}")
    print("  " + "-" * 46)

    # Layer 2: DDS Admissibility
    admissibility = check_admissibility(graph, world)
    print(f"\n  Layer 2 (DDS Admissibility):")
    for line in admissibility.summary().split("\n"):
        print(f"    {line}")

    # Layer 3: Execution (only if admissible)
    if admissibility.is_admissible:
        rules = evaluate_rules(graph, world)
        print(f"\n  Layer 3 (Execution — rule evaluation):")
        for line in rules.summary().split("\n"):
            print(f"    {line}")
    else:
        print(f"\n  Layer 3 (Execution): SKIPPED")
        print(f"    World is not admissible — rule evaluation does not proceed.")
        print(f"    DDS acts as a gatekeeper: inadmissible worlds are rejected")
        print(f"    before any domain rules are evaluated.")

    # SHACL Bridge: DDS→SHACL complementarity
    shacl_result = shacl_validate(graph, world)
    print(f"\n  SHACL Bridge (DDS→SHACL validation):")
    for line in shacl_result.summary().split("\n"):
        print(f"    {line}")

    # Highlight DDS/SHACL agreement or divergence
    if admissibility.is_admissible and shacl_result.conforms:
        print(f"    DDS and SHACL agree: world is valid.")
    elif not admissibility.is_admissible and not shacl_result.conforms:
        print(f"    DDS and SHACL agree: world has issues.")
    elif admissibility.is_admissible and not shacl_result.conforms:
        print(f"    DIVERGENCE: DDS admits (with UNKNOWN gaps), SHACL flags missing values.")
        print(f"    This shows DDS's UNKNOWN semantics — gaps are admissible but explicit.")
    elif not admissibility.is_admissible and shacl_result.conforms:
        print(f"    DIVERGENCE: DDS rejects (e.g., vocabulary closure), SHACL has no shape to check.")
        print(f"    This shows DDS's vocabulary closure — SHACL only validates known shapes.")

    if note:
        print(f"\n  NOTE: {note}")


def main():
    print("=" * 60)
    print("  DDS Reference Implementation — Case Study 1")
    print("  Visitor Access Control")
    print("=" * 60)

    # -----------------------------------------------------------------------
    # LAYER 1: DDS Self-QC
    # -----------------------------------------------------------------------
    run_gating_demo()

    graph = build_domain()
    print(f"\n  Domain: {graph}")
    for name, lang in graph.languages.items():
        print(f"    {lang}")
    run_self_validation(graph)
    run_self_validation_failure()

    # -----------------------------------------------------------------------
    # LAYERS 2 + 3: Scenarios
    # -----------------------------------------------------------------------
    print_header("LAYERS 2+3: Scenarios (Admissibility + Execution)")

    # Scenario A: Valid world — passes both layers
    run_scenario(
        "Scenario A: Valid World (passes both layers)",
        graph,
        _build_world_valid(graph),
        note="All entity types in vocabulary, all MUST attributes satisfied,\n"
             "  all relations properly typed. Rule evaluation finds no violations.",
    )

    # Scenario B: UNKNOWN escort — admissible with gap, rules pass
    run_scenario(
        "Scenario B: UNKNOWN Escort Status (admissible with gap)",
        graph,
        _build_world_unknown_escort(graph),
        note="The UNKNOWN escort status is surfaced by DDS admissibility\n"
             "  (Layer 2, condition 3) as an explicit gap. DDS does NOT infer\n"
             "  whether the visitor is escorted — the UNKNOWN is preserved.\n"
             "  Rule evaluation (Layer 3) proceeds because the world is admissible.",
    )

    # Scenario C: Unescorted secure zone — admissible, but rule violation
    run_scenario(
        "Scenario C: Unescorted Secure Zone (MUST NOT violation)",
        graph,
        _build_world_unescorted_secure(graph),
        note="Layer 2 (DDS) confirms the world is structurally admissible.\n"
             "  Layer 3 (Execution) then evaluates the MUST_NOT rule and finds\n"
             "  a violation: unescorted access to a secure zone. This shows the\n"
             "  layering: DDS validates structure, execution evaluates rules.",
    )

    print(f"\n{'=' * 60}")
    print("  Case Study 1 Complete")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
