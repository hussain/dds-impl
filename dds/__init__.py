"""Deterministic Domain Semantics (DDS) — Reference Implementation.

DDS is a semantic layer that renders open-world knowledge systematically closable
through explicit domain definition. This package implements the core abstractions:

- Domain Language (DomL): formal specification of admissible meaning
- Domain Language Graph (DomLG): semantic composition boundary
- Gating: open-world to closed-world transformation
- Validation: DDS-valid admissibility predicate
- SHACL Bridge: DDS→SHACL translation demonstrating complementarity

The validation module cleanly separates three layers:

  Layer 1 — self_validate():       DDS Self-QC (domain definition coherence)
  Layer 2 — check_admissibility(): DDS Admissibility (structural admissibility of W under D)
  Layer 3 — evaluate_rules():      Execution (consuming DDS rules to evaluate records)

  Combined — validate():           Layers 2+3 as the five-condition DDS-valid(D, W) predicate

The SHACL bridge (dds.shacl_bridge) translates DDS domains to SHACL shapes and
semantic worlds to RDF graphs, enabling validation via pySHACL. This demonstrates
that DDS and SHACL are complementary layers: DDS validates domain-level admissibility
(vocabulary closure, normative coherence) while SHACL validates instance-level
conformance (graph shape constraints). Requires optional dependencies: rdflib, pyshacl.
"""
