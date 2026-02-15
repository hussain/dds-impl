"""SHACL Bridge — translates DDS domain definitions to SHACL shapes.

Demonstrates DDS→SHACL complementarity:
  - DDS (Layers 1-2) validates domain definition coherence and admissibility
  - SHACL validates instance data (RDF graphs) against shapes

This bridge translates:
  1. DomL entities/attributes → SHACL NodeShapes with property constraints
  2. DomL relations → SHACL property shapes with sh:class constraints
  3. DomL normative rules → SHACL constraint mappings:
       MUST attribute → sh:minCount 1
       Relation type → sh:class on the target
       Optionality REQUIRED → sh:minCount 1
       Optionality OPTIONAL → sh:minCount 0
  4. SemanticWorld → RDF data graph for validation

DDS normative operators that have no direct SHACL equivalent
(MUST_NOT conditionals, SHOULD, SHOULD_NOT, MAY) are documented as
comments in the shapes graph to show the boundary between DDS and SHACL.
"""

from __future__ import annotations

from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, URIRef, XSD
from rdflib.namespace import SH

from .domain_language import DomainLanguage
from .domain_language_graph import DomainLanguageGraph
from .normative import NormativeOp
from .types import (
    UNKNOWN,
    Attribute,
    EntityType,
    Optionality,
    Relation,
)
from .validation import SemanticWorld


# ---------------------------------------------------------------------------
# Namespace for DDS-generated RDF
# ---------------------------------------------------------------------------

DDS = Namespace("http://dds.example.org/")
DDS_DATA = Namespace("http://dds.example.org/data/")


# ---------------------------------------------------------------------------
# Type mapping: Python types → XSD datatypes
# ---------------------------------------------------------------------------

_TYPE_MAP = {
    str: XSD.string,
    int: XSD.integer,
    float: XSD.double,
    bool: XSD.boolean,
}


# ---------------------------------------------------------------------------
# DomL → SHACL Shapes
# ---------------------------------------------------------------------------

def domain_to_shacl(graph: DomainLanguageGraph) -> Graph:
    """Translate a DomainLanguageGraph into a SHACL shapes graph.

    Each entity type becomes a sh:NodeShape. Attributes become property
    shapes with datatype and cardinality constraints. Relations become
    property shapes with sh:class constraints.

    Normative rules are reflected where SHACL has a direct equivalent:
      - MUST on attribute → sh:minCount 1 (enforced)
      - MUST on relation → sh:minCount 1 on the property shape

    Normative rules without direct SHACL equivalents are added as
    rdfs:comment annotations on the shape:
      - MUST_NOT (conditional) → comment noting the prohibition
      - SHOULD / SHOULD_NOT → comment noting the advisory
      - MAY → comment noting permission
    """
    sg = Graph()
    sg.bind("sh", SH)
    sg.bind("dds", DDS)
    sg.bind("xsd", XSD)

    # Collect MUST targets for minCount enforcement
    must_targets = set()
    for lang in graph.languages.values():
        for rule in lang.normative_rules:
            if rule.operator == NormativeOp.MUST:
                must_targets.add(rule.target.element)

    for lang in graph.languages.values():
        for entity in lang.entities:
            shape_uri = DDS[f"{entity.name}Shape"]

            sg.add((shape_uri, RDF.type, SH.NodeShape))
            sg.add((shape_uri, SH.targetClass, DDS[entity.name]))
            sg.add((shape_uri, RDFS.label, Literal(f"Shape for {entity.name}")))

            # Attributes → property shapes
            for attr in lang.attributes.get(entity, []):
                prop_shape = BNode()
                sg.add((shape_uri, SH.property, prop_shape))
                sg.add((prop_shape, SH.path, DDS[attr.name]))
                sg.add((prop_shape, SH.name, Literal(attr.name)))

                # Datatype
                if attr.value_type and attr.value_type in _TYPE_MAP:
                    sg.add((prop_shape, SH.datatype, _TYPE_MAP[attr.value_type]))

                # Cardinality from optionality
                if attr.optionality == Optionality.REQUIRED or attr in must_targets:
                    sg.add((prop_shape, SH.minCount, Literal(1)))
                sg.add((prop_shape, SH.maxCount, Literal(1)))

            # Relations → property shapes with sh:class
            for rel in lang.relations:
                if rel.source != entity:
                    continue
                prop_shape = BNode()
                sg.add((shape_uri, SH.property, prop_shape))
                sg.add((prop_shape, SH.path, DDS[rel.name]))
                sg.add((prop_shape, SH.name, Literal(rel.name)))
                sg.add((prop_shape, SH["class"], DDS[rel.target.name]))

                if rel in must_targets:
                    sg.add((prop_shape, SH.minCount, Literal(1)))

            # Annotate normative rules that don't map to SHACL
            for rule in lang.normative_rules:
                target = rule.target
                if not isinstance(target.element, (EntityType, Attribute)):
                    continue
                # Only annotate entity-scoped rules
                if isinstance(target.element, EntityType) and target.element != entity:
                    continue
                if isinstance(target.element, Attribute) and target.element.entity != entity:
                    continue

                if rule.operator in (NormativeOp.MUST_NOT, NormativeOp.SHOULD,
                                     NormativeOp.SHOULD_NOT, NormativeOp.MAY):
                    desc = target.description or repr(target.element)
                    comment = f"[DDS {rule.operator.value}] {desc}"
                    sg.add((shape_uri, RDFS.comment, Literal(comment)))

    return sg


