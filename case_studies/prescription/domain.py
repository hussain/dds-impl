"""Prescription Validation — Domain Language definitions.

Case Study 2: A tiny but challenging healthcare domain.

Two Domain Languages compose this domain:
- Formulary: drugs, dosage forms, therapeutic classes
- PatientSafety: patients, prescriptions, contraindications (imports Formulary)

This domain exercises every DDS feature:
- All five normative operators (MUST, MUST NOT, SHOULD, SHOULD NOT, MAY)
- Genuine UNKNOWN pressure (allergy status, pregnancy status)
- Multi-DomL composition via DomLG
- Safety-critical constraints
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dds.domain_language import DomainLanguage
from dds.domain_language_graph import DomainLanguageGraph, EdgeLabel
from dds.normative import NormativeOp
from dds.types import UNKNOWN, EntityType, Optionality
from dds.validation import SemanticWorld


def build_formulary() -> DomainLanguage:
    """Build the Formulary Domain Language.

    Defines admissible drugs, dosage forms, and therapeutic classes.
    This is the pharmacopeia — what drugs exist and their properties.
    """
    lang = DomainLanguage(name="Formulary")

    # Entities
    drug = lang.add_entity("Drug")
    dosage_form = lang.add_entity("DosageForm")
    therapeutic_class = lang.add_entity("TherapeuticClass")

    # Attributes
    lang.add_attribute(drug, "name", value_type=str)
    lang.add_attribute(drug, "activeIngredient", value_type=str)
    drug_schedule = lang.add_attribute(drug, "schedule", value_type=str)
    lang.add_attribute(drug, "isGeneric", value_type=bool)
    lang.add_attribute(drug, "isBrandName", value_type=bool)
    lang.add_attribute(drug, "isTeratogenic", value_type=bool,
                       optionality=Optionality.OPTIONAL)
    lang.add_attribute(drug, "isNephrotoxic", value_type=bool,
                       optionality=Optionality.OPTIONAL)
    lang.add_attribute(drug, "genericEquivalentExists", value_type=bool,
                       optionality=Optionality.OPTIONAL)

    lang.add_attribute(dosage_form, "form", value_type=str)
    lang.add_attribute(dosage_form, "maxDailyDose", value_type=float)
    lang.add_attribute(dosage_form, "unit", value_type=str)

    lang.add_attribute(therapeutic_class, "name", value_type=str)

    # Relations
    lang.add_relation("hasDosageForm", source=drug, target=dosage_form)
    lang.add_relation("belongsToClass", source=drug, target=therapeutic_class)

    # Normative: drug must have a name and active ingredient
    drug_name = lang.get_attribute(drug, "name")
    drug_ingredient = lang.get_attribute(drug, "activeIngredient")
    lang.must(drug_name, description="Every drug must have a name")
    lang.must(drug_ingredient, description="Every drug must have an active ingredient")

    return lang


def build_patient_safety() -> DomainLanguage:
    """Build the PatientSafety Domain Language.

    Defines patients, prescriptions, contraindications, and safety rules.
    Imports Formulary for drug references.
    """
    lang = DomainLanguage(name="PatientSafety")
    lang.add_import("Formulary")

    # Entities
    patient = lang.add_entity("Patient")
    prescription = lang.add_entity("Prescription")
    contraindication = lang.add_entity("Contraindication")
    allergy_record = lang.add_entity("AllergyRecord")
    drug = lang.add_entity("Drug")  # re-declared for cross-language relations

    # Patient attributes
    lang.add_attribute(patient, "name", value_type=str)
    patient_id_verified = lang.add_attribute(patient, "idVerified", value_type=bool)
    lang.add_attribute(patient, "pregnancyStatus", value_type=str,
                       optionality=Optionality.UNKNOWN_ADMISSIBLE)
    lang.add_attribute(patient, "renalFunction", value_type=str,
                       optionality=Optionality.UNKNOWN_ADMISSIBLE)

    # Prescription attributes
    lang.add_attribute(prescription, "prescriberName", value_type=str)
    rx_signed = lang.add_attribute(prescription, "isSigned", value_type=bool)
    lang.add_attribute(prescription, "dosage", value_type=float)
    lang.add_attribute(prescription, "dosageUnit", value_type=str)
    lang.add_attribute(prescription, "isVerbal", value_type=bool,
                       optionality=Optionality.OPTIONAL)
    lang.add_attribute(prescription, "isEmergency", value_type=bool,
                       optionality=Optionality.OPTIONAL)

    # Contraindication attributes
    lang.add_attribute(contraindication, "reason", value_type=str)
    lang.add_attribute(contraindication, "severity", value_type=str)

    # AllergyRecord attributes
    lang.add_attribute(allergy_record, "allergen", value_type=str)
    lang.add_attribute(allergy_record, "status", value_type=str,
                       optionality=Optionality.UNKNOWN_ADMISSIBLE)

    # Relations
    rx_patient = lang.add_relation("forPatient", source=prescription, target=patient)
    rx_drug = lang.add_relation("prescribesDrug", source=prescription, target=drug)
    ci_drug = lang.add_relation("contraindicatesDrug", source=contraindication, target=drug)
    ci_patient = lang.add_relation("appliesToPatient", source=contraindication, target=patient)
    allergy_patient = lang.add_relation("allergyOf", source=allergy_record, target=patient)

    # -------------------------------------------------------------------
    # Normative rules — exercises ALL five operators
    # -------------------------------------------------------------------

    # MUST: Patient identity verified
    lang.must(
        patient_id_verified,
        description="Patient identity must be verified before dispensing",
    )

    # MUST: Prescription must be signed
    lang.must(
        rx_signed,
        description="Prescription must be signed by prescriber",
    )

    # MUST: Every prescription must reference a patient
    lang.must(
        rx_patient,
        description="Every prescription must reference a patient",
    )

    # MUST: Every prescription must reference a drug
    lang.must(
        rx_drug,
        description="Every prescription must reference a drug",
    )

    # MUST NOT: Dispense drug with known contraindication
    lang.must_not(
        rx_drug,
        condition=_check_contraindicated,
        description="Must not dispense drug with known contraindication for patient",
    )

    # SHOULD: Check pregnancy status for teratogenic drugs
    lang.should(
        prescription,
        condition=_check_pregnancy_teratogenic,
        description="Should check pregnancy status when prescribing teratogenic drugs",
    )

    # SHOULD: Verify renal function for nephrotoxic drugs
    lang.should(
        prescription,
        condition=_check_renal_nephrotoxic,
        description="Should verify renal function when prescribing nephrotoxic drugs",
    )

    # SHOULD NOT: Dispense brand-name when generic equivalent exists
    lang.should_not(
        prescription,
        condition=_check_brand_vs_generic,
        description="Should not dispense brand-name when generic equivalent exists",
    )

    # MAY: Accept verbal orders in emergency
    lang.may(
        prescription,
        description="May accept verbal prescription orders in emergency situations",
    )

    # MAY: Substitute therapeutic equivalents
    lang.may(
        rx_drug,
        description="May substitute therapeutic equivalents",
    )

    return lang


def build_domain() -> DomainLanguageGraph:
    """Build the complete Prescription Validation domain.

    DomLG = ({Formulary, PatientSafety}, {(PatientSafety, Formulary)}, λ)
    where λ(PatientSafety, Formulary) = imports
    """
    formulary = build_formulary()
    patient_safety = build_patient_safety()

    graph = DomainLanguageGraph()
    graph.add_language(formulary)
    graph.add_language(patient_safety)
    graph.add_edge("PatientSafety", "Formulary", EdgeLabel.IMPORTS)

    return graph


# ---------------------------------------------------------------------------
# MUST NOT condition: known contraindication
# ---------------------------------------------------------------------------

def _check_contraindicated(world: SemanticWorld):
    """Check if any prescription dispenses a contraindicated drug for its patient.

    Returns list of violations or False.
    """
    violations = []

    # Find all prescriptions
    for rx in world.elements:
        if rx.entity_type.name != "Prescription":
            continue

        # Find patient and drug for this prescription
        patient_id = None
        drug_id = None
        for r in world.relations:
            if r.source_id == rx.identity:
                if r.relation.name == "forPatient":
                    patient_id = r.target_id
                elif r.relation.name == "prescribesDrug":
                    drug_id = r.target_id

        if not patient_id or not drug_id:
            continue

        # Check if there's a contraindication for this drug-patient pair
        for ci in world.elements:
            if ci.entity_type.name != "Contraindication":
                continue

            ci_drug = None
            ci_patient = None
            for r in world.relations:
                if r.source_id == ci.identity:
                    if r.relation.name == "contraindicatesDrug":
                        ci_drug = r.target_id
                    elif r.relation.name == "appliesToPatient":
                        ci_patient = r.target_id

            if ci_drug == drug_id and ci_patient == patient_id:
                violations.append(
                    f"Prescription '{rx.identity}': drug '{drug_id}' is "
                    f"contraindicated for patient '{patient_id}' — "
                    f"reason: {ci.attribute_values.get('reason', 'unspecified')}"
                )

    return violations if violations else False


# ---------------------------------------------------------------------------
# SHOULD condition: pregnancy check for teratogenic drugs
# ---------------------------------------------------------------------------

def _check_pregnancy_teratogenic(world: SemanticWorld):
    """Advisory: pregnancy status should be checked for teratogenic drugs."""
    advisories = []

    for rx in world.elements:
        if rx.entity_type.name != "Prescription":
            continue

        patient_id = None
        drug_id = None
        for r in world.relations:
            if r.source_id == rx.identity:
                if r.relation.name == "forPatient":
                    patient_id = r.target_id
                elif r.relation.name == "prescribesDrug":
                    drug_id = r.target_id

        if not drug_id or not patient_id:
            continue

        # Check if drug is teratogenic
        drug_elem = world.get_element_by_id(drug_id)
        if drug_elem and drug_elem.attribute_values.get("isTeratogenic") is True:
            # Check patient pregnancy status
            patient_elem = world.get_element_by_id(patient_id)
            if patient_elem:
                preg_status = patient_elem.attribute_values.get("pregnancyStatus")
                if preg_status is UNKNOWN or preg_status == UNKNOWN:
                    advisories.append(
                        f"Prescription '{rx.identity}': drug '{drug_id}' is teratogenic "
                        f"but patient '{patient_id}' pregnancy status is UNKNOWN"
                    )

    return advisories if advisories else False


# ---------------------------------------------------------------------------
# SHOULD condition: renal function check for nephrotoxic drugs
# ---------------------------------------------------------------------------

def _check_renal_nephrotoxic(world: SemanticWorld):
    """Advisory: renal function should be checked for nephrotoxic drugs."""
    advisories = []

    for rx in world.elements:
        if rx.entity_type.name != "Prescription":
            continue

        patient_id = None
        drug_id = None
        for r in world.relations:
            if r.source_id == rx.identity:
                if r.relation.name == "forPatient":
                    patient_id = r.target_id
                elif r.relation.name == "prescribesDrug":
                    drug_id = r.target_id

        if not drug_id or not patient_id:
            continue

        drug_elem = world.get_element_by_id(drug_id)
        if drug_elem and drug_elem.attribute_values.get("isNephrotoxic") is True:
            patient_elem = world.get_element_by_id(patient_id)
            if patient_elem:
                renal = patient_elem.attribute_values.get("renalFunction")
                if renal is UNKNOWN or renal == UNKNOWN:
                    advisories.append(
                        f"Prescription '{rx.identity}': drug '{drug_id}' is nephrotoxic "
                        f"but patient '{patient_id}' renal function is UNKNOWN"
                    )

    return advisories if advisories else False


# ---------------------------------------------------------------------------
# SHOULD NOT condition: brand-name when generic exists
# ---------------------------------------------------------------------------

def _check_brand_vs_generic(world: SemanticWorld):
    """Advisory: should not dispense brand-name when generic equivalent exists."""
    advisories = []

    for rx in world.elements:
        if rx.entity_type.name != "Prescription":
            continue

        drug_id = None
        for r in world.relations:
            if r.source_id == rx.identity and r.relation.name == "prescribesDrug":
                drug_id = r.target_id
                break

        if not drug_id:
            continue

        drug_elem = world.get_element_by_id(drug_id)
        if drug_elem:
            is_brand = drug_elem.attribute_values.get("isBrandName", False)
            generic_exists = drug_elem.attribute_values.get("genericEquivalentExists", False)
            if is_brand and generic_exists:
                advisories.append(
                    f"Prescription '{rx.identity}': drug '{drug_id}' is brand-name "
                    f"but generic equivalent exists — consider generic"
                )

    return advisories if advisories else False
