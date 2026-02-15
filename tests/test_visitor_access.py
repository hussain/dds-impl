"""End-to-end tests for Case Study 1: Visitor Access Control."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from dds.types import UNKNOWN, EntityType
from dds.validation import SemanticWorld, self_validate, validate, ConditionStatus

from case_studies.visitor_access.domain import build_domain
from case_studies.visitor_access.gating_example import (
    VisitorAccessGatingAgent,
    create_security_manual_source,
)


@pytest.fixture
def graph():
    return build_domain()


class TestDomainConstruction:
    def test_two_languages(self, graph):
        assert len(graph.languages) == 2
        assert "VisitorCore" in graph.languages
        assert "ZonePolicy" in graph.languages

    def test_one_edge(self, graph):
        assert len(graph.edges) == 1
        assert graph.edges[0].source == "ZonePolicy"
        assert graph.edges[0].target == "VisitorCore"

    def test_self_validation_passes(self, graph):
        result = self_validate(graph)
        assert result.is_valid


class TestGating:
    def test_gating_succeeds(self):
        source = create_security_manual_source()
        agent = VisitorAccessGatingAgent()
        result = agent.gate(source)
        assert result.success

    def test_provenance_mapped(self):
        source = create_security_manual_source()
        agent = VisitorAccessGatingAgent()
        result = agent.gate(source)
        assert "MUST(Visitor.idVerified)" in result.provenance_map
        assert "MUST_NOT(secure ∧ ¬escorted)" in result.provenance_map

    def test_unknowns_surfaced(self):
        source = create_security_manual_source()
        agent = VisitorAccessGatingAgent()
        result = agent.gate(source)
        assert len(result.unknowns) > 0
        assert any("restricted" in u.lower() for u in result.unknowns)


class TestScenarioValid:
    def test_all_pass(self, graph):
        vc = graph.languages["VisitorCore"]
        zp = graph.languages["ZonePolicy"]
        vr_visitor = [r for r in vc.relations if r.name == "visitor"][0]
        vr_host = [r for r in vc.relations if r.name == "host"][0]
        vr_zone = [r for r in zp.relations if r.name == "zone"][0]

        world = SemanticWorld()
        world.add_element(EntityType("Visitor"), "v1",
                          {"name": "A. Karim", "idVerified": True}, provenance="input")
        world.add_element(EntityType("Host"), "h1",
                          {"department": "Engineering"}, provenance="input")
        world.add_element(EntityType("Zone"), "z1",
                          {"clearanceLevel": "public"}, provenance="input")
        world.add_element(EntityType("VisitRecord"), "vr1",
                          {"purpose": "meeting", "escorted": True}, provenance="input")
        world.add_relation(vr_visitor, "vr1", "v1", provenance="input")
        world.add_relation(vr_host, "vr1", "h1", provenance="input")
        world.add_relation(vr_zone, "vr1", "z1", provenance="input")

        result = validate(graph, world)
        assert result.is_valid


class TestScenarioUnescortedSecure:
    def test_must_not_violation(self, graph):
        vc = graph.languages["VisitorCore"]
        zp = graph.languages["ZonePolicy"]
        vr_visitor = [r for r in vc.relations if r.name == "visitor"][0]
        vr_host = [r for r in vc.relations if r.name == "host"][0]
        vr_zone = [r for r in zp.relations if r.name == "zone"][0]

        world = SemanticWorld()
        world.add_element(EntityType("Visitor"), "v1",
                          {"name": "R. Fahed", "idVerified": True}, provenance="input")
        world.add_element(EntityType("Host"), "h1",
                          {"department": "Engineering"}, provenance="input")
        world.add_element(EntityType("Zone"), "z2",
                          {"clearanceLevel": "secure"}, provenance="input")
        world.add_element(EntityType("VisitRecord"), "vr1",
                          {"purpose": "maintenance", "escorted": False}, provenance="input")
        world.add_relation(vr_visitor, "vr1", "v1", provenance="input")
        world.add_relation(vr_host, "vr1", "h1", provenance="input")
        world.add_relation(vr_zone, "vr1", "z2", provenance="input")

        result = validate(graph, world)
        assert not result.is_valid
        c5 = result.conditions[4]
        assert c5.status == ConditionStatus.FAIL
        assert any("unescorted" in d.lower() for d in c5.details)
