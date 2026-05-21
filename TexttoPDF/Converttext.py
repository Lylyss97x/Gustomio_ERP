"""
GUSTOMIO — Commande interactive depuis le catalogue officiel 2026
Sélection par catégorie → produit → quantité → génération JSON
"""
import re
import json
from datetime import datetime, timedelta

# ══════════════════════════════════════════════
#  CATALOGUE GUSTOMIO (extrait du PDF officiel)
# ══════════════════════════════════════════════

CATALOGUE = {
    "01 - CRÉMERIE / BEURRE": [
        {"code": "61194",     "libelle": "Beurre doux 250 g",                        "uv": "Pièce"},
        {"code": "61256",     "libelle": "Beurre doux Verneuil 250 g",               "uv": "Pièce"},
        {"code": "V4640",     "libelle": "Beurre demi-sel 250 g",                    "uv": "Pièce"},
        {"code": "61257",     "libelle": "Beurre demi-sel Verneuil 250 g",           "uv": "Pièce"},
        {"code": "082043",    "libelle": "Beurre doux 82% 25 kg",                    "uv": "Pièce"},
        {"code": "61448",     "libelle": "Beurre doux motte 10 kg",                  "uv": "Pièce"},
        {"code": "168",       "libelle": "Beurre sec doux AOP Tourage Montaigu 2 kg","uv": "Pièce"},
        {"code": "62573",     "libelle": "Beurre doux tourage AOP Isigny 1 kg",      "uv": "Pièce"},
        {"code": "33700000",  "libelle": "Beurre demi-sel motte AOP Isigny 5 kg",    "uv": "Pièce"},
        {"code": "L0272",     "libelle": "Micro beurre doux AOP Isigny 10g x 100",   "uv": "Pièce"},
        {"code": "2088",      "libelle": "Beurre doux AOP recharge Isigny 25g x 47", "uv": "Colis"},
        {"code": "62174",     "libelle": "Beurre demi-sel Echiré 20g x 20",          "uv": "Pièce"},
    ],
    "01 - CRÉMERIE / CRÈME": [
        {"code": "61409",     "libelle": "Crème Végétop Debic 33% 1 L",              "uv": "Litre"},
        {"code": "61343",     "libelle": "Crème Culinaire Végétop Debic 15% 1 L",   "uv": "Litre"},
        {"code": "61662",     "libelle": "Crème Chanty Duo Risso 1 L",               "uv": "Litre"},
        {"code": "61190",     "libelle": "Crème fouettée vanille Isigny Aerosol 500g","uv": "Pièce"},
        {"code": "31410006",  "libelle": "Crème fraîche épaisse 30% 1 L",            "uv": "Litre"},
        {"code": "M5823",     "libelle": "Crème fraiche épaisse Isigny 40% 5 L",     "uv": "Pièce"},
        {"code": "61298",     "libelle": "Crème fraiche épaisse AOP Isigny 35% 500g","uv": "Pièce"},
        {"code": "291",       "libelle": "Crème entière liquide Montaigu 35% 1 L",   "uv": "Litre"},
        {"code": "61812",     "libelle": "Crème gastronomique President pro 35% 1 L","uv": "Litre"},
        {"code": "2013",      "libelle": "Panna Italienne 37% 1 L",                  "uv": "Litre"},
    ],
    "01 - CRÉMERIE / YAOURT & FROMAGE BLANC": [
        {"code": "61687",     "libelle": "Yaourt grec Kri Kri 1 kg",                 "uv": "Pièce"},
        {"code": "61948",     "libelle": "Yaourt brassé nature Ferme de l'Abbaye 4x125g","uv":"Pièce"},
        {"code": "61909",     "libelle": "Yaourt sur lit myrtille Ferme Abbaye 4x125g","uv":"Pièce"},
        {"code": "61911",     "libelle": "Yaourt sur lit fraise Ferme Abbaye 4x125g","uv": "Pièce"},
        {"code": "26230006",  "libelle": "Fromage blanc 20% 1 L",                    "uv": "Pièce"},
    ],
    "01 - CRÉMERIE / LAIT & OEUF": [
        {"code": "61809",     "libelle": "Lait entier frais 1 L",                    "uv": "Litre"},
        {"code": "C6813",     "libelle": "Lait demi-écrémé UHT 1 L",                "uv": "Litre"},
        {"code": "60634",     "libelle": "Lait entier UHT 1 L",                      "uv": "Litre"},
        {"code": "18011",     "libelle": "Lait de soja barista Alpro 1 L",           "uv": "Litre"},
        {"code": "62257",     "libelle": "Lait d'avoine barista Alpro 1 L",          "uv": "Litre"},
        {"code": "LEU30M",    "libelle": "Oeufs moyens std x 30",                    "uv": "Pièce"},
        {"code": "LEU180M",   "libelle": "Oeufs moyens std x 180",                   "uv": "Colis"},
        {"code": "60832",     "libelle": "Oeufs moyens bio x 90",                    "uv": "Colis"},
        {"code": "61607",     "libelle": "Oeufs entier liquide Liot 1 kg",           "uv": "Pièce"},
        {"code": "61609",     "libelle": "Oeufs durs écalés x 70",                   "uv": "Pièce"},
    ],
    "02 - FROMAGE / Brebis & Chèvre": [
        {"code": "S0512",     "libelle": "Ossau iraty AOP ~ 4 kg",                   "uv": "Kilo"},
        {"code": "A3790",     "libelle": "Roquefort ~ 1,3 kg",                       "uv": "Kilo"},
        {"code": "5000",      "libelle": "Brisures de roquefort 1 kg",               "uv": "Kilo"},
        {"code": "62266",     "libelle": "Palet de chèvre spécial cuisson 20g x 20", "uv": "Colis"},
        {"code": "72990006",  "libelle": "Sainte maure cendré Touraine AOP 250 g",   "uv": "Pièce"},
        {"code": "38020",     "libelle": "Rocamadour AOP 35g x 20",                  "uv": "Colis"},
        {"code": "503",       "libelle": "Chèvre frais seau 2 kg",                   "uv": "Pièce"},
    ],
    "02 - FROMAGE / Vache": [
        {"code": "R7907",     "libelle": "Brie de Meaux AOP ~ 3 kg",                 "uv": "Kilo"},
        {"code": "47060030",  "libelle": "Camembert pasteurisé 240 g",               "uv": "Pièce"},
        {"code": "3338026",   "libelle": "Camembert au lait cru Isigny 250 g",       "uv": "Pièce"},
        {"code": "V0602",     "libelle": "Comté doux 6 mois AOP ~ 3,3 kg",          "uv": "Kilo"},
        {"code": "1019",      "libelle": "Comté affiné 18/20 mois AOP ~ 4,5 kg",    "uv": "Kilo"},
        {"code": "61355",     "libelle": "Comté affiné 24 mois AOP ~ 4,5 kg",       "uv": "Kilo"},
        {"code": "342024",    "libelle": "Reblochon fruitier AOP",                   "uv": "Pièce"},
        {"code": "M11602",    "libelle": "Raclette meule ~ 5 kg",                    "uv": "Kilo"},
        {"code": "62504",     "libelle": "Cantal jeune AOP bloc ~ 2,5 kg",          "uv": "Kilo"},
        {"code": "L2055",     "libelle": "Bleu d'Auvergne AOP ~ 1,2 kg",            "uv": "Kilo"},
        {"code": "B9213",     "libelle": "Beaufort AOP ~ 2 kg",                      "uv": "Kilo"},
        {"code": "61820",     "libelle": "Epoisse ~ 900 g",                          "uv": "Kilo"},
    ],
    "02 - FROMAGE / Râpé & Tranché": [
        {"code": "CE93",      "libelle": "Emmental râpé européen 1 kg",              "uv": "Kilo"},
        {"code": "CE94",      "libelle": "Emmental râpé français extra fin 1 kg",    "uv": "Pièce"},
        {"code": "61039",     "libelle": "Comté râpé AOP 5 kg",                      "uv": "Pièce"},
        {"code": "62260",     "libelle": "Cantal jeune râpé AOP 2 kg",               "uv": "Pièce"},
        {"code": "TE54",      "libelle": "Emmental tranché 66 tranches 1 kg",        "uv": "Pièce"},
        {"code": "128109",    "libelle": "Raclette tranchée 400 g",                  "uv": "Pièce"},
    ],
    "02 - FROMAGE / Étranger & Tartiner": [
        {"code": "61775",     "libelle": "Halloumi chypre Simos 750 g",              "uv": "Pièce"},
        {"code": "61685",     "libelle": "Feta brebis/chèvre Simos 2 kg",           "uv": "Pièce"},
        {"code": "60570",     "libelle": "Feta en dés Simos 900 g",                  "uv": "Pièce"},
        {"code": "62508",     "libelle": "Manchego AOP ~ 3 kg",                      "uv": "Kilo"},
        {"code": "CR35",      "libelle": "Cream cheese Hochland 3,5 kg",             "uv": "Pièce"},
        {"code": "61628",     "libelle": "Philadelphia 1,65 kg",                     "uv": "Pièce"},
        {"code": "SM6",       "libelle": "Saint-Môret 1 kg",                         "uv": "Pièce"},
    ],
    "03 - FROMAGE ITALIEN / Burrata & Mozzarella": [
        {"code": "61177",     "libelle": "Burrata pasteurisée 125g x 2",             "uv": "Pièce"},
        {"code": "2051",      "libelle": "Burrata di bufala 125 g",                  "uv": "Pièce"},
        {"code": "60824",     "libelle": "Burrata à la truffe 125 g",                "uv": "Pièce"},
        {"code": "61238",     "libelle": "Stracciatella pasteurisée 250 g",          "uv": "Pièce"},
        {"code": "272",       "libelle": "Mozzarella di bufala DOP 125g x 8",        "uv": "Pièce"},
        {"code": "900",       "libelle": "Mozzarella di bufala à la truffe 125 g",   "uv": "Pièce"},
        {"code": "62545",     "libelle": "Mozzarella bille 10g x 100",               "uv": "Kilo"},
        {"code": "62549",     "libelle": "Mozzarella bloc 1 kg",                     "uv": "Kilo"},
        {"code": "60759",     "libelle": "Mozzarella cubettata 3 kg",                "uv": "Pièce"},
        {"code": "62547",     "libelle": "Mozzarella julienne 3 kg",                 "uv": "Pièce"},
    ],
    "03 - FROMAGE ITALIEN / Parmigiano, Grana, Pecorino": [
        {"code": "62558",     "libelle": "Parmigiano reggiano DOP bloc ~ 1 kg",      "uv": "Kilo"},
        {"code": "62559",     "libelle": "Parmigiano reggiano DOP râpé 1 kg",        "uv": "Pièce"},
        {"code": "62557",     "libelle": "Parmigiano reggiano DOP copeaux 500 g",    "uv": "Pièce"},
        {"code": "20",        "libelle": "Grana padano DOP bloc ~ 1 kg",             "uv": "Kilo"},
        {"code": "62561",     "libelle": "Grana padano DOP râpé 1 kg",               "uv": "Pièce"},
        {"code": "62543",     "libelle": "Pecorino romano DOP ~ 4 kg",               "uv": "Kilo"},
        {"code": "61236",     "libelle": "Pecorino romano DOP râpé 1 kg",            "uv": "Pièce"},
    ],
    "03 - FROMAGE ITALIEN / Ricotta & Mascarpone": [
        {"code": "62541",     "libelle": "Ricotta 250 g",                             "uv": "Pièce"},
        {"code": "62419",     "libelle": "Ricotta 1,5 kg",                            "uv": "Pièce"},
        {"code": "61497",     "libelle": "Ricotta di bufala 200 g",                   "uv": "Pièce"},
        {"code": "60315",     "libelle": "Mascarpone Virgilio 41% 250 g",             "uv": "Pièce"},
        {"code": "62556",     "libelle": "Mascarpone Virgilio 41% 2 kg",              "uv": "Pièce"},
        {"code": "60755",     "libelle": "Mascarpone Galbani 41% 2 kg",               "uv": "Pièce"},
    ],
    "04 - CHARCUTERIE / Jambon & Saucisson": [
        {"code": "62018",     "libelle": "Demi jambon cuit supérieur Le Mistral ~ 3,5 kg","uv":"Kilo"},
        {"code": "60742",     "libelle": "Jambon cuit supérieur DD Grancoeur ~ 6,5 kg","uv":"Kilo"},
        {"code": "61760",     "libelle": "Jambon cuit supérieur tranché 50g x 20",   "uv": "Pièce"},
        {"code": "5256",      "libelle": "Cecina ~ 2,5 kg",                           "uv": "Kilo"},
        {"code": "60993",     "libelle": "Jambon Serrano reserva désossé ~ 5 kg",    "uv": "Kilo"},
        {"code": "19328",     "libelle": "Rosette maison Calixte ~ 2,5 kg",          "uv": "Kilo"},
        {"code": "471000",    "libelle": "Saucisson sec long d'Auvergne 850 g",      "uv": "Kilo"},
        {"code": "29299",     "libelle": "Rosette tranchée Aoste x 48 500 g",        "uv": "Pièce"},
    ],
    "04 - CHARCUTERIE / Chorizo, Lardon, Bacon": [
        {"code": "61266",     "libelle": "Pepperoni piquant tranche Aoste 1 kg",     "uv": "Pièce"},
        {"code": "61637",     "libelle": "Chorizo tranche 1 kg",                     "uv": "Pièce"},
        {"code": "628",       "libelle": "Chorizo gran doblon fort ~ 2 kg",          "uv": "Kilo"},
        {"code": "108",       "libelle": "Chorizo gran doblon doux ~ 2 kg",          "uv": "Kilo"},
        {"code": "19192",     "libelle": "Bacon fumé 1/2 ~ 1,7 kg",                  "uv": "Kilo"},
        {"code": "21163",     "libelle": "Bacon fumé 40 tranches 500 g",             "uv": "Pièce"},
        {"code": "71426",     "libelle": "Lardons crus fumés supérieurs 1 kg",       "uv": "Pièce"},
        {"code": "71228",     "libelle": "Lardons fumés allumettes cru 5x5 1 kg",    "uv": "Pièce"},
        {"code": "61418",     "libelle": "Poitrine fumée tranchée 25g 1 kg",         "uv": "Pièce"},
    ],
    "04 - CHARCUTERIE / Pâté & Foie gras": [
        {"code": "70720",     "libelle": "Paté de campagne ~ 1,4 kg",                "uv": "Kilo"},
        {"code": "710321",    "libelle": "Rillette traditionnelle pain ~ 1,6 kg",    "uv": "Kilo"},
        {"code": "62071",     "libelle": "Terrine de foie gras 1 kg",                "uv": "Kilo"},
        {"code": "590023",    "libelle": "Pâté campagne d'Auvergne pur porc 350 g",  "uv": "Pièce"},
    ],
    "05 - CHARCUTERIE ITALIENNE / Salame & Guanciale": [
        {"code": "10537",     "libelle": "Salame al finocchio ~ 3 kg",               "uv": "Kilo"},
        {"code": "60224",     "libelle": "Salame Milano ~ 3,8 kg",                   "uv": "Kilo"},
        {"code": "2080",      "libelle": "Salame Napoli ~ 1,8 kg",                   "uv": "Kilo"},
        {"code": "60621",     "libelle": "Nduja di Spilinga ~ 540 g",                "uv": "Kilo"},
        {"code": "61762",     "libelle": "Guanciale San Carlo ~ 1,4 kg",             "uv": "Kilo"},
        {"code": "3515",      "libelle": "Pancetta coppata ~ 2 kg",                  "uv": "Kilo"},
        {"code": "61412",     "libelle": "Speck Senfter IGP ~ 2,5 kg",               "uv": "Kilo"},
        {"code": "3521",      "libelle": "Bresaola punta d'anca IGP Mottolini ~ 2 kg","uv":"Kilo"},
    ],
    "05 - CHARCUTERIE ITALIENNE / Jambon & Mortadella": [
        {"code": "10580",     "libelle": "Jambon de Parme DOP Leoncini 18 mois ~ 8 kg","uv":"Kilo"},
        {"code": "11522",     "libelle": "Jambon de Parme DOP Zarotti 18 mois ~ 7 kg","uv":"Kilo"},
        {"code": "61246",     "libelle": "Jambon de Parme DOP Zarotti 24 mois ~ 8 kg","uv":"Kilo"},
        {"code": "10583",     "libelle": "Jambon San Daniele DOP 16 mois ~ 8 kg",    "uv": "Kilo"},
        {"code": "10677",     "libelle": "Mortadella Bologna IGP pistache ~ 3 kg",   "uv": "Kilo"},
        {"code": "60537",     "libelle": "Mortadella aux truffes ~ 3 kg",             "uv": "Kilo"},
        {"code": "61258",     "libelle": "Jambon cru italien 24 tranches 320 g",     "uv": "Pièce"},
        {"code": "22287",     "libelle": "Bresaola 27 tranches 250 g",               "uv": "Pièce"},
    ],
    "06 - VIANDE / Volaille & Canard": [
        {"code": "415",       "libelle": "Filet de poulet cru 2,5 kg",               "uv": "Pièce"},
        {"code": "310",       "libelle": "Cuisses de poulet ~ 250g 10 kg",           "uv": "Colis"},
        {"code": "61612",     "libelle": "Tranchettes de poulet rôti 6mm 1 kg",      "uv": "Pièce"},
        {"code": "62086",     "libelle": "Lobe foie gras ~ 500 g",                   "uv": "Kilo"},
        {"code": "62080",     "libelle": "Confit de cuisses de canard 12 cuisses",   "uv": "Pièce"},
    ],
    "06 - VIANDE / Boeuf & Veau": [
        {"code": "62409",     "libelle": "Steak haché façon bouchère VBF 15% 180g x8","uv":"Pièce"},
        {"code": "62032",     "libelle": "Onglet de boeuf UE ~ 2,5 kg",              "uv": "Kilo"},
        {"code": "62200",     "libelle": "Bavette aloyau UE ~ 3 kg",                 "uv": "Kilo"},
        {"code": "62307",     "libelle": "Entrecote UE 3.5 kg+",                     "uv": "Kilo"},
        {"code": "62230",     "libelle": "Côte de boeuf tomahawk ~ 1 kg",            "uv": "Kilo"},
        {"code": "62301",     "libelle": "Noix de veau rosée ~ 3 kg",                "uv": "Kilo"},
        {"code": "61563",     "libelle": "Osso Buco ~ 1,5 kg",                       "uv": "Kilo"},
        {"code": "62164",     "libelle": "Épaule de veau désossée",                  "uv": "Kilo"},
    ],
    "06 - VIANDE / Porc": [
        {"code": "61673",     "libelle": "Échine de porc ~ 5 kg",                    "uv": "Kilo"},
        {"code": "62215",     "libelle": "Filet mignon de porc 5 kg",                "uv": "Kilo"},
        {"code": "62153",     "libelle": "Saucisse brasse Label Rouge 1 kg",         "uv": "Kilo"},
        {"code": "60845",     "libelle": "Porchetta au four en tranche ~ 3 kg",      "uv": "Kilo"},
        {"code": "61288",     "libelle": "Saucisses fraiches 1 kg",                  "uv": "Kilo"},
        {"code": "61289",     "libelle": "Saucisses fraiches fenouil 1 kg",          "uv": "Kilo"},
    ],
    "07 - POISSON": [
        {"code": "101100",    "libelle": "Saumon fumé Norvège bande 1 kg",           "uv": "Pièce"},
        {"code": "60838",     "libelle": "Thon listao au naturel 3/1",               "uv": "Pièce"},
        {"code": "61094",     "libelle": "Thon listao au naturel poche 1 kg",        "uv": "Pièce"},
        {"code": "62310",     "libelle": "Thon listao au naturel 600 g",             "uv": "Pièce"},
        {"code": "4142",      "libelle": "Filet d'anchois à l'huile de tournesol 4/4","uv":"Pièce"},
        {"code": "296008",    "libelle": "Filet d'anchois del mar Cantabrico 550 g", "uv": "Pièce"},
        {"code": "128099",    "libelle": "Sardine à l'huile d'olive 16/20 115 g",    "uv": "Pièce"},
        {"code": "100026",    "libelle": "Crevette roses grosses 100/200 900g net",  "uv": "Pièce"},
        {"code": "62511",     "libelle": "Salade de poulpe seau 5 kg",               "uv": "Pièce"},
        {"code": "61915",     "libelle": "Bottarga di muggine ~ 70 g",               "uv": "Kilo"},
    ],
}


