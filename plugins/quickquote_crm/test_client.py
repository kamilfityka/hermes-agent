"""Unit tests for pure helpers (no network). Run: python test_client.py"""
from __future__ import annotations

from client import CrmClient


def test_iri_from_bare_id():
    assert CrmClient.iri("clients", "abc-123") == "/clients/abc-123"

def test_iri_passthrough_when_already_iri():
    assert CrmClient.iri("clients", "/clients/abc-123") == "/clients/abc-123"

def test_iri_strips_resource_slashes():
    assert CrmClient.iri("/users/", "u1") == "/users/u1"

def test_iri_none_for_empty():
    assert CrmClient.iri("clients", None) is None
    assert CrmClient.iri("clients", "") is None

def test_id_from_iri():
    assert CrmClient.id_from_iri("/clients/abc-123") == "abc-123"
    assert CrmClient.id_from_iri("/catalog/color-codes/xyz") == "xyz"

def test_id_from_iri_passthrough():
    assert CrmClient.id_from_iri("abc-123") == "abc-123"
    assert CrmClient.id_from_iri(None) is None

def test_unwrap_hydra_collection():
    payload = {"hydra:member": [{"id": 1}], "hydra:totalItems": 1}
    assert CrmClient._unwrap(payload) == {"items": [{"id": 1}], "total": 1}

def test_unwrap_plain_object():
    assert CrmClient._unwrap({"id": 1}) == {"id": 1}

def test_config_error_lists_missing():
    error = CrmClient(base_url="", email="", password="")._config_error()
    assert "CRM_API_BASE_URL" in error and "CRM_EMAIL" in error and "CRM_PASSWORD" in error

def test_config_error_none_when_complete():
    assert CrmClient(base_url="https://x/api", email="a@b.pl", password="pw")._config_error() is None


if __name__ == "__main__":
    import sys
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1; print(f"FAIL {name}: {exc}")
    sys.exit(1 if failures else 0)