# ---------------------------------------------------------------------------
# SemanticWorld → RDF Data Graph
# ---------------------------------------------------------------------------

def world_to_rdf(world: SemanticWorld) -> Graph:
    """Translate a SemanticWorld into an RDF data graph.

    Each semantic element becomes an RDF resource with:
      - rdf:type set to the entity type
      - Attribute values as datatype properties
      - Provenance as rdfs:comment (if present)

    UNKNOWN values are omitted from the RDF graph (SHACL will flag
    the missing required property). This is the correct behavior:
    UNKNOWN in DDS means "explicitly unknown" — in RDF, the absence
    is detectable by SHACL's sh:minCount constraint.

    Relations become object property triples.
    """
    dg = Graph()
    dg.bind("dds", DDS)
    dg.bind("data", DDS_DATA)

    for elem in world.elements:
        uri = DDS_DATA[elem.identity]
        dg.add((uri, RDF.type, DDS[elem.entity_type.name]))

        for attr_name, value in elem.attribute_values.items():
            if value is UNKNOWN or value == UNKNOWN:
                # UNKNOWN values are omitted — SHACL will detect the gap
                continue
            dg.add((uri, DDS[attr_name], _to_literal(value)))

        if elem.provenance:
            dg.add((uri, RDFS.comment,
                    Literal(f"provenance: {elem.provenance}")))

    for rel in world.relations:
        source_uri = DDS_DATA[rel.source_id]
        target_uri = DDS_DATA[rel.target_id]
        dg.add((source_uri, DDS[rel.relation.name], target_uri))

    return dg


def _to_literal(value) -> Literal:
    """Convert a Python value to an RDF Literal with appropriate datatype."""
    if isinstance(value, bool):
        return Literal(value, datatype=XSD.boolean)
    if isinstance(value, int):
        return Literal(value, datatype=XSD.integer)
    if isinstance(value, float):
        return Literal(value, datatype=XSD.double)
    return Literal(str(value), datatype=XSD.string)


# ---------------------------------------------------------------------------
# SHACL Validation
# ---------------------------------------------------------------------------

def shacl_validate(
    graph: DomainLanguageGraph,
    world: SemanticWorld,
) -> SHACLValidationResult:
    """Run SHACL validation: DDS domain → shapes, world → data, then validate.

    Returns a structured result with conformance status and violation details.
    """
    from pyshacl import validate as pyshacl_validate

    shapes_graph = domain_to_shacl(graph)
    data_graph = world_to_rdf(world)

    conforms, results_graph, results_text = pyshacl_validate(
        data_graph,
        shacl_graph=shapes_graph,
        inference="none",
        abort_on_first=False,
    )

    # Parse violations from results
    violations = []
    for result in results_graph.subjects(RDF.type, SH.ValidationResult):
        focus = results_graph.value(result, SH.focusNode)
        path = results_graph.value(result, SH.resultPath)
        message = results_graph.value(result, SH.resultMessage)
        severity = results_graph.value(result, SH.resultSeverity)

        violations.append(SHACLViolation(
            focus_node=str(focus) if focus else "",
            path=str(path) if path else "",
            message=str(message) if message else "",
            severity=str(severity) if severity else "",
        ))

    return SHACLValidationResult(
        conforms=conforms,
        violations=violations,
        results_text=results_text,
        shapes_graph=shapes_graph,
        data_graph=data_graph,
    )


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field


@dataclass
class SHACLViolation:
    """A single SHACL validation violation."""
    focus_node: str
    path: str
    message: str
    severity: str

    def __repr__(self) -> str:
        node = self.focus_node.split("/")[-1] if "/" in self.focus_node else self.focus_node
        path = self.path.split("/")[-1] if "/" in self.path else self.path
        return f"SHACLViolation({node}.{path}: {self.message})"


@dataclass
class SHACLValidationResult:
    """Result of SHACL validation through the DDS→SHACL bridge."""
    conforms: bool
    violations: list[SHACLViolation] = field(default_factory=list)
    results_text: str = ""
    shapes_graph: Graph | None = None
    data_graph: Graph | None = None

    def summary(self) -> str:
        lines = []
        status = "CONFORMS" if self.conforms else "DOES NOT CONFORM"
        lines.append(f"SHACL Validation: {status}")
        lines.append("-" * 50)
        if self.violations:
            lines.append(f"  Violations ({len(self.violations)}):")
            for v in self.violations:
                node = v.focus_node.split("/")[-1] if "/" in v.focus_node else v.focus_node
                path = v.path.split("/")[-1] if "/" in v.path else v.path
                lines.append(f"    - {node}.{path}: {v.message}")
        else:
            lines.append("  No violations found.")
        return "\n".join(lines)

    def shapes_as_turtle(self) -> str:
        """Serialize the SHACL shapes graph as Turtle for inspection."""
        if self.shapes_graph is None:
            return ""
        return self.shapes_graph.serialize(format="turtle")

    def data_as_turtle(self) -> str:
        """Serialize the RDF data graph as Turtle for inspection."""
        if self.data_graph is None:
            return ""
        return self.data_graph.serialize(format="turtle")
