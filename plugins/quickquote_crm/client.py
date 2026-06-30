"""HTTP client for the QuickQuote Pro API (Symfony + API Platform + LexikJWT)."""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

_TOKEN_REFRESH_SKEW_SECONDS = 60
_DEFAULT_TTL_SECONDS = 8 * 60 * 60  # matches lexik_jwt token_ttl


class CrmError(Exception):
    """Config/transport error that handlers turn into JSON."""


class CrmClient:
    """Stateful client that owns a JWT and refreshes it on demand."""

    def __init__(self, base_url=None, email=None, password=None, *, timeout=20.0):
        self._base_url = (base_url or os.getenv("CRM_API_BASE_URL", "")).rstrip("/")
        self._email = email or os.getenv("CRM_EMAIL", "")
        self._password = password or os.getenv("CRM_PASSWORD", "")
        self._timeout = timeout
        self._token = None
        self._token_expires_at = 0.0
        self._current_user_iri = None

    # --- IRI helpers ---
    @staticmethod
    def iri(resource: str, identifier):
        if not identifier:
            return None
        if identifier.startswith("/"):
            return identifier
        return f"/{resource.strip('/')}/{identifier}"

    @staticmethod
    def id_from_iri(value):
        if isinstance(value, str) and value.startswith("/"):
            return value.rstrip("/").rsplit("/", 1)[-1]
        return value

    # --- auth ---
    def _config_error(self):
        missing = [n for n, v in (
            ("CRM_API_BASE_URL", self._base_url),
            ("CRM_EMAIL", self._email),
            ("CRM_PASSWORD", self._password),
        ) if not v]
        if missing:
            return "Brak wymaganych zmiennych środowiskowych: " + ", ".join(missing)
        return None

    def _login(self):
        url = f"{self._base_url}/authentication_token"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    url,
                    json={"email": self._email, "password": self._password},
                    headers={"Accept": "application/json"},
                )
        except httpx.HTTPError as exc:
            raise CrmError(f"Nie udało się połączyć z CRM przy logowaniu: {exc}") from exc
        if response.status_code >= 400:
            raise CrmError(
                f"Logowanie do CRM nieudane (HTTP {response.status_code}). "
                "Sprawdź CRM_EMAIL / CRM_PASSWORD konta serwisowego."
            )
        token = response.json().get("token")
        if not token:
            raise CrmError("Odpowiedź logowania nie zawiera pola 'token'.")
        self._token = token
        self._token_expires_at = time.time() + _DEFAULT_TTL_SECONDS
        self._current_user_iri = None

    def _ensure_token(self):
        if self._token and time.time() < self._token_expires_at - _TOKEN_REFRESH_SKEW_SECONDS:
            return
        self._login()

    # --- core request ---
    def request(self, method, path, *, params=None, json_body=None,
                authenticated=True, _retry_on_401=True):
        config_error = self._config_error()
        if config_error:
            raise CrmError(config_error)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/merge-patch+json"
            if method.upper() == "PATCH" else "application/json",
        }
        if authenticated:
            self._ensure_token()
            headers["Authorization"] = f"Bearer {self._token}"
        url = f"{self._base_url}{path}"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.request(method, url, params=params,
                                          json=json_body, headers=headers)
        except httpx.HTTPError as exc:
            raise CrmError(f"Błąd połączenia z CRM: {exc}") from exc
        if response.status_code == 401 and authenticated and _retry_on_401:
            self._token = None
            return self.request(method, path, params=params, json_body=json_body,
                                authenticated=authenticated, _retry_on_401=False)
        if response.status_code >= 400:
            raise CrmError(self._format_error(response))
        if not response.content:
            return {"ok": True, "status_code": response.status_code}
        if "json" not in response.headers.get("content-type", ""):
            return {"text": response.text[:2000]}
        return self._unwrap(response.json())

    @staticmethod
    def _format_error(response):
        try:
            body = response.json()
            detail = (body.get("detail") or body.get("hydra:description")
                      or body.get("title") or body.get("message") or "")
        except ValueError:
            detail = response.text[:500]
        suffix = f": {detail}" if detail else ""
        return f"CRM API zwróciło błąd HTTP {response.status_code}{suffix}"

    @staticmethod
    def _unwrap(payload):
        if isinstance(payload, dict) and "hydra:member" in payload:
            return {"items": payload.get("hydra:member", []),
                    "total": payload.get("hydra:totalItems")}
        return payload

    def current_user_iri(self):
        if self._current_user_iri:
            return self._current_user_iri
        me = self.request("GET", "/users/me")
        identifier = me.get("id") if isinstance(me, dict) else None
        if not identifier:
            raise CrmError("Nie udało się ustalić bieżącego użytkownika (/users/me).")
        self._current_user_iri = self.iri("users", str(identifier))
        return self._current_user_iri
