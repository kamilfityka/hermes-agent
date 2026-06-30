"""Tool schemas exposed to the model (descriptions drive tool selection)."""

CRM_SEARCH_CLIENTS = {
    "name": "crm_search_clients",
    "description": ("Wyszukaj klientów (firmy) w CRM QuickQuote Pro po nazwie lub NIP. "
                    "Użyj, gdy użytkownik pyta o klienta/firmę lub potrzebujesz jego ID."),
    "parameters": {"type": "object", "properties": {
        "name": {"type": "string", "description": "Fraza w nazwie (case-insensitive)."},
        "nip": {"type": "string", "description": "Dokładny NIP."},
        "limit": {"type": "integer", "default": 5}}},
}
CRM_GET_CLIENT = {
    "name": "crm_get_client",
    "description": "Pobierz szczegóły klienta wraz z kontaktami i ofertami. Wymaga ID.",
    "parameters": {"type": "object", "properties": {
        "id": {"type": "string", "description": "UUID klienta."}}, "required": ["id"]},
}
CRM_CREATE_CLIENT = {
    "name": "crm_create_client",
    "description": ("Utwórz nowego klienta (firmę). Odpowiednik 'dodaj leada' — "
                    "QuickQuote nie ma encji leada; szansę dodaje się potem jako ofertę."),
    "parameters": {"type": "object", "properties": {
        "name": {"type": "string"}, "company": {"type": "string"},
        "email": {"type": "string"}, "phone": {"type": "string"},
        "address": {"type": "string"}, "city": {"type": "string"},
        "nip": {"type": "string"}, "notes": {"type": "string"}},
        "required": ["name", "company", "email"]},
}
CRM_CREATE_CONTACT = {
    "name": "crm_create_contact",
    "description": "Dodaj osobę kontaktową do istniejącego klienta (wymaga client_id).",
    "parameters": {"type": "object", "properties": {
        "client_id": {"type": "string"}, "first_name": {"type": "string"},
        "last_name": {"type": "string"}, "email": {"type": "string"},
        "phone": {"type": "string"}, "position": {"type": "string"}},
        "required": ["client_id"]},
}
CRM_SEARCH_OFFERS = {
    "name": "crm_search_offers",
    "description": ("Wyszukaj oferty (wyceny). 'pokaż oferty klienta X', "
                    "'oferty w statusie wysłana'. Wyniki stronicowane (15/str.)."),
    "parameters": {"type": "object", "properties": {
        "query": {"type": "string"},
        "status": {"type": "string", "enum": ["draft", "sent", "accepted", "rejected", "expired"]},
        "client_id": {"type": "string"}, "assigned_to_id": {"type": "string"},
        "page": {"type": "integer", "default": 1}}},
}
CRM_GET_OFFER = {
    "name": "crm_get_offer",
    "description": "Pobierz szczegóły oferty z pozycjami i sumami. Wymaga ID.",
    "parameters": {"type": "object", "properties": {
        "id": {"type": "string"}}, "required": ["id"]},
}
CRM_CREATE_OFFER = {
    "name": "crm_create_offer",
    "description": ("Utwórz ofertę (wycenę = szansa sprzedażowa). Można podać pozycje (items). "
                    "Autor ustawiany automatycznie na konto serwisowe."),
    "parameters": {"type": "object", "properties": {
        "number": {"type": "string"}, "client_name": {"type": "string"},
        "client_id": {"type": "string"}, "contact_name": {"type": "string"},
        "valid_until": {"type": "string", "description": "ISO YYYY-MM-DD."},
        "language": {"type": "string", "enum": ["pl", "en", "de"], "default": "pl"},
        "notes": {"type": "string"},
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "product_name": {"type": "string"}, "product_sku": {"type": "string"},
            "quantity": {"type": "number"}, "unit_price": {"type": "number"},
            "discount": {"type": "number", "default": 0}},
            "required": ["product_name", "quantity", "unit_price"]}}},
        "required": ["number", "client_name"]},
}
CRM_UPDATE_OFFER = {
    "name": "crm_update_offer",
    "description": "Zaktualizuj ofertę: status, etap (sales_stage_id), handlowiec, follow-up.",
    "parameters": {"type": "object", "properties": {
        "id": {"type": "string"},
        "status": {"type": "string", "enum": ["draft", "sent", "accepted", "rejected", "expired"]},
        "sales_stage_id": {"type": "string"}, "assigned_to_id": {"type": "string"},
        "next_follow_up_at": {"type": "string"}, "notes": {"type": "string"}},
        "required": ["id"]},
}
CRM_CLOSE_OFFER = {
    "name": "crm_close_offer",
    "description": "Zamknij ofertę jako wygraną (won) lub przegraną (lost).",
    "parameters": {"type": "object", "properties": {
        "id": {"type": "string"},
        "result": {"type": "string", "enum": ["won", "lost"]},
        "reason": {"type": "string"}, "loss_reason_id": {"type": "string"}},
        "required": ["id", "result"]},
}
CRM_REOPEN_OFFER = {
    "name": "crm_reopen_offer",
    "description": "Ponownie otwórz zamkniętą ofertę.",
    "parameters": {"type": "object", "properties": {
        "id": {"type": "string"}}, "required": ["id"]},
}
CRM_ADD_COMMENT = {
    "name": "crm_add_comment",
    "description": "Dodaj komentarz/notatkę do oferty. Autor = konto serwisowe.",
    "parameters": {"type": "object", "properties": {
        "offer_id": {"type": "string"}, "content": {"type": "string"}},
        "required": ["offer_id", "content"]},
}
CRM_SEND_OFFER_EMAIL = {
    "name": "crm_send_offer_email",
    "description": ("Wyślij ofertę mailem. recipient='client' = REALNY mail do klienta "
                    "(używaj ostrożnie, po potwierdzeniu). recipient='me' = kopia do autora."),
    "parameters": {"type": "object", "properties": {
        "offer_id": {"type": "string"},
        "recipient": {"type": "string", "enum": ["client", "me"], "default": "me"}},
        "required": ["offer_id"]},
}
CRM_PIPELINE_STATS = {
    "name": "crm_pipeline_stats",
    "description": "Statystyki pipeline: wartości/liczby ofert na etapach, win-rate, czas zamknięcia.",
    "parameters": {"type": "object", "properties": {}},
}
CATALOG_SEARCH_SKUS = {
    "name": "catalog_search_skus",
    "description": ("Przeszukaj katalog SKU. Zwraca sku, nazwę, kolor, produkt L1, ilość i cennik. "
                    "Użyj przy pytaniach o produkt/cenę/dostępność lub szukaniu SKU do oferty."),
    "parameters": {"type": "object", "properties": {
        "query": {"type": "string"}, "limit": {"type": "integer", "default": 10}}},
}
CATALOG_GET_SKU = {
    "name": "catalog_get_sku",
    "description": "Szczegóły jednego SKU (cennik, ilość, kolor). SKU może zawierać ukośniki.",
    "parameters": {"type": "object", "properties": {
        "sku": {"type": "string"}}, "required": ["sku"]},
}
CATALOG_LIST_PRODUCTS = {
    "name": "catalog_list_products",
    "description": "Wylistuj produkty poziomu 1 (rodziny) z liczbą kolorów i SKU.",
    "parameters": {"type": "object", "properties": {
        "limit": {"type": "integer", "default": 20}}},
}
CATALOG_SET_SKU_QUANTITY = {
    "name": "catalog_set_sku_quantity",
    "description": "Ustaw stan magazynowy SKU. Zapis — wymaga ROLE_CATALOG_ADMIN.",
    "parameters": {"type": "object", "properties": {
        "sku": {"type": "string"}, "quantity": {"type": "integer"}},
        "required": ["sku", "quantity"]},
}
CATALOG_ADD_SKU = {
    "name": "catalog_add_sku",
    "description": "Dodaj nowe SKU do katalogu. Zapis — wymaga ROLE_CATALOG_ADMIN.",
    "parameters": {"type": "object", "properties": {
        "sku": {"type": "string"}, "name": {"type": "string"},
        "color_code_id": {"type": "string"}, "quantity": {"type": "integer", "default": 0}},
        "required": ["sku", "color_code_id"]},
}
