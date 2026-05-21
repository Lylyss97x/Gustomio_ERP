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

    prompt = f"""
Tu lis un email de commande de produits alimentaires et tu retournes uniquement un JSON valide.

Format exact à respecter :
{{
  "id": "{mail_id}",
  "from": "{from_email}",
  "liste produit": [
    {{
      "nom du produit": "string",
      "quantité": number
    }}
  ]
}}

Règles :
- Garde exactement la valeur de "id".
- Garde exactement la valeur de "from".
- Extrait uniquement les produits réellement présents dans l'email.
- Si aucun produit n'est trouvé, retourne "liste produit": [].
- Ne mets aucun texte autour.
- Ne mets pas de markdown.
- Retourne uniquement un JSON brut.

Email :
\"\"\"
{email_text}
\"\"\"
""".strip()

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": "Tu extrais des commandes email en JSON strict."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    content = response.choices[0].message.content.strip()

    # Nettoyage si jamais Groq renvoie ```json ... ```
    if content.startswith("```"):
        content = re.sub(r"^```json\\s*", "", content)
        content = re.sub(r"^```", "", content)
        content = re.sub(r"```$", "", content).strip()

    return json.loads(content)

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