# ══════════════════════════════════════════════
#  VALIDATION
# ══════════════════════════════════════════════

def valider_date(valeur: str) -> bool:
    valeur = valeur.strip().replace("-", "/")
    try:
        date = datetime.strptime(valeur, "%d/%m/%Y")
        if date.date() <= datetime.today().date():
            print("    La date doit être dans le futur.")
            return False
        if date.date() > (datetime.today() + timedelta(days=365)).date():
            print("    La date ne peut pas dépasser 1 an à l'avance.")
            return False
        return True
    except ValueError:
        return False

def valider_quantite(valeur: str) -> bool:
    try:
        return float(valeur.replace(",", ".")) > 0
    except ValueError:
        return False

def demander(prompt, validateur=None, msg_erreur="",
             transformer=None, obligatoire=True) -> str:
    while True:
        valeur = input(prompt).strip()
        if not valeur:
            if not obligatoire:
                return ""
            print("    Ce champ est obligatoire.")
            continue
        if validateur and not validateur(valeur):
            if msg_erreur:
                print(f"    {msg_erreur}")
            continue
        return transformer(valeur) if transformer else valeur


# ══════════════════════════════════════════════
#  SÉLECTION DANS LE CATALOGUE
# ══════════════════════════════════════════════

def choisir_categorie() -> str:
    categories = list(CATALOGUE.keys())
    print("\n  Catégories disponibles :\n")
    for i, cat in enumerate(categories, 1):
        print(f"    {i:2}. {cat}")
    while True:
        choix = input("\n  Votre choix [1-{}] : ".format(len(categories))).strip()
        try:
            idx = int(choix) - 1
            if 0 <= idx < len(categories):
                return categories[idx]
        except ValueError:
            pass
        print("    Entrez un numéro valide.")


