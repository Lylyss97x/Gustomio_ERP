import os
import re
import json
import imaplib
import email
from email import policy
from email.parser import BytesParser
from html import unescape
from groq import Groq
from dotenv import load_dotenv
from email.utils import parseaddr
load_dotenv()

# =========================
# CONFIG
# =========================
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
    {"code": "PAT-05", "libelle": "Pâtons à pizza surgelés x50", "unite": "carton"}
]



# =========================
# EMAIL -> TEXT
# =========================
def html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", html)
    html = re.sub(r"(?i)<br\\s*/?>", "\n", html)
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

# =========================
# IMAP
# =========================
def fetch_unread_emails():
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
            "raw_email": raw_email
        })

    mail.logout()
    return emails

# =========================
# GROQ -> JSON
# =========================
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
1. Identifie le client s'il se présente. Sinon utilise null.
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
        temperature=0
    )

    content = response.choices[0].message.content.strip()

    if content.startswith("```"):
        content = re.sub(r"^```json\\s*", "", content)
        content = re.sub(r"^```", "", content)
        content = re.sub(r"```$", "", content).strip()

    data = json.loads(content)

    # Réinjection des métadonnées fiables côté code
    data["id_mail"] = mail_id
    data["from"] = from_email

    display_name, email_addr = parseaddr(from_email)

    if not data.get("nom_client"):
        data["nom_client"] = display_name if display_name else None

    return data

# =========================
# MAIN
# =========================
def main():
    emails = fetch_unread_emails()

    if not emails:
        print("Aucun email non lu.")
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
                email_text=email_text
            )
            print("\n--- JSON EXTRAIT ---")
            print(json.dumps(order_json, ensure_ascii=False, indent=2))
        except Exception as e:
            print("\nErreur extraction IA :", str(e))
if __name__ == "__main__":
    main()