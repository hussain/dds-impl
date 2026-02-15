"""Prescription Validation — End-to-end DDS demonstration.

Case Study 2: Tiny but challenging healthcare domain.

Demonstrates three DDS layers:

  LAYER 1 — DDS Self-QC
    Gating: K (clinical guidelines) -> Gate -> DomL
    Self-validation: domain definition coherence checks

  LAYER 2 — DDS Admissibility
    Structural admissibility of semantic worlds under the domain.
    Checks vocabulary closure, relation types, completeness, provenance.

  LAYER 3 — Execution (NOT part of DDS)
    Consuming DDS-defined normative rules to evaluate concrete records.
    Evaluates MUST_NOT violations, SHOULD/SHOULD_NOT advisories.

The scenarios demonstrate how layers compose:
  - Some scenarios fail at Layer 2 (inadmissible) and never reach Layer 3
  - Some pass Layer 2 but fail at Layer 3 (rule violation)
  - Some pass both layers but surface advisories (SHOULD/SHOULD_NOT)
This is the clean DDS layering the paper describes.
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

from .domain import build_domain
from .gating_example import PrescriptionGatingAgent, create_clinical_guidelines_source


def print_header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_layer(number: int, name: str, scope: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  LAYER {number}: {name}")
    print(f"  Scope: {scope}")
    print(f"{'─' * 60}")


def _get_relations(graph: DomainLanguageGraph):
    """Helper: collect all relations from the graph."""
    rels = {}
    for lang in graph.languages.values():
        for r in lang.relations:
            rels[r.name] = r
    return rels


# ===========================================================================
# LAYER 1: DDS Self-QC
# ===========================================================================

def run_gating_demo():
    """Demonstrate the gating step for clinical guidelines."""
    print_header("LAYER 1: DDS Self-QC")
    print_layer(1, "DDS Self-QC", "Domain definition coherence")

    print("\n  Step 1a: Gating (clinical guidelines to Domain Language)")
    print("  " + "-" * 46)

    source = create_clinical_guidelines_source()
    print(f"\n  Source: {source.name}")
    print(f"  Propositions ({len(source.propositions)}):")
    for prop in source.propositions:
        print(f"    - \"{prop.text}\"")
        print(f"      [from: {prop.source_section}]")

    agent = PrescriptionGatingAgent()
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


# ===========================================================================
# LAYER 2 + 3: Scenarios
# ===========================================================================

def _build_world_clean(graph):
    """Build a clean prescription world (all checks pass)."""
    rels = _get_relations(graph)
    world = SemanticWorld()

    world.add_element(
        EntityType("Patient"), "pat1",
        {"name": "Jane Smith", "idVerified": True,
         "pregnancyStatus": "not_pregnant", "renalFunction": "normal"},
        provenance="admission_record",
    )
    world.add_element(
        EntityType("Drug"), "drug1",
        {"name": "Amoxicillin", "activeIngredient": "amoxicillin",
         "schedule": "Rx", "isGeneric": True, "isBrandName": False,
         "isTeratogenic": False, "isNephrotoxic": False},
        provenance="formulary",
    )
    world.add_element(
        EntityType("Prescription"), "rx1",
        {"prescriberName": "Dr. Lee", "isSigned": True,
         "dosage": 500.0, "dosageUnit": "mg"},
        provenance="prescription_form",
    )
    world.add_relation(rels["forPatient"], "rx1", "pat1", provenance="prescription_form")
    world.add_relation(rels["prescribesDrug"], "rx1", "drug1", provenance="prescription_form")

    return world


def _build_world_contraindicated(graph):
    """Build a world with known contraindication (MUST NOT violation)."""
    rels = _get_relations(graph)
    world = SemanticWorld()

    world.add_element(
        EntityType("Patient"), "pat1",
        {"name": "Ahmed Hassan", "idVerified": True,
         "pregnancyStatus": "not_applicable", "renalFunction": "normal"},
        provenance="admission_record",
    )
    world.add_element(
        EntityType("Drug"), "drug1",
        {"name": "Methotrexate", "activeIngredient": "methotrexate",
         "schedule": "Rx", "isGeneric": True, "isBrandName": False,
         "isTeratogenic": True, "isNephrotoxic": True},
        provenance="formulary",
    )
    world.add_element(
        EntityType("Prescription"), "rx1",
        {"prescriberName": "Dr. Chen", "isSigned": True,
         "dosage": 15.0, "dosageUnit": "mg"},
        provenance="prescription_form",
    )
    world.add_element(
        EntityType("Contraindication"), "ci1",
        {"reason": "Severe hepatic impairment", "severity": "absolute"},
        provenance="medical_record",
    )
    world.add_relation(rels["forPatient"], "rx1", "pat1", provenance="prescription_form")
    world.add_relation(rels["prescribesDrug"], "rx1", "drug1", provenance="prescription_form")
    world.add_relation(rels["contraindicatesDrug"], "ci1", "drug1", provenance="medical_record")
    world.add_relation(rels["appliesToPatient"], "ci1", "pat1", provenance="medical_record")

    return world


def _build_world_unknown_allergy(graph):
    """Build a world with unknown allergy status (UNKNOWN surfaced)."""
    rels = _get_relations(graph)
    world = SemanticWorld()

    world.add_element(
        EntityType("Patient"), "pat1",
        {"name": "Maria Garcia", "idVerified": True,
         "pregnancyStatus": "not_pregnant", "renalFunction": "normal"},
        provenance="admission_record",
    )
    world.add_element(
        EntityType("Drug"), "drug1",
        {"name": "Penicillin V", "activeIngredient": "phenoxymethylpenicillin",
         "schedule": "Rx", "isGeneric": True, "isBrandName": False},
        provenance="formulary",
    )
    world.add_element(
        EntityType("Prescription"), "rx1",
        {"prescriberName": "Dr. Patel", "isSigned": True,
         "dosage": 250.0, "dosageUnit": "mg"},
        provenance="prescription_form",
    )
    world.add_element(
        EntityType("AllergyRecord"), "ar1",
        {"allergen": "penicillin", "status": UNKNOWN},
        provenance="admission_record",
    )
    world.add_relation(rels["forPatient"], "rx1", "pat1", provenance="prescription_form")
    world.add_relation(rels["prescribesDrug"], "rx1", "drug1", provenance="prescription_form")
    world.add_relation(rels["allergyOf"], "ar1", "pat1", provenance="admission_record")

    return world


def _build_world_teratogenic(graph):
    """Build a world with teratogenic drug + unknown pregnancy."""
    rels = _get_relations(graph)
    world = SemanticWorld()

    world.add_element(
        EntityType("Patient"), "pat1",
        {"name": "Sara Kim", "idVerified": True,
         "pregnancyStatus": UNKNOWN, "renalFunction": "normal"},
        provenance="admission_record",
    )
    world.add_element(
        EntityType("Drug"), "drug1",
        {"name": "Isotretinoin", "activeIngredient": "isotretinoin",
         "schedule": "Rx", "isGeneric": False, "isBrandName": True,
         "isTeratogenic": True, "isNephrotoxic": False,
         "genericEquivalentExists": True},
        provenance="formulary",
    )
    world.add_element(
        EntityType("Prescription"), "rx1",
        {"prescriberName": "Dr. Wilson", "isSigned": True,
         "dosage": 20.0, "dosageUnit": "mg"},
        provenance="prescription_form",
    )
    world.add_relation(rels["forPatient"], "rx1", "pat1", provenance="prescription_form")
    world.add_relation(rels["prescribesDrug"], "rx1", "drug1", provenance="prescription_form")

    return world


def _build_world_vocab_failure(graph):
    """Build a world with unknown entity type (vocabulary closure failure)."""
    rels = _get_relations(graph)
    world = SemanticWorld()

    world.add_element(
        EntityType("Patient"), "pat1",
        {"name": "Tom Brown", "idVerified": True},
        provenance="admission_record",
    )
    world.add_element(
        EntityType("Supplement"), "sup1",  # NOT in any Domain Language
        {"name": "Vitamin D3", "dosage": 5000, "unit": "IU"},
        provenance="patient_request",
    )

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
    print("  DDS Reference Implementation — Case Study 2")
    print("  Prescription Validation")
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

    # -----------------------------------------------------------------------
    # LAYERS 2 + 3: Scenarios
    # -----------------------------------------------------------------------
    print_header("LAYERS 2+3: Scenarios (Admissibility + Execution)")

    # Scenario A: Clean prescription — passes both layers
    run_scenario(
        "Scenario A: Clean Prescription (passes both layers)",
        graph,
        _build_world_clean(graph),
        note="All entity types in vocabulary, all MUST attributes satisfied.\n"
             "  Rule evaluation finds no violations or advisories.",
    )

    # Scenario B: Known contraindication — admissible, but MUST_NOT violation
    run_scenario(
        "Scenario B: Known Contraindication (MUST NOT violation)",
        graph,
        _build_world_contraindicated(graph),
        note="Layer 2 (DDS) confirms structural admissibility.\n"
             "  Layer 3 (Execution) evaluates the conditional MUST_NOT rule\n"
             "  and detects the contraindication. This is the key layering:\n"
             "  DDS validates what the domain allows; execution checks rules.",
    )

    # Scenario C: Unknown allergy — admissible with UNKNOWN gap
    run_scenario(
        "Scenario C: Unknown Allergy Status (UNKNOWN surfaced)",
        graph,
        _build_world_unknown_allergy(graph),
        note="The UNKNOWN allergy status is surfaced by DDS admissibility\n"
             "  (Layer 2, condition 3) as an explicit gap. DDS does NOT infer\n"
             "  whether the patient is allergic. The UNKNOWN is preserved as\n"
             "  a first-class gap for clinical judgment. The system does NOT\n"
             "  default to 'no allergy' or 'has allergy'.",
    )

    # Scenario D: Teratogenic drug + unknown pregnancy — advisories surfaced
    run_scenario(
        "Scenario D: Teratogenic Drug + Unknown Pregnancy (advisories)",
        graph,
        _build_world_teratogenic(graph),
        note="This scenario surfaces TWO advisories from Layer 3:\n"
             "  1. SHOULD: pregnancy status is UNKNOWN for teratogenic drug\n"
             "  2. SHOULD_NOT: brand-name prescribed when generic exists\n"
             "  Neither advisory causes validation failure — they are surfaced\n"
             "  for clinical decision-making. DDS admissibility (Layer 2)\n"
             "  already flagged pregnancyStatus as an UNKNOWN gap.",
    )

    # Scenario E: Vocabulary closure failure — fails at Layer 2
    run_scenario(
        "Scenario E: Vocabulary Closure Failure (inadmissible)",
        graph,
        _build_world_vocab_failure(graph),
        note="'Supplement' is not in Vocab(DomLG). DDS rejects the world\n"
             "  at Layer 2 (vocabulary closure). The system does NOT silently\n"
             "  accept unknown entity types. Rule evaluation (Layer 3) is\n"
             "  SKIPPED because the world is inadmissible.",
    )

    print(f"\n{'=' * 60}")
    print("  Case Study 2 Complete")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
