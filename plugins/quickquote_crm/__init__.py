"""QuickQuote Pro CRM plugin for Hermes.

Registers 18 tools across two toolsets (``crm``, ``catalog``) plus a ``/crm``
help command. The registration calls below match this fork's ``PluginContext``
API (``hermes_cli/plugins.py``):

* ``ctx.register_tool(name=, toolset=, schema=, handler=)`` — verified against
  ``PluginContext.register_tool`` (which also accepts ``check_fn``,
  ``requires_env``, ``emoji`` keywords).
* ``ctx.register_command(name, handler=, description=)`` — verified against
  ``PluginContext.register_command``; the handler signature is
  ``fn(raw_args: str) -> str | None``.

Everything else (client.py / schemas.py / tools.py) is gateway-agnostic — if a
future fork renames these ``ctx`` methods, this file is the only one to touch.
"""
from __future__ import annotations

from . import schemas, tools

_TOOLS = [
    (schemas.CRM_SEARCH_CLIENTS, tools.crm_search_clients, "crm"),
    (schemas.CRM_GET_CLIENT, tools.crm_get_client, "crm"),
    (schemas.CRM_CREATE_CLIENT, tools.crm_create_client, "crm"),
    (schemas.CRM_CREATE_CONTACT, tools.crm_create_contact, "crm"),
    (schemas.CRM_SEARCH_OFFERS, tools.crm_search_offers, "crm"),
    (schemas.CRM_GET_OFFER, tools.crm_get_offer, "crm"),
    (schemas.CRM_CREATE_OFFER, tools.crm_create_offer, "crm"),
    (schemas.CRM_UPDATE_OFFER, tools.crm_update_offer, "crm"),
    (schemas.CRM_CLOSE_OFFER, tools.crm_close_offer, "crm"),
    (schemas.CRM_REOPEN_OFFER, tools.crm_reopen_offer, "crm"),
    (schemas.CRM_ADD_COMMENT, tools.crm_add_comment, "crm"),
    (schemas.CRM_SEND_OFFER_EMAIL, tools.crm_send_offer_email, "crm"),
    (schemas.CRM_PIPELINE_STATS, tools.crm_pipeline_stats, "crm"),
    (schemas.CATALOG_SEARCH_SKUS, tools.catalog_search_skus, "catalog"),
    (schemas.CATALOG_GET_SKU, tools.catalog_get_sku, "catalog"),
    (schemas.CATALOG_LIST_PRODUCTS, tools.catalog_list_products, "catalog"),
    (schemas.CATALOG_SET_SKU_QUANTITY, tools.catalog_set_sku_quantity, "catalog"),
    (schemas.CATALOG_ADD_SKU, tools.catalog_add_sku, "catalog"),
]

_HELP_TEXT = (
    "QuickQuote Pro CRM jest podpięty. Przykłady:\n"
    "- znajdź klienta ACME\n"
    "- pokaż oferty w statusie wysłana\n"
    "- dodaj klienta: Jan Kowalski, ACME Sp. z o.o., jan@acme.pl\n"
    "- dopisz komentarz do oferty <id>: oddzwonić jutro\n"
    "- sprawdź dostępność SKU N 202\n"
    "- statystyki pipeline"
)


def register(ctx):
    for schema, handler, toolset in _TOOLS:
        ctx.register_tool(name=schema["name"], toolset=toolset,
                          schema=schema, handler=handler)
    ctx.register_command("crm", handler=lambda raw: _HELP_TEXT,
                         description="Pomoc QuickQuote Pro CRM")
