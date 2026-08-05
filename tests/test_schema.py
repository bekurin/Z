"""Schema-conformance tests for spec cards.

Valid fixtures must satisfy schemas/spec-card.schema.json; structurally-broken fixtures
must be rejected. Complements test_validate_card (which checks the arithmetic/hash the
schema can't express).
"""
from __future__ import annotations

import pytest

jsonschema = pytest.importorskip("jsonschema")

from conftest import load_fixture


@pytest.mark.parametrize("name", ["valid_greenfield", "valid_brownfield", "forced_pass"])
def test_valid_fixtures_conform(schema, name):
    jsonschema.validate(load_fixture(name), schema)


@pytest.mark.parametrize("name", ["missing_field", "bad_ac"])
def test_structurally_broken_fixtures_are_rejected(schema, name):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(load_fixture(name), schema)


def test_bad_id_pattern_rejected(schema, make_card):
    card = make_card(id="no-timestamp-here")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(card, schema)


def test_frozen_must_be_true(schema, make_card):
    card = make_card(frozen=False)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(card, schema)


def test_unknown_top_level_field_rejected(schema, make_card):
    card = make_card()
    card["surprise"] = "nope"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(card, schema)


def test_threshold_const_enforced(schema, make_card):
    card = make_card()
    card["ambiguity"]["threshold"] = 0.3
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(card, schema)
