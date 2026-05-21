import os
import re
import json
import imaplib
import email
import xmlrpc.client

from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from html import unescape

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# =========================================================
# CONFIG EMAIL / GROQ
# =========================================================
IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")
IMAP_FOLDER = "INBOX"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

catalogue_gustomio = [
    {"code": "BUR-01", "libelle": "Burrata des Pouilles 250g", "unite": "pièce"},
    {"code": "LIM-12", "libelle": "Limoncello de Sorrente 70cl", "unite": "bouteille"},
    {"code": "PAT-05", "libelle": "Pâtons à pizza surgelés x50", "unite": "carton"},
]

# =========================================================
# CONFIG ODOO XML-RPC
# =========================================================
ODOO_URL = os.getenv("ODOO_URL", "").rstrip("/")
ODOO_DB = os.getenv("ODOO_DB", "")
ODOO_USERNAME = os.getenv("ODOO_USERNAME", "")
ODOO_API_KEY = os.getenv("ODOO_API_KEY", "")

_uid = None
_common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
_models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")

# =========================================================
# EMAIL -> TEXT
# =========================================================
def html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</p>", "\n", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = unescape(html)
    html = re.sub(r"[ \t]+", " ", html)
    html = re.sub(r"\n\s*\n+", "\n", html)
    return html.strip()

def extract_email_text(raw_email: bytes) -> str:
    msg = BytesParser(policy=policy.default).parsebytes(raw_email)

    plain_part = msg.get_body(preferencelist=("plain",))
    if plain_part:
        return plain_part.get_content().strip()

    html_part = msg.get_body(preferencelist=("html",))
    if html_part:
        return html_to_text(html_part.get_content())

    if msg.get_content_type() == "text/plain":
        return msg.get_content().strip()

    if msg.get_content_type() == "text/html":
        return html_to_text(msg.get_content())

    return ""

# =========================================================
# IMAP
# =========================================================
def fetch_order_emails():
    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    mail.login(IMAP_USER, IMAP_PASSWORD)
    mail.select(IMAP_FOLDER)

    status, data = mail.search(None, '(SUBJECT "commande")')
    if status != "OK":
        mail.logout()
        return []

    emails = []

    for num in data[0].split():
        status, msg_data = mail.fetch(num, "(RFC822)")
        if status != "OK":
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email, policy=policy.default)

        emails.append({
            "message_num": num.decode(),
            "message_id": msg.get("Message-ID"),
            "subject": msg.get("Subject"),
            "from": msg.get("From"),
            "raw_email": raw_email,
        })

    mail.logout()
    return emails

# =========================================================
# GROQ
# =========================================================
def extract_order_with_groq(mail_id: str, from_email: str, email_text: str) -> dict:
    if not GROQ_API_KEY:
        raise ValueError("La variable d'environnement GROQ_API_KEY est absente.")

    client = Groq(api_key=GROQ_API_KEY)
    catalogue_json = json.dumps(catalogue_gustomio, ensure_ascii=False, indent=2)

    prompt = f"""
Tu es un assistant de prise de commande pour le distributeur GUSTOMIO.
Voici le contenu d'un email de commande laissé par un restaurateur.

Voici le SEUL catalogue de produits autorisé :
{catalogue_json}

Ta mission :
1. Identifie le client s'il se présente dans le texte. Sinon utilise null.
2. Extrais les produits demandés et trouve la correspondance exacte dans le catalogue en utilisant uniquement le champ "code".
3. Si un produit demandé n'existe pas dans le catalogue, est ambigu, ou si la quantité n'est pas claire, signale-le.

Tu dois OBLIGATOIREMENT répondre au format JSON strict avec cette structure exacte :
{{
    "nom_client": "nom ou null",
    "lignes_commande": [
        {{
            "code_article": "code du catalogue",
            "quantite_demandee": entier
        }}
    ],
    "statut": "OK",
    "raison_alerte": null
}}

Règles strictes :
- Utilise uniquement les codes présents dans le catalogue fourni.
- Ne jamais inventer de code article.
- Si un produit est absent du catalogue, ambigu, ou si une quantité est floue, mets :
  - "statut": "ALERTE"
  - "raison_alerte": "explication courte"
- Si tout est correct, mets :
  - "statut": "OK"
  - "raison_alerte": null
- Si aucun produit n'est détecté, retourne "lignes_commande": [] et "statut": "ALERTE".
- "quantite_demandee" doit être un entier.
- Ne retourne aucun texte hors JSON.
- Ne retourne pas de markdown.
- Ne retourne qu'un seul objet JSON.

Contenu de l'email :
\"\"\"
{email_text}
\"\"\"
""".strip()

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "Tu extrais des commandes GUSTOMIO en JSON strict à partir d'emails."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
    )

    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```json\s*", "", content)
        content = re.sub(r"^```", "", content)
        content = re.sub(r"```$", "", content).strip()

    data = json.loads(content)

    data["id_mail"] = mail_id
    data["from"] = from_email

    display_name, email_addr = parseaddr(from_email)
    if not data.get("nom_client"):
        data["nom_client"] = display_name if display_name else email_addr

    return data

# =========================================================
# ODOO XML-RPC
# =========================================================
def _kw(model: str, method: str, args=None, kwargs=None):
    return _models.execute_kw(
        ODOO_DB, _uid, ODOO_API_KEY,
        model, method,
        args or [],
        kwargs or {},
    )

