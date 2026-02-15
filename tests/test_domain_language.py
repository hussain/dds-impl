"""Tests for Domain Language construction and vocabulary computation."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from dds.domain_language import DomainLanguage
from dds.types import EntityType, Attribute, OperationType, Optionality, UNKNOWN


class TestDomainLanguageConstruction:
    def test_empty_language(self):
        lang = DomainLanguage(name="Empty")
        assert lang.name == "Empty"
        assert len(lang.entities) == 0
        assert len(lang.operations) == 0
        assert len(lang.vocab()) == 0

    def test_add_entity(self):
        lang = DomainLanguage(name="Test")
        visitor = lang.add_entity("Visitor")
        assert isinstance(visitor, EntityType)
        assert visitor.name == "Visitor"
        assert visitor in lang.entities

    def test_add_attribute(self):
        lang = DomainLanguage(name="Test")
        visitor = lang.add_entity("Visitor")
        attr = lang.add_attribute(visitor, "name", value_type=str)
        assert isinstance(attr, Attribute)
        assert attr.entity == visitor
        assert attr.name == "name"
        assert attr.optionality == Optionality.REQUIRED

    def test_add_attribute_unknown_admissible(self):
        lang = DomainLanguage(name="Test")
        visitor = lang.add_entity("Visitor")
        attr = lang.add_attribute(
            visitor, "escorted", value_type=bool,
            optionality=Optionality.UNKNOWN_ADMISSIBLE,
        )
        assert attr.optionality == Optionality.UNKNOWN_ADMISSIBLE

    def test_add_operation(self):
        lang = DomainLanguage(name="Test")
        op = lang.add_operation("CheckIn")
        assert isinstance(op, OperationType)
        assert op in lang.operations

    def test_add_relation(self):
        lang = DomainLanguage(name="Test")
        vr = lang.add_entity("VisitRecord")
        host = lang.add_entity("Host")
        rel = lang.add_relation("host", source=vr, target=host)
        assert rel in lang.relations
        assert rel.source == vr
        assert rel.target == host

    def test_add_import(self):
        lang = DomainLanguage(name="Test")
        imp = lang.add_import("OtherLang")
        assert imp in lang.imports
        assert imp.target_name == "OtherLang"


class TestVocabulary:
    def test_vocab_includes_entities(self):
        lang = DomainLanguage(name="Test")
        visitor = lang.add_entity("Visitor")
        vocab = lang.vocab()
        assert visitor in vocab

    def test_vocab_includes_attributes(self):
        lang = DomainLanguage(name="Test")
        visitor = lang.add_entity("Visitor")
        attr = lang.add_attribute(visitor, "name", value_type=str)
        vocab = lang.vocab()
        assert attr in vocab

    def test_vocab_includes_operations(self):
        lang = DomainLanguage(name="Test")
        op = lang.add_operation("CheckIn")
        vocab = lang.vocab()
        assert op in vocab

    def test_vocab_size(self):
        lang = DomainLanguage(name="Test")
        visitor = lang.add_entity("Visitor")
        lang.add_attribute(visitor, "name", value_type=str)
        lang.add_attribute(visitor, "idVerified", value_type=bool)
        lang.add_operation("CheckIn")
        # 1 entity + 2 attributes + 1 operation = 4
        assert len(lang.vocab()) == 4


class TestGetAttribute:
    def test_found(self):
        lang = DomainLanguage(name="Test")
        visitor = lang.add_entity("Visitor")
        lang.add_attribute(visitor, "name", value_type=str)
        result = lang.get_attribute(visitor, "name")
        assert result is not None
        assert result.name == "name"

    def test_not_found(self):
        lang = DomainLanguage(name="Test")
        visitor = lang.add_entity("Visitor")
        result = lang.get_attribute(visitor, "nonexistent")
        assert result is None


class TestClosureCheck:
    def test_no_imports_no_errors(self):
        lang = DomainLanguage(name="Test")
        lang.add_entity("Visitor")
        errors = lang.check_closure()
        assert len(errors) == 0

    def test_unresolved_import(self):
        lang = DomainLanguage(name="Test")
        lang.add_import("Missing")
        errors = lang.check_closure(resolved_imports={})
        assert any("Unresolved import" in e for e in errors)

    def test_resolved_import(self):
        other = DomainLanguage(name="Other")
        other.add_entity("SharedEntity")

        lang = DomainLanguage(name="Test")
        lang.add_import("Other")
        errors = lang.check_closure(resolved_imports={"Other": other})
        assert len(errors) == 0
