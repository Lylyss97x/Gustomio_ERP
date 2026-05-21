# Gustomio Pipeline — Odoo Connector

Automatise la création de commandes et d'opportunités CRM dans Odoo à partir des commandes clients reçues par email ou PDF.

## Ce que ça fait

```
Email / PDF client
       │
       ▼
  JSON structuré  ──►  confidence ≥ 0.85 + AUTO_PUSH  ──►  Commande Odoo (sale.order)
  (parsé par IA)  ──►  sinon                           ──►  Lead CRM (review humaine)
```

**Exemple concret :**
- Un email de *Trattoria Roma* commande 4 barquettes de burrata
- L'IA parse l'email, calcule un score de confiance à 0.93
- Le connecteur crée automatiquement la commande `S00002` dans Odoo

## Stack

- Python 3.14
- Odoo 19 SaaS via XML-RPC (API key)
- `requests` + `python-dotenv`

## Installation (devs)

```bash
# 1. Cloner le repo
git clone https://github.com/Lylyss97x/Gustomio_ERP.git
cd Gustomio_ERP

# 2. Installer les dépendances
pip install requests python-dotenv

# 3. Configurer les accès Odoo
cp .env.example .env
# Remplir ODOO_API_KEY dans .env
# (Odoo > Paramètres > Mon profil > Sécurité > Clés API)
```

## Tester

```bash
# Connexion + routage complet (sale.order ET crm.lead)
python -m pipeline.odoo_connector
```

## Fonctions disponibles

| Fonction | Description |
|---|---|
| `authenticate()` | Connexion à Odoo, retourne uid |
| `get_or_create_customer(name)` | Trouve ou crée le client dans Odoo |
| `get_product_id(article_code)` | Trouve le produit par référence interne |
| `create_sale_order(order_json)` | Crée la commande + lignes → `S00002` |
| `create_crm_lead(order_json)` | Crée une opportunité CRM pour review |
| `route_order(order_json)` | Dispatche automatiquement selon la confiance |

## Format JSON attendu

```json
{
  "source": "email",
  "client_name": "Trattoria Roma",
  "delivery_address": "14 rue Lepic Paris 18e",
  "delivery_date": "2025-05-29",
  "items": [
    {
      "article_code": "ART-FR-001",
      "label_source": "burrata",
      "qty": 4,
      "unit": "barquette",
      "confidence_item": 0.95
    }
  ],
  "confidence_score": 0.93,
  "flags": [],
  "recommendation": "AUTO_PUSH"
}
```

## Logique de routage

| Condition | Résultat |
|---|---|
| `AUTO_PUSH` + confidence ≥ 0.85 + aucun flag | → Commande Odoo directe |
| Confidence < 0.85 ou flag ou `REVIEW` | → Lead CRM (revue humaine) |
