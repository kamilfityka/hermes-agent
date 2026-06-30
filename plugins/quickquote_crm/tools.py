"""Tool handlers: accept args:dict, never raise, return JSON string."""
from __future__ import annotations

import json
from typing import Any

from .client import CrmClient, CrmError

_client = CrmClient()


def _ok(payload): return json.dumps(payload, ensure_ascii=False, default=str)
def _err(message): return json.dumps({"error": message}, ensure_ascii=False)
def _compact(data): return {k: v for k, v in data.items() if v not in (None, "", [])}


def _call(method, path, **kwargs):
    try:
        return _ok(_client.request(method, path, **kwargs))
    except CrmError as exc:
        return _err(str(exc))


# --- crm ---
def crm_search_clients(args, **_):
    params = _compact({"name": (args.get("name") or "").strip() or None,
                       "nip": (args.get("nip") or "").strip() or None,
                       "itemsPerPage": int(args.get("limit", 5))})
    if not params.get("name") and not params.get("nip"):
        return _err("Podaj 'name' lub 'nip' do wyszukania.")
    return _call("GET", "/clients", params=params)


def crm_get_client(args, **_):
    identifier = _client.id_from_iri(args.get("id"))
    if not identifier:
        return _err("Pole 'id' jest wymagane.")
    return _call("GET", f"/clients/{identifier}")


def crm_create_client(args, **_):
    payload = _compact({"name": args.get("name"), "company": args.get("company"),
                        "email": args.get("email"), "phone": args.get("phone"),
                        "address": args.get("address"), "city": args.get("city"),
                        "nip": args.get("nip"), "notes": args.get("notes")})
    for field in ("name", "company", "email"):
        if not payload.get(field):
            return _err(f"Pole '{field}' jest wymagane.")
    return _call("POST", "/clients", json_body=payload)


def crm_create_contact(args, **_):
    client_iri = _client.iri("clients", _client.id_from_iri(args.get("client_id")))
    if not client_iri:
        return _err("Pole 'client_id' jest wymagane.")
    payload = _compact({"client": client_iri, "firstName": args.get("first_name"),
                        "lastName": args.get("last_name"), "email": args.get("email"),
                        "phone": args.get("phone"), "position": args.get("position")})
    return _call("POST", "/contacts", json_body=payload)


def crm_search_offers(args, **_):
    params = _compact({"q": (args.get("query") or "").strip() or None,
                       "status": args.get("status"),
                       "client": _client.iri("clients", _client.id_from_iri(args.get("client_id"))),
                       "assignedTo": _client.iri("users", _client.id_from_iri(args.get("assigned_to_id"))),
                       "page": int(args.get("page", 1))})
    return _call("GET", "/offers", params=params)


def crm_get_offer(args, **_):
    identifier = _client.id_from_iri(args.get("id"))
    if not identifier:
        return _err("Pole 'id' jest wymagane.")
    return _call("GET", f"/offers/{identifier}")


def crm_create_offer(args, **_):
    if not args.get("number") or not args.get("client_name"):
        return _err("Pola 'number' i 'client_name' są wymagane.")
    try:
        created_by = _client.current_user_iri()
    except CrmError as exc:
        return _err(str(exc))
    payload = _compact({"number": args.get("number"), "clientName": args.get("client_name"),
                        "client": _client.iri("clients", _client.id_from_iri(args.get("client_id"))),
                        "contactName": args.get("contact_name"), "validUntil": args.get("valid_until"),
                        "language": args.get("language", "pl"), "notes": args.get("notes"),
                        "createdBy": created_by})
    try:
        offer = _client.request("POST", "/offers", json_body=payload)
    except CrmError as exc:
        return _err(str(exc))
    offer_iri = _client.iri("offers", _client.id_from_iri(offer.get("id")))
    created_items, item_errors = [], []
    for raw in args.get("items") or []:
        item_payload = _compact({"offer": offer_iri, "productName": raw.get("product_name"),
                                 "productSku": raw.get("product_sku"), "quantity": raw.get("quantity"),
                                 "unitPrice": raw.get("unit_price"), "discount": raw.get("discount", 0)})
        try:
            created_items.append(_client.request("POST", "/offer_items", json_body=item_payload))
        except CrmError as exc:
            item_errors.append({"item": raw.get("product_name"), "error": str(exc)})
    return _ok({"offer": offer, "items": created_items, "item_errors": item_errors})


def crm_update_offer(args, **_):
    identifier = _client.id_from_iri(args.get("id"))
    if not identifier:
        return _err("Pole 'id' jest wymagane.")
    payload = _compact({"status": args.get("status"),
                        "salesStage": _client.iri("sales_stages", _client.id_from_iri(args.get("sales_stage_id"))),
                        "assignedTo": _client.iri("users", _client.id_from_iri(args.get("assigned_to_id"))),
                        "nextFollowUpAt": args.get("next_follow_up_at"), "notes": args.get("notes")})
    if not payload:
        return _err("Podaj przynajmniej jedno pole do zmiany.")
    return _call("PATCH", f"/offers/{identifier}", json_body=payload)


def crm_close_offer(args, **_):
    identifier = _client.id_from_iri(args.get("id"))
    result = args.get("result")
    if not identifier or result not in ("won", "lost"):
        return _err("Wymagane: 'id' oraz 'result' = 'won' lub 'lost'.")
    payload = _compact({"result": result, "reason": args.get("reason"),
                        "lossReasonId": _client.id_from_iri(args.get("loss_reason_id"))})
    return _call("POST", f"/api/offers/{identifier}/close", json_body=payload)


def crm_reopen_offer(args, **_):
    identifier = _client.id_from_iri(args.get("id"))
    if not identifier:
        return _err("Pole 'id' jest wymagane.")
    return _call("POST", f"/api/offers/{identifier}/reopen")


def crm_add_comment(args, **_):
    offer_iri = _client.iri("offers", _client.id_from_iri(args.get("offer_id")))
    content = (args.get("content") or "").strip()
    if not offer_iri or not content:
        return _err("Wymagane: 'offer_id' oraz 'content'.")
    return _call("POST", "/offer_comments", json_body={"offer": offer_iri, "content": content})


def crm_send_offer_email(args, **_):
    identifier = _client.id_from_iri(args.get("offer_id"))
    recipient = args.get("recipient", "me")
    if not identifier:
        return _err("Pole 'offer_id' jest wymagane.")
    if recipient not in ("client", "me"):
        return _err("'recipient' musi być 'client' albo 'me'.")
    return _call("POST", f"/offers/{identifier}/email/{recipient}")


def crm_pipeline_stats(_args, **_):
    return _call("GET", "/api/stats/pipeline")


# --- catalog ---
def catalog_search_skus(args, **_):
    query = (args.get("query") or "").strip().lower()
    limit = int(args.get("limit", 10))
    try:
        result = _client.request("GET", "/catalog/skus", authenticated=False)
    except CrmError as exc:
        return _err(str(exc))
    items = result.get("items", result) if isinstance(result, dict) else result
    if query and isinstance(items, list):
        items = [s for s in items if query in json.dumps(s, ensure_ascii=False, default=str).lower()]
    return _ok({"items": items[:limit] if isinstance(items, list) else items})


def catalog_get_sku(args, **_):
    sku = (args.get("sku") or "").strip()
    if not sku:
        return _err("Pole 'sku' jest wymagane.")
    return _call("GET", f"/catalog/skus/{sku}", authenticated=False)


def catalog_list_products(args, **_):
    limit = int(args.get("limit", 20))
    try:
        result = _client.request("GET", "/catalog/products", authenticated=False)
    except CrmError as exc:
        return _err(str(exc))
    items = result.get("items", result) if isinstance(result, dict) else result
    return _ok({"items": items[:limit] if isinstance(items, list) else items})


def catalog_set_sku_quantity(args, **_):
    sku = (args.get("sku") or "").strip()
    if not sku or "quantity" not in args:
        return _err("Wymagane: 'sku' oraz 'quantity'.")
    return _call("PATCH", f"/catalog/skus/by-sku/{sku}/quantity",
                 json_body={"quantity": int(args["quantity"])})


def catalog_add_sku(args, **_):
    payload = _compact({"sku": args.get("sku"), "name": args.get("name"),
                        "colorCode": _client.iri("catalog/color-codes", _client.id_from_iri(args.get("color_code_id"))),
                        "quantity": args.get("quantity", 0)})
    if not payload.get("sku") or not payload.get("colorCode"):
        return _err("Wymagane: 'sku' oraz 'color_code_id'.")
    return _call("POST", "/catalog/skus", json_body=payload)