def choisir_produit(categorie: str) -> dict:
    produits = CATALOGUE[categorie]
    print(f"\n  Produits — {categorie} :\n")
    for i, p in enumerate(produits, 1):
        print(f"    {i:2}. [{p['code']:12}] {p['libelle']}  ({p['uv']})")
    while True:
        choix = input("\n  Votre choix [1-{}] : ".format(len(produits))).strip()
        try:
            idx = int(choix) - 1
            if 0 <= idx < len(produits):
                return produits[idx]
        except ValueError:
            pass
        print("    Entrez un numéro valide.")


# ══════════════════════════════════════════════
#  SAISIE COMMANDE
# ══════════════════════════════════════════════

def saisie_commande() -> dict:
    print("\n" + "="*60)
    print("   GUSTOMIO — Commande depuis le catalogue 2026")
    print("="*60)

    print("\n  INFORMATIONS CLIENT\n")
    client   = demander("  Nom du client        : ")
    adresse  = demander("  Adresse de livraison : ")
    livraison= demander(
        "  Date de livraison (JJ/MM/AAAA) : ",
        validateur=valider_date,
        transformer=lambda v: v.strip().replace("-", "/"),
        msg_erreur="Format invalide ou date passée. Ex : 25/05/2025"
    )
    print("\n  Canal de réception :")
    print("    1 - E-mail   2 - Vocal   3 - PDF   4 - Application")
    canal_choix = demander(
        "  Votre choix [1-4] : ",
        validateur=lambda v: v in ("1","2","3","4"),
        msg_erreur="Tapez 1, 2, 3 ou 4."
    )
    canal = {"1":"email","2":"vocal","3":"pdf","4":"app"}[canal_choix]

    print("\n  ARTICLES\n")
    nb_str = demander(
        "  Combien d'articles voulez-vous commander ? ",
        validateur=lambda v: v.isdigit() and 1 <= int(v) <= 50,
        msg_erreur="Entrez un nombre entier entre 1 et 50."
    )
    nb_articles = int(nb_str)

    articles = []
    for i in range(1, nb_articles + 1):
        print(f"\n  {'─'*55}")
        print(f"  Article {i}/{nb_articles}")
        print(f"  {'─'*55}")

        categorie = choisir_categorie()
        produit   = choisir_produit(categorie)

        print(f"\n  ✔  Produit sélectionné : {produit['libelle']}")
        print(f"     Code : {produit['code']}  |  UV : {produit['uv']}")

        quantite = demander(
            f"\n  Quantité (en {produit['uv']}) : ",
            validateur=valider_quantite,
            transformer=lambda v: v.replace(",", "."),
            msg_erreur="Entrez un nombre positif."
        )

        articles.append({
            "code_article": produit["code"],
            "libelle":      produit["libelle"],
            "quantite":     float(quantite),
            "unite":        produit["uv"],
            "categorie":    categorie,
        })

    print("\n  NOTES\n")
    notes = demander(
        "  Remarques / instructions (Entrée pour ignorer) : ",
        obligatoire=False
    )

    now = datetime.now()
    return {
        "metadata": {
            "id_commande":   f"CMD-{now.strftime('%Y%m%d-%H%M%S')}",
            "date_creation": now.strftime("%d/%m/%Y %H:%M:%S"),
            "canal":         canal,
            "statut":        "en_attente_validation",
            "source":        "catalogue_gustomio_2026",
            "version":       "1.0"
        },
        "client": {
            "nom":               client,
            "adresse_livraison": adresse,
            "date_livraison":    livraison,
        },
        "articles":  articles,
        "resume": {
            "nombre_articles": len(articles),
            "notes":           notes if notes else None,
        },
        "odoo": {
            "pret_pour_import": True,
            "endpoint":         "/api/sale.order/create",
            "methode":          "POST"
        }
    }


# ══════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════

def main():
    try:
        commande = saisie_commande()
    except KeyboardInterrupt:
        print("\n\n  Saisie annulée.")
        return

    safe_name = commande["client"]["nom"].replace(" ", "_").replace("/", "-")
    cmd_id    = commande["metadata"]["id_commande"]
    output    = f"commande_{safe_name}_{cmd_id}.json"

    print(f"\n  Génération du fichier JSON...")
    with open(output, "w", encoding="utf-8") as f:
        json.dump(commande, f, ensure_ascii=False, indent=2)

    print(f"  Fichier créé : {output}")
    print(f"\n  Aperçu :\n{'─'*60}")
    print(json.dumps(commande, ensure_ascii=False, indent=2))
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    main()