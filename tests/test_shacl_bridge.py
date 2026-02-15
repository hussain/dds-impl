"""Tests for the DDS→SHACL bridge.

Demonstrates that DDS domain definitions translate correctly to SHACL shapes
and that pySHACL validation produces results consistent with DDS validation.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from rdflib import Graph, Namespace, RDF, RDFS, Literal, URIRef
from rdflib.namespace import SH, XSD

from dds.domain_language import DomainLanguage
from dds.domain_language_graph import DomainLanguageGraph
from dds.normative import NormativeOp
from dds.types import UNKNOWN, EntityType, Optionality
from dds.validation import SemanticWorld, check_admissibility, evaluate_rules
from dds.shacl_bridge import (
    DDS,
    DDS_DATA,
    domain_to_shacl,
    world_to_rdf,
    shacl_validate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _simple_domain() -> DomainLanguageGraph:
    """Build a minimal domain: Person with name (required) and verified (MUST)."""
    lang = DomainLanguage(name="TestDomain")
    person = lang.add_entity("Person")
    lang.add_attribute(person, "name", value_type=str)
    verified = lang.add_attribute(person, "verified", value_type=bool)
    lang.must(verified, description="Person must be verified")

    item = lang.add_entity("Item")
    lang.add_attribute(item, "label", value_type=str)

    lang.add_relation("owns", source=person, target=item)

    graph = DomainLanguageGraph()
    graph.add_language(lang)
    return graph


# ---------------------------------------------------------------------------
# Shape generation tests
# ---------------------------------------------------------------------------

class TestDomainToShacl:
    def test_generates_node_shapes(self):
        graph = _simple_domain()
        shapes = domain_to_shacl(graph)

        # Should have NodeShape for Person and Item
        node_shapes = list(shapes.subjects(RDF.type, SH.NodeShape))
        assert len(node_shapes) == 2

        shape_uris = {str(s) for s in node_shapes}
        assert str(DDS["PersonShape"]) in shape_uris
        assert str(DDS["ItemShape"]) in shape_uris

    def test_person_shape_targets_class(self):
        graph = _simple_domain()
        shapes = domain_to_shacl(graph)

        target = shapes.value(DDS["PersonShape"], SH.targetClass)
        assert target == DDS["Person"]

    def test_must_attribute_has_min_count(self):
        graph = _simple_domain()
        shapes = domain_to_shacl(graph)

        # Find the property shape for 'verified' on PersonShape
        verified_shape = None
        for prop in shapes.objects(DDS["PersonShape"], SH.property):
            path = shapes.value(prop, SH.path)
            if path == DDS["verified"]:
                verified_shape = prop
                break

        assert verified_shape is not None
        min_count = shapes.value(verified_shape, SH.minCount)
        assert min_count is not None
        assert int(min_count) == 1

    def test_relation_has_class_constraint(self):
        graph = _simple_domain()
        shapes = domain_to_shacl(graph)

        # Find the property shape for 'owns' on PersonShape
        owns_shape = None
        for prop in shapes.objects(DDS["PersonShape"], SH.property):
            path = shapes.value(prop, SH.path)
            if path == DDS["owns"]:
                owns_shape = prop
                break

        assert owns_shape is not None
        cls = shapes.value(owns_shape, SH["class"])
        assert cls == DDS["Item"]

    def test_shapes_serializable(self):
        graph = _simple_domain()
        shapes = domain_to_shacl(graph)
        turtle = shapes.serialize(format="turtle")
        assert "PersonShape" in turtle
        assert "sh:NodeShape" in turtle


# ---------------------------------------------------------------------------
# RDF data graph tests
# ---------------------------------------------------------------------------

class TestWorldToRdf:
    def test_elements_become_resources(self):
        world = SemanticWorld()
        world.add_element(EntityType("Person"), "p1", {"name": "Alice", "verified": True})

        rdf = world_to_rdf(world)
        uri = DDS_DATA["p1"]
        assert (uri, RDF.type, DDS["Person"]) in rdf

    def test_attributes_become_properties(self):
        world = SemanticWorld()
        world.add_element(EntityType("Person"), "p1", {"name": "Alice", "verified": True})

        rdf = world_to_rdf(world)
        uri = DDS_DATA["p1"]

        name_val = rdf.value(uri, DDS["name"])
        assert str(name_val) == "Alice"

        verified_val = rdf.value(uri, DDS["verified"])
        assert verified_val.toPython() is True

    def test_unknown_values_omitted(self):
        world = SemanticWorld()
        world.add_element(EntityType("Person"), "p1", {"name": "Alice", "verified": UNKNOWN})

        rdf = world_to_rdf(world)
        uri = DDS_DATA["p1"]

        # name should be present
        assert rdf.value(uri, DDS["name"]) is not None
        # verified=UNKNOWN should be omitted
        assert rdf.value(uri, DDS["verified"]) is None

    def test_relations_become_triples(self):
        from dds.types import Relation
        person = EntityType("Person")
        item = EntityType("Item")
        owns = Relation("owns", source=person, target=item)

        world = SemanticWorld()
        world.add_element(person, "p1", {"name": "Alice", "verified": True})
        world.add_element(item, "i1", {"label": "Book"})
        world.add_relation(owns, "p1", "i1")

        rdf = world_to_rdf(world)
        assert (DDS_DATA["p1"], DDS["owns"], DDS_DATA["i1"]) in rdf

    def test_provenance_as_comment(self):
        world = SemanticWorld()
        world.add_element(
            EntityType("Person"), "p1",
            {"name": "Alice"}, provenance="input_form"
        )

        rdf = world_to_rdf(world)
        comment = rdf.value(DDS_DATA["p1"], RDFS.comment)
        assert comment is not None
        assert "input_form" in str(comment)


# ---------------------------------------------------------------------------
# End-to-end SHACL validation tests
# ---------------------------------------------------------------------------

class TestShaclValidation:
    def test_valid_world_conforms(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(
            EntityType("Person"), "p1",
            {"name": "Alice", "verified": True},
            provenance="input",
        )

        result = shacl_validate(graph, world)
        assert result.conforms

    def test_missing_must_attribute_fails(self):
        graph = _simple_domain()
        world = SemanticWorld()
        # 'verified' is MUST but not provided
        world.add_element(EntityType("Person"), "p1", {"name": "Alice"})

        result = shacl_validate(graph, world)
        assert not result.conforms
        assert len(result.violations) > 0

    def test_unknown_value_detected_as_missing(self):
        """UNKNOWN in DDS → omitted in RDF → SHACL detects missing required property."""
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(
            EntityType("Person"), "p1",
            {"name": "Alice", "verified": UNKNOWN},
        )

        result = shacl_validate(graph, world)
        # SHACL should flag the missing 'verified' (since UNKNOWN is omitted)
        assert not result.conforms

    def test_dds_and_shacl_agree_on_valid(self):
        """DDS admissibility and SHACL should both pass for a valid world."""
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(
            EntityType("Person"), "p1",
            {"name": "Alice", "verified": True},
            provenance="input",
        )

        dds_result = check_admissibility(graph, world)
        shacl_result = shacl_validate(graph, world)

        assert dds_result.is_admissible
        assert shacl_result.conforms

    def test_dds_and_shacl_agree_on_invalid(self):
        """Both DDS and SHACL should flag missing MUST attribute."""
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(EntityType("Person"), "p1", {"name": "Alice"})

        dds_result = check_admissibility(graph, world)
        shacl_result = shacl_validate(graph, world)

        assert not dds_result.is_admissible
        assert not shacl_result.conforms

    def test_summary_output(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(
            EntityType("Person"), "p1",
            {"name": "Alice", "verified": True},
            provenance="input",
        )

        result = shacl_validate(graph, world)
        summary = result.summary()
        assert "CONFORMS" in summary

    def test_turtle_output(self):
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(
            EntityType("Person"), "p1",
            {"name": "Alice", "verified": True},
        )

        result = shacl_validate(graph, world)
        shapes_ttl = result.shapes_as_turtle()
        data_ttl = result.data_as_turtle()

        assert "PersonShape" in shapes_ttl
        assert "Alice" in data_ttl


# ---------------------------------------------------------------------------
# DDS-beyond-SHACL: what DDS catches that SHACL doesn't
# ---------------------------------------------------------------------------

class TestDdsBeyondShacl:
    def test_vocabulary_closure_not_in_shacl(self):
        """DDS catches unknown entity types; SHACL doesn't (open-world for types)."""
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(EntityType("Alien"), "a1", {"name": "Zog"})

        # DDS catches this immediately (vocabulary closure)
        dds_result = check_admissibility(graph, world)
        assert not dds_result.is_admissible

        # SHACL has no shape for Alien, so it won't flag it
        # (SHACL only validates nodes that match sh:targetClass)
        shacl_result = shacl_validate(graph, world)
        assert shacl_result.conforms  # SHACL misses this!

    def test_unknown_is_admissible_in_dds_but_fails_shacl(self):
        """DDS treats UNKNOWN as admissible (explicit gap); SHACL sees it as missing."""
        graph = _simple_domain()
        world = SemanticWorld()
        world.add_element(
            EntityType("Person"), "p1",
            {"name": "Alice", "verified": UNKNOWN},
            provenance="input",
        )

        dds_result = check_admissibility(graph, world)
        assert dds_result.is_admissible  # UNKNOWN is an explicit gap, admissible
        assert dds_result.has_unknowns    # but flagged

        shacl_result = shacl_validate(graph, world)
        assert not shacl_result.conforms  # SHACL sees missing property = violation
