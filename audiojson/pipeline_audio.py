import os
import json
from dotenv import load_dotenv
from groq import Groq

# --- 1. CONFIGURATION INITIALE ---
load_dotenv()
client = Groq()

CHEMIN_AUDIO = "audiojson/test-final.m4a"
CHEMIN_CATALOGUE = "audiojson/catalogue.json"

print(" Étape 1 : Transcription de l'audio...")

# Vérification que le fichier audio existe bien
if not os.path.exists(CHEMIN_AUDIO):
    print(f" Erreur : Le fichier audio '{CHEMIN_AUDIO}' est introuvable.")
    exit()

# --- 2. TRANSCRIPTION (Whisper) ---
try:
    with open(CHEMIN_AUDIO, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=audio_file
        )
    texte_transcrit = transcription.text
    print(" Transcription réussie :")
    print(f"   \"{texte_transcrit}\"\n")
except Exception as e:
    print(f" Erreur lors de la transcription : {e}")
    exit()

# --- 3. CHARGEMENT DU CATALOGUE ---
print(" Étape 2 : Chargement du catalogue...")
try:
    with open(CHEMIN_CATALOGUE, "r", encoding="utf-8") as fichier_catalogue:
        catalogue_gustomio = json.load(fichier_catalogue)
    print(" Catalogue chargé avec succès.\n")
except FileNotFoundError:
    print(f" Erreur : Le fichier '{CHEMIN_CATALOGUE}' est introuvable.")
    exit()

# --- 4. ANALYSE ET EXTRACTION (Llama 3) ---
print(" Étape 3 : Analyse et extraction de la commande...")
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

    # Récupération et affichage du résultat final
    resultat_json_str = reponse.choices[0].message.content
    resultat_dict = json.loads(resultat_json_str)

    print("\n --- RÉSULTAT STRUCTURÉ --- ")
    print(json.dumps(resultat_dict, indent=4, ensure_ascii=False))

except Exception as e:
    print(f" Erreur lors de l'analyse IA : {e}")