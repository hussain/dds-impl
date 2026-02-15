"""Prescription Validation — Gating example.

Demonstrates gating from clinical guidelines (open-world knowledge K)
into Domain Language definitions.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dds.gating import GatingAgent, GatingResult, SourceProposition, StructuredSource
from .domain import build_formulary, build_patient_safety


class PrescriptionGatingAgent(GatingAgent):
    """Gating agent for clinical pharmacy guidelines.

    Transforms open-world clinical guidelines into DDS Domain Language
    definitions. Treated as untrusted — validation happens after gating.
    """

    def gate(self, source: StructuredSource) -> GatingResult:
        provenance_map: dict[str, list[SourceProposition]] = {}
        unknowns: list[str] = []

        for prop in source.propositions:
            text = prop.text.lower()

            if "identity" in text or "verify" in text and "patient" in text:
                provenance_map.setdefault("MUST(Patient.idVerified)", []).append(prop)

            elif "signed" in text or "signature" in text:
                provenance_map.setdefault("MUST(Prescription.isSigned)", []).append(prop)

            elif "contraindic" in text:
                provenance_map.setdefault(
                    "MUST_NOT(contraindicated drug)", []
                ).append(prop)

            elif "teratogenic" in text or "pregnancy" in text:
                provenance_map.setdefault(
                    "SHOULD(pregnancy check for teratogenic)", []
                ).append(prop)

            elif "nephrotoxic" in text or "renal" in text:
                provenance_map.setdefault(
                    "SHOULD(renal check for nephrotoxic)", []
                ).append(prop)

            elif "generic" in text and ("brand" in text or "prefer" in text):
                provenance_map.setdefault(
                    "SHOULD_NOT(brand when generic exists)", []
                ).append(prop)

            elif "verbal" in text or "emergency" in text:
                provenance_map.setdefault(
                    "MAY(verbal orders in emergency)", []
                ).append(prop)

        # UNKNOWN-preserving: guidelines may not cover all scenarios
        unknowns.append(
            "Drug interaction severity thresholds: guidelines reference "
            "'clinically significant' without quantitative criteria. "
            "Severity assessment is UNKNOWN-admissible."
        )
        unknowns.append(
            "Pediatric dosage adjustments: guidelines address adult patients only. "
            "Pediatric dosing rules are UNKNOWN."
        )

        formulary = build_formulary()

        return GatingResult.accepted(
            domain_language=formulary,
            provenance_map=provenance_map,
            unknowns=unknowns,
        )


def create_clinical_guidelines_source() -> StructuredSource:
    """Create the structured source K from clinical pharmacy guidelines."""
    source = StructuredSource(name="Hospital Pharmacy Practice Guidelines v2.1")

    source.add(
        "Patient identity must be verified before any drug is dispensed.",
        source_document="Hospital Pharmacy Practice Guidelines v2.1",
        source_section="Section 3.1: Patient Identification",
    )
    source.add(
        "All prescriptions must bear the prescriber's signature.",
        source_document="Hospital Pharmacy Practice Guidelines v2.1",
        source_section="Section 3.2: Prescription Validity",
    )
    source.add(
        "No drug shall be dispensed if a documented contraindication exists for the patient.",
        source_document="Hospital Pharmacy Practice Guidelines v2.1",
        source_section="Section 4.1: Contraindication Screening",
    )
    source.add(
        "Pregnancy status should be assessed before dispensing teratogenic medications.",
        source_document="Hospital Pharmacy Practice Guidelines v2.1",
        source_section="Section 4.2: Special Population Screening",
    )
    source.add(
        "Renal function should be evaluated before dispensing nephrotoxic agents.",
        source_document="Hospital Pharmacy Practice Guidelines v2.1",
        source_section="Section 4.3: Organ Function Assessment",
    )
    source.add(
        "Generic equivalents should be preferred over brand-name drugs when available.",
        source_document="Hospital Pharmacy Practice Guidelines v2.1",
        source_section="Section 5.1: Formulary Compliance",
    )
    source.add(
        "Verbal prescription orders may be accepted in documented emergency situations.",
        source_document="Hospital Pharmacy Practice Guidelines v2.1",
        source_section="Section 3.3: Emergency Provisions",
    )

    return source
