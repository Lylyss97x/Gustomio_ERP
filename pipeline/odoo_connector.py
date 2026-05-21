import os
import xmlrpc.client

from dotenv import load_dotenv

load_dotenv()

ODOO_URL = os.getenv("ODOO_URL", "").rstrip("/")
ODOO_DB = os.getenv("ODOO_DB", "")
ODOO_USERNAME = os.getenv("ODOO_USERNAME", "")
ODOO_API_KEY = os.getenv("ODOO_API_KEY", "")

_uid: int | None = None
_common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
_models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")


# ── Transport ──────────────────────────────────────────────────────────────────

def _kw(model: str, method: str, args=None, kwargs=None):
    return _models.execute_kw(
        ODOO_DB, _uid, ODOO_API_KEY,
        model, method,
        args or [],
        kwargs or {},
    )


def _ensure_auth():
    if _uid is None:
        authenticate()


# ── Public API ─────────────────────────────────────────────────────────────────

def authenticate() -> int:
    """Authenticate via XML-RPC with API key and return the user id."""
    global _uid
    uid = _common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_API_KEY, {})
    if not uid:
        raise RuntimeError(
            "Authentification échouée — vérifiez ODOO_USERNAME / ODOO_API_KEY dans .env"
        )
    _uid = uid
    return uid


def get_or_create_customer(client_name: str) -> int:
    """Return existing res.partner id or create a new customer record."""
    _ensure_auth()
    ids = _kw("res.partner", "search", [[["name", "=", client_name]]])
    if ids:
        return ids[0]
    return _kw("res.partner", "create", [{"name": client_name, "customer_rank": 1}])


def get_product_id(article_code: str) -> int:
    """Return product.product id matching the internal reference (default_code)."""
    _ensure_auth()
    ids = _kw("product.product", "search", [[["default_code", "=", article_code]]])
    if not ids:
        raise ValueError(f"Produit introuvable pour le code article : {article_code}")
    return ids[0]


def create_sale_order(order_json: dict) -> str:
    """
    Create a sale.order + lines from the pipeline JSON.
    Returns the Odoo order name e.g. 'SO/2025/0001'.
    """
    authenticate()

    partner_id = get_or_create_customer(order_json["client_name"])

    delivery = order_json.get("delivery_address", "")
    source = order_json.get("source", "")
    note_lines = []
    if delivery:
        note_lines.append(f"Livraison : {delivery}")
    if source:
        note_lines.append(f"Source : {source}")

    order_vals: dict = {
        "partner_id": partner_id,
        "note": "\n".join(note_lines),
    }
    if order_json.get("delivery_date"):
        # Odoo expects 'YYYY-MM-DD HH:MM:SS' in the commitment_date field
        order_vals["commitment_date"] = f"{order_json['delivery_date']} 08:00:00"

    order_id: int = _kw("sale.order", "create", [order_vals])

    for item in order_json.get("items", []):
        product_id = get_product_id(item["article_code"])
        _kw("sale.order.line", "create", [{
            "order_id": order_id,
            "product_id": product_id,
            "product_uom_qty": item["qty"],
            "name": item.get("label_source", ""),
        }])

    order = _kw("sale.order", "read", [[order_id], ["name"]])
    return order[0]["name"]


def _get_first_crm_stage() -> int:
    """Return the id of the first stage in the CRM pipeline."""
    stages = _kw(
        "crm.stage", "search_read",
        [[]],
        {"fields": ["id"], "limit": 1, "order": "sequence asc"},
    )
    if not stages:
        raise RuntimeError("Aucune étape CRM trouvée — vérifiez le module CRM Odoo")
    return stages[0]["id"]


def create_crm_lead(order_json: dict) -> str:
    """
    Create a CRM opportunity for human review.
    Returns the lead name e.g. 'Trattoria Roma — burrata x4'.
    """
    authenticate()

    partner_id = get_or_create_customer(order_json["client_name"])
    stage_id = _get_first_crm_stage()

    items_summary = ", ".join(
        f"{i['label_source']} x{i['qty']}" for i in order_json.get("items", [])
    )
    lead_name = f"{order_json['client_name']} — {items_summary}"

    description_lines = [
        f"Source : {order_json.get('source', '')}",
        f"Livraison : {order_json.get('delivery_address', '')}",
        f"Date souhaitée : {order_json.get('delivery_date', '')}",
        f"Confidence : {order_json.get('confidence_score', 0):.0%}",
    ]
    if order_json.get("flags"):
        description_lines.append(f"Flags : {', '.join(order_json['flags'])}")

    lead_id: int = _kw("crm.lead", "create", [{
        "name": lead_name,
        "partner_id": partner_id,
        "type": "opportunity",
        "stage_id": stage_id,
        "description": "\n".join(description_lines),
    }])

    lead = _kw("crm.lead", "read", [[lead_id], ["name"]])
    return lead[0]["name"]


CONFIDENCE_THRESHOLD = 0.85


def route_order(order_json: dict) -> dict:
    """
    Route the order to sale.order or crm.lead based on recommendation and confidence.

    Returns {"type": "sale_order"|"crm_lead", "ref": "<name>"}
    """
    auto_push = order_json.get("recommendation") == "AUTO_PUSH"
    confident = float(order_json.get("confidence_score", 0)) >= CONFIDENCE_THRESHOLD
    has_flags = bool(order_json.get("flags"))

    if auto_push and confident and not has_flags:
        ref = create_sale_order(order_json)
        return {"type": "sale_order", "ref": ref}
    else:
        ref = create_crm_lead(order_json)
        return {"type": "crm_lead", "ref": ref}


def test_connection() -> str:
    """Verify credentials and return a human-readable status line."""
    uid = authenticate()
    version_info = _common.version()
    odoo_version = version_info.get("server_version", "?")
    return f"Connexion OK — uid={uid}, Odoo {odoo_version}, db={ODOO_DB}"


# ── CLI quick-test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(test_connection())

    # AUTO_PUSH + confidence haute → sale.order direct
    high_confidence = {
        "source": "email",
        "client_name": "Trattoria Roma",
        "delivery_address": "14 rue Lepic Paris 18e",
        "delivery_date": "2025-05-29",
        "items": [{"article_code": "ART-FR-001", "label_source": "burrata", "qty": 4, "unit": "barquette", "confidence_item": 0.95}],
        "confidence_score": 0.93,
        "flags": [],
        "recommendation": "AUTO_PUSH",
    }

    # Confidence faible → crm.lead pour review humaine
    low_confidence = {
        "source": "email",
        "client_name": "Osteria Belmondo",
        "delivery_address": "3 rue de Rivoli Paris 1er",
        "delivery_date": "2025-05-30",
        "items": [{"article_code": "ART-FR-002", "label_source": "mozzarella", "qty": 2, "unit": "kg", "confidence_item": 0.60}],
        "confidence_score": 0.61,
        "flags": ["LOW_CONFIDENCE"],
        "recommendation": "REVIEW",
    }

    for sample in [high_confidence, low_confidence]:
        result = route_order(sample)
        icon = "📦" if result["type"] == "sale_order" else "🔍"
        print(f"{icon}  [{result['type']}] {result['ref']}")
