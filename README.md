# DDS — Example Implementation

Python implementation accompanying the paper:

> **Deterministic Domain Semantics: A Formal Layer for Closing Open Worlds**
> Hussain Hammad. *Submitted to Journal of Web Semantics.*

## Overview

Deterministic Domain Semantics (DDS) is a representation-independent formal layer
that renders open-world knowledge systematically closable through explicit domain
definition. This repository provides an example implementation of the core
abstractions defined in the paper.

### Core modules (`dds/`)

| Module | Paper section | Description |
|---|---|---|
| `types.py` | Sec. 2.1 | Domain Language tuple components (DomL) |
| `normative.py` | Sec. 2.3 | Normative rule modalities and Self-QC |
| `domain_language.py` | Sec. 2.1 | DomL construction and validation |
| `domain_language_graph.py` | Sec. 2.4 | DomLG — composition via import edges |
| `gating.py` | Sec. 3 | OWA→CWA transformation |
| `validation.py` | Sec. 4 | Three-layer validation (Self-QC → Admissibility → Execution) |
| `shacl_bridge.py` | Sec. 5 | DDS→SHACL translation demonstrating complementarity |

### Case studies (`case_studies/`)

| Case study | Scenarios | Description |
|---|---|---|
| `visitor_access/` | 3 | Building visitor access control (Sec. 6.1) |
| `prescription/` | 5 | Medical prescription validation (Sec. 6.2) |

## Requirements

- Python ≥ 3.11
- No dependencies for core modules
- Optional: `rdflib`, `pyshacl` for the SHACL bridge

## Usage

```bash
# Install optional SHACL dependencies
pip install rdflib pyshacl

# Run all tests
python -m pytest

# Run a case study
python -m case_studies.visitor_access.run
python -m case_studies.prescription.run
```

## License

MIT — see [LICENSE](LICENSE).