def authenticate():
    global _uid
    uid = _common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_API_KEY, {})
    if not uid:
        raise RuntimeError("Authentification Odoo échouée.")
    _uid = uid
    return uid

def _ensure_auth():
    if _uid is None:
        authenticate()

def get_or_create_customer(client_name: str, email_from: str = "") -> int:
    _ensure_auth()

    if email_from:
        ids = _kw("res.partner", "search", [[["email", "=", email_from]]])
        if ids:
            return ids[0]

    ids = _kw("res.partner", "search", [[["name", "=", client_name]]])
    if ids:
        return ids[0]

    vals = {
        "name": client_name or email_from or "Client email",
        "customer_rank": 1,
    }
    if email_from:
        vals["email"] = email_from

    return _kw("res.partner", "create", [vals])

def get_product_id(article_code: str) -> int:
    _ensure_auth()
    ids = _kw("product.product", "search", [[["default_code", "=", article_code]]])
    if not ids:
        raise ValueError(f"Produit introuvable pour le code article : {article_code}")
    return ids[0]

def create_sale_order_from_groq(order_json: dict) -> str:
    _ensure_auth()

    _, email_addr = parseaddr(order_json.get("from", ""))
    partner_id = get_or_create_customer(order_json.get("nom_client"), email_addr)

    order_lines = []
    for item in order_json.get("lignes_commande", []):
        product_id = get_product_id(item["code_article"])
        order_lines.append((0, 0, {
            "product_id": product_id,
            "product_uom_qty": item["quantite_demandee"],
        }))

    order_vals = {
        "partner_id": partner_id,
        "client_order_ref": order_json.get("id_mail", ""),
        "note": f"Source: email\nAlerte IA: {order_json.get('raison_alerte') or 'Aucune'}",
        "order_line": order_lines,
    }

    order_id = _kw("sale.order", "create", [order_vals])
    order = _kw("sale.order", "read", [[order_id], ["name"]])
    return order[0]["name"]

def _get_first_crm_stage() -> int:
    _ensure_auth()
    stages = _kw(
        "crm.stage", "search_read",
        [[]],
        {"fields": ["id"], "limit": 1, "order": "sequence asc"},
    )
    if not stages:
        raise RuntimeError("Aucune étape CRM trouvée dans Odoo.")
    return stages[0]["id"]

def create_crm_lead_from_groq(order_json: dict) -> str:
    _ensure_auth()

    _, email_addr = parseaddr(order_json.get("from", ""))
    partner_id = get_or_create_customer(order_json.get("nom_client"), email_addr)
    stage_id = _get_first_crm_stage()

    items_summary = ", ".join(
        f"{i['code_article']} x{i['quantite_demandee']}"
        for i in order_json.get("lignes_commande", [])
    ) or "Aucun article reconnu"

    lead_name = f"{order_json.get('nom_client') or 'Client inconnu'} — {items_summary}"

    description_lines = [
        f"Source : email",
        f"Message-ID : {order_json.get('id_mail', '')}",
        f"From : {order_json.get('from', '')}",
        f"Statut IA : {order_json.get('statut', '')}",
        f"Raison alerte : {order_json.get('raison_alerte', '')}",
        f"Lignes reconnues : {json.dumps(order_json.get('lignes_commande', []), ensure_ascii=False)}",
    ]

    lead_id = _kw("crm.lead", "create", [{
        "name": lead_name,
        "partner_id": partner_id,
        "type": "opportunity",
        "stage_id": stage_id,
        "email_from": email_addr,
        "description": "\n".join(description_lines),
    }])

    lead = _kw("crm.lead", "read", [[lead_id], ["name"]])
    return lead[0]["name"]

def route_to_odoo(order_json: dict) -> dict:
    """
    Si OK + au moins une ligne => sale.order
    Sinon => crm.lead
    """
    status_ok = order_json.get("statut") == "OK"
    has_lines = bool(order_json.get("lignes_commande"))

    if status_ok and has_lines:
        ref = create_sale_order_from_groq(order_json)
        return {"type": "sale_order", "ref": ref}
    else:
        ref = create_crm_lead_from_groq(order_json)
        return {"type": "crm_lead", "ref": ref}

# =========================================================
# MAIN
# =========================================================
def main():
    authenticate()
    emails = fetch_order_emails()

    if not emails:
        print("Aucun email commande non lu.")
        return

    for item in emails:
        print("=" * 80)
        print("Sujet :", item["subject"])
        print("De    :", item["from"])

        email_text = extract_email_text(item["raw_email"])
        print("\n--- TEXTE EXTRAIT ---")
        print(email_text[:2000])

        try:
            order_json = extract_order_with_groq(
                mail_id=item["message_id"] or item["message_num"],
                from_email=item["from"],
                email_text=email_text,
            )

            print("\n--- JSON EXTRAIT ---")
            print(json.dumps(order_json, ensure_ascii=False, indent=2))

            result = route_to_odoo(order_json)
            print("\n--- ENVOI ODOO ---")
            print(json.dumps(result, ensure_ascii=False, indent=2))

        except Exception as e:
            print("\nErreur pipeline :", str(e))

if __name__ == "__main__":
    main()