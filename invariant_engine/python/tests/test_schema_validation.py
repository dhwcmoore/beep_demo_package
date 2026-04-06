"""
test_schema_validation.py

Verifies that:
1. Both the example and generated JSON fixtures validate against the
   audit_invariants.v1 JSON Schema (draft-07).
2. A deliberately malformed document fails validation with a clear error.
3. A document with an unknown top-level key fails (additionalProperties: false).
"""
import json
import os
import copy
import pytest
import jsonschema

# ── paths ────────────────────────────────────────────────────────────────────

_HERE = os.path.dirname(__file__)
_SCHEMAS_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "schemas"))

_SCHEMA_PATH   = os.path.join(_SCHEMAS_DIR, "audit_invariants.v1.schema.json")
_EXAMPLE_PATH  = os.path.join(_SCHEMAS_DIR, "audit_invariants.v1.example.json")
_GENERATED_PATH = os.path.join(_SCHEMAS_DIR, "audit_invariants.v1.generated.json")


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def schema():
    with open(_SCHEMA_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def example_doc():
    with open(_EXAMPLE_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def generated_doc():
    with open(_GENERATED_PATH) as f:
        return json.load(f)


def _validate(doc, schema):
    """Validate doc against schema; raises jsonschema.ValidationError on failure."""
    jsonschema.validate(instance=doc, schema=schema,
                        format_checker=jsonschema.FormatChecker())


# ── tests ─────────────────────────────────────────────────────────────────────

def test_example_validates(schema, example_doc):
    _validate(example_doc, schema)


def test_generated_validates(schema, generated_doc):
    _validate(generated_doc, schema)


def test_missing_required_field_fails(schema, example_doc):
    """Removing a required field must produce a ValidationError."""
    bad = copy.deepcopy(example_doc)
    del bad["homology"]
    with pytest.raises(jsonschema.ValidationError, match="'homology' is a required property"):
        _validate(bad, schema)


def test_wrong_schema_version_fails(schema, example_doc):
    """schema_version must be the literal string 'audit_invariants.v1'."""
    bad = copy.deepcopy(example_doc)
    bad["schema_version"] = "audit_invariants.v2"
    with pytest.raises(jsonschema.ValidationError):
        _validate(bad, schema)


def test_bad_hash_pattern_fails(schema, example_doc):
    """payload_sha256 must be exactly 64 lowercase hex chars."""
    bad = copy.deepcopy(example_doc)
    bad["integrity"]["payload_sha256"] = "not-a-hash"
    with pytest.raises(jsonschema.ValidationError):
        _validate(bad, schema)


def test_unknown_top_level_key_fails(schema, example_doc):
    """additionalProperties: false — unknown keys must be rejected."""
    bad = copy.deepcopy(example_doc)
    bad["rogue_field"] = "oops"
    with pytest.raises(jsonschema.ValidationError, match="rogue_field"):
        _validate(bad, schema)


def test_negative_betti_fails(schema, example_doc):
    """Betti numbers must be non-negative integers."""
    bad = copy.deepcopy(example_doc)
    bad["homology"]["betti"]["0"] = -1
    with pytest.raises(jsonschema.ValidationError):
        _validate(bad, schema)
