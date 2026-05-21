import imaplib

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
IMAP_USER = "gustomiofeshab@gmail.com"
IMAP_PASSWORD = "odpi rkvk dzrl uqds"

mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
mail.login(IMAP_USER, IMAP_PASSWORD)
print("Connexion IMAP OK")
mail.logout()