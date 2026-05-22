import os
import json
import xmlrpc.client
from dotenv import load_dotenv
from groq import Groq

# --- 1. CONFIGURATION ET ENVIRONNEMENT ---
# Cherche automatiquement le .env à la racine du projet
load_dotenv()

client = Groq()

CHEMIN_AUDIO = "audiojson/test-final.m4a"
CHEMIN_CATALOGUE = "audiojson/catalogue.json"

# Variables Odoo
ODOO_URL = os.getenv("ODOO_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USERNAME = os.getenv("ODOO_USERNAME")
ODOO_API_KEY = os.getenv("ODOO_API_KEY")

print("Étape 1 : Transcription de l'audio...")
if not os.path.exists(CHEMIN_AUDIO):
    print(f"Erreur : Le fichier audio '{CHEMIN_AUDIO}' est introuvable.")
    exit()

# --- 2. TRANSCRIPTION (Whisper) ---
try:
    with open(CHEMIN_AUDIO, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=audio_file
        )
    texte_transcrit = transcription.text
    print(f"Transcription réussie : \"{texte_transcrit}\"\n")
except Exception as e:
    print(f"Erreur lors de la transcription : {e}")
    exit()

# --- 3. CHARGEMENT DU CATALOGUE ---
print("Étape 2 : Chargement du catalogue...")
try:
    with open(CHEMIN_CATALOGUE, "r", encoding="utf-8") as fichier_catalogue:
        catalogue_gustomio = json.load(fichier_catalogue)
    print("Catalogue chargé avec succès.\n")
except FileNotFoundError:
    print(f"Erreur : Le fichier '{CHEMIN_CATALOGUE}' est introuvable.")
    exit()

# --- 4. ANALYSE ET EXTRACTION (Llama 3) ---
print("Étape 3 : Analyse de la commande par l'IA...")
prompt_systeme = f"""
Tu es un assistant de prise de commande pour le distributeur GUSTOMIO.
Voici la transcription d'un message vocal laissé par un restaurateur.

Voici le SEUL catalogue de produits autorisé :
{json.dumps(catalogue_gustomio, ensure_ascii=False)}

Ta mission :
1. Identifie le client s'il se présente.
2. Extrais les produits demandés et trouve la correspondance exacte dans le catalogue (utilise le champ "code").
3. Si un produit demandé n'existe pas ou est ambigu, signale-le.

Tu dois OBLIGATOIREMENT répondre au format JSON strict avec cette structure exacte :
{{
    "nom_client": "nom ou null",
    "lignes_commande": [
        {{
            "code_article": "code du catalogue",
            "quantite_demandee": entier
        }}
    ],
    "statut": "OK" (si tout a été trouvé) ou "ALERTE" (si un produit manque au catalogue, ou quantité floue),
    "raison_alerte": "explication courte ou null"
}}
"""

try:
    reponse = client.chat.completions.create(
        model="llama-3.3-70b-versatile", 
        messages=[
            {"role": "system", "content": prompt_systeme},
            {"role": "user", "content": f"Texte à analyser : {texte_transcrit}"}
        ],
        response_format={"type": "json_object"}, 
        temperature=0 
    )
    resultat_dict = json.loads(reponse.choices[0].message.content)
    print("Analyse terminée.\n")
except Exception as e:
    print(f"Erreur lors de l'analyse IA : {e}")
    exit()

# --- 5. CONNEXION ET INJECTION DANS ODOO ---
print("Étape 4 : Traitement vers l'ERP Odoo...")

# Sécurité : on vérifie que la Clé API a bien été trouvée
if not all([ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY]):
    print("Erreur : Il manque des identifiants Odoo dans le fichier .env !")
    print(f"DEBUG -> URL: {ODOO_URL}, DB: {ODOO_DB}, USERNAME: {ODOO_USERNAME}, API_KEY: {'***' if ODOO_API_KEY else None}")
    exit()

if resultat_dict.get("statut") == "ALERTE":
    print("ALERTE IA : La commande nécessite une vérification humaine.")
    print(f"Raison : {resultat_dict.get('raison_alerte')}")
    print("Envoi vers Odoo annulé.")
else:
    try:
        # Authentification XML-RPC avec la clé API
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common', allow_none=True)
        uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_API_KEY, {})
        
        if not uid:
            print("Erreur : Identifiants Odoo incorrects ou base de données introuvable.")
            exit()
            
        models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object', allow_none=True)
        
        # A. Création de l'entête de la commande (Sale Order)
        partenaire_id_mvp = 10 # ID du client par défaut pour le test
        nom_client = resultat_dict.get('nom_client')
        titre_commande = f"Commande vocale : {nom_client}" if nom_client else "Commande vocale : Inconnu"
        
        order_id = models.execute_kw(ODOO_DB, uid, ODOO_API_KEY, 'sale.order', 'create', [{
            'partner_id': partenaire_id_mvp,
            'client_order_ref': titre_commande
        }])
        
        print(f"Commande créée dans Odoo (ID: {order_id})")

        # B. Ajout des lignes de commande
        for ligne in resultat_dict.get('lignes_commande', []):
            code_article = ligne.get('code_article')
            quantite = ligne.get('quantite_demandee')
            
            # On cherche l'ID interne du produit dans Odoo
            product_ids = models.execute_kw(ODOO_DB, uid, ODOO_API_KEY, 'product.product', 'search', [[
                ('default_code', '=', code_article)
            ]])
            
            # CREATION A LA VOLÉE SI LE PRODUIT N'EXISTE PAS
            if not product_ids:
                print(f"   Le code {code_article} n'existe pas. Création à la volée dans Odoo...")
                nouveau_produit_id = models.execute_kw(ODOO_DB, uid, ODOO_API_KEY, 'product.product', 'create', [{
                    'name': f"Produit importé - {code_article}", 
                    'default_code': code_article,
                    'type': 'consu' # Permet d'éviter les soucis de stock bloquants
                }])
                product_ids = [nouveau_produit_id]
            
            # Ajout de la ligne avec le product_id trouvé ou nouvellement créé
            models.execute_kw(ODOO_DB, uid, ODOO_API_KEY, 'sale.order.line', 'create', [{
                'order_id': order_id,
                'product_id': product_ids[0],
                'product_uom_qty': float(quantite) if quantite else 1.0,
            }])
            print(f"   Ligne ajoutée avec succès : {quantite}x [{code_article}]")
        
        print("\nSUCCÈS : Le pipeline Zero-Saisie est terminé avec succès !")

    except Exception as e:
        print(f"Erreur lors de la communication avec Odoo : {e}")