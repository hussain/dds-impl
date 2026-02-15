"""End-to-end tests for Case Study 2: Prescription Validation."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from dds.types import UNKNOWN, EntityType
from dds.validation import SemanticWorld, self_validate, validate, ConditionStatus

from case_studies.prescription.domain import build_domain


@pytest.fixture
def graph():
    return build_domain()


def _get_relations(graph):
    rels = {}
    for lang in graph.languages.values():
        for r in lang.relations:
            rels[r.name] = r
    return rels


class TestDomainConstruction:
    def test_two_languages(self, graph):
        assert len(graph.languages) == 2
        assert "Formulary" in graph.languages
        assert "PatientSafety" in graph.languages

    def test_self_validation_passes(self, graph):
        result = self_validate(graph)
        assert result.is_valid, f"Self-validation failed: {result.errors}"


class TestCleanPrescription:
    def test_valid(self, graph):
        rels = _get_relations(graph)
        world = SemanticWorld()
        world.add_element(
            EntityType("Patient"), "pat1",
            {"name": "Jane", "idVerified": True,
             "pregnancyStatus": "not_pregnant", "renalFunction": "normal"},
            provenance="input",
        )
        world.add_element(
            EntityType("Drug"), "drug1",
            {"name": "Amoxicillin", "activeIngredient": "amoxicillin",
             "schedule": "Rx", "isGeneric": True, "isBrandName": False},
            provenance="formulary",
        )
        world.add_element(
            EntityType("Prescription"), "rx1",
            {"prescriberName": "Dr. Lee", "isSigned": True,
             "dosage": 500.0, "dosageUnit": "mg"},
            provenance="prescription",
        )
        world.add_relation(rels["forPatient"], "rx1", "pat1", provenance="prescription")
        world.add_relation(rels["prescribesDrug"], "rx1", "drug1", provenance="prescription")

        result = validate(graph, world)
        assert result.is_valid


class TestContraindication:
    def test_must_not_violation(self, graph):
        rels = _get_relations(graph)
        world = SemanticWorld()
        world.add_element(
            EntityType("Patient"), "pat1",
            {"name": "Ahmed", "idVerified": True}, provenance="input",
        )
        world.add_element(
            EntityType("Drug"), "drug1",
            {"name": "Methotrexate", "activeIngredient": "methotrexate",
             "schedule": "Rx", "isGeneric": True, "isBrandName": False},
            provenance="formulary",
        )
        world.add_element(
            EntityType("Prescription"), "rx1",
            {"prescriberName": "Dr. Chen", "isSigned": True,
             "dosage": 15.0, "dosageUnit": "mg"},
            provenance="prescription",
        )
        world.add_element(
            EntityType("Contraindication"), "ci1",
            {"reason": "Hepatic impairment", "severity": "absolute"},
            provenance="medical_record",
        )
        world.add_relation(rels["forPatient"], "rx1", "pat1", provenance="prescription")
        world.add_relation(rels["prescribesDrug"], "rx1", "drug1", provenance="prescription")
        world.add_relation(rels["contraindicatesDrug"], "ci1", "drug1", provenance="record")
        world.add_relation(rels["appliesToPatient"], "ci1", "pat1", provenance="record")

        result = validate(graph, world)
        assert not result.is_valid
        c5 = result.conditions[4]
        assert c5.status == ConditionStatus.FAIL
        assert any("contraindicated" in d.lower() for d in c5.details)


class TestUnknownAllergyStatus:
    def test_unknown_surfaced_not_defaulted(self, graph):
        """UNKNOWN allergy status must be preserved, not resolved."""
        rels = _get_relations(graph)
        world = SemanticWorld()
        world.add_element(
            EntityType("Patient"), "pat1",
            {"name": "Maria", "idVerified": True}, provenance="input",
        )
        world.add_element(
            EntityType("Drug"), "drug1",
            {"name": "Penicillin", "activeIngredient": "penicillin",
             "schedule": "Rx", "isGeneric": True, "isBrandName": False},
            provenance="formulary",
        )
        world.add_element(
            EntityType("Prescription"), "rx1",
            {"prescriberName": "Dr. Patel", "isSigned": True,
             "dosage": 250.0, "dosageUnit": "mg"},
            provenance="prescription",
        )
        world.add_element(
            EntityType("AllergyRecord"), "ar1",
            {"allergen": "penicillin", "status": UNKNOWN},
            provenance="admission_record",
        )
        world.add_relation(rels["forPatient"], "rx1", "pat1", provenance="prescription")
        world.add_relation(rels["prescribesDrug"], "rx1", "drug1", provenance="prescription")
        world.add_relation(rels["allergyOf"], "ar1", "pat1", provenance="record")

        result = validate(graph, world)
        # Valid because UNKNOWN is preserved (not inferred as "no allergy")
        assert result.is_valid


class TestTeratogenicUnknownPregnancy:
    def test_should_advisory_surfaced(self, graph):
        rels = _get_relations(graph)
        world = SemanticWorld()
        world.add_element(
            EntityType("Patient"), "pat1",
            {"name": "Sara", "idVerified": True,
             "pregnancyStatus": UNKNOWN, "renalFunction": "normal"},
            provenance="input",
        )
        world.add_element(
            EntityType("Drug"), "drug1",
            {"name": "Isotretinoin", "activeIngredient": "isotretinoin",
             "schedule": "Rx", "isGeneric": False, "isBrandName": True,
             "isTeratogenic": True, "genericEquivalentExists": True},
            provenance="formulary",
        )
        world.add_element(
            EntityType("Prescription"), "rx1",
            {"prescriberName": "Dr. Wilson", "isSigned": True,
             "dosage": 20.0, "dosageUnit": "mg"},
            provenance="prescription",
        )
        world.add_relation(rels["forPatient"], "rx1", "pat1", provenance="prescription")
        world.add_relation(rels["prescribesDrug"], "rx1", "drug1", provenance="prescription")

        result = validate(graph, world)
        # Valid (SHOULD doesn't fail validation) but advisories surfaced
        assert result.is_valid
        c5 = result.conditions[4]
        assert any("teratogenic" in d.lower() for d in c5.details)
        assert any("brand-name" in d.lower() for d in c5.details)


class TestVocabularyClosureFailure:
    def test_unknown_entity_type_rejected(self, graph):
        rels = _get_relations(graph)
        supplement = EntityType("Supplement")  # NOT in any DomL

        world = SemanticWorld()
        world.add_element(
            EntityType("Patient"), "pat1",
            {"name": "Tom", "idVerified": True}, provenance="input",
        )
        world.add_element(supplement, "sup1", {"name": "Vitamin D3"}, provenance="request")

        result = validate(graph, world)
        assert not result.is_valid
        c1 = result.conditions[0]
        assert c1.status == ConditionStatus.FAIL
        assert any("Supplement" in d for d in c1.details)
