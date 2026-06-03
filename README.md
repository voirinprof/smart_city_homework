# GMQ580 — Pipeline géospatial pour une ville intelligente

## Contexte

La Ville de Sherbrooke publie ses données géographiques sur un portail en libre accès. Dans ce travail, vous devrez construire un **pipeline de traitement géospatial complet** : téléchargement, traitement, analyse et export.

Trois modules de départ vous sont fournis — `src/downloader.py`, `src/ingest.py` et `src/process.py` — qui permettent d'accéder aux données. Votre travail consiste à concevoir et implémenter le reste du pipeline.

---

## Mise en place du dépôt

Avant de commencer, vous devez créer votre propre dépôt privé à partir du dépôt du cours. Ce dépôt est configuré comme **template** : vous n'avez pas à forker ni à manipuler git manuellement.

### Étape 1 — Créer votre dépôt depuis le template

1. Accédez au dépôt du cours sur GitHub
2. Cliquez sur le bouton **Use this template** → **Create a new repository**
3. Choisissez un nom pour votre dépôt (ex. `gmq580-td1-prenom-nom`)
4. Sélectionnez **Private**
5. Cliquez sur **Create repository**

Vous disposez maintenant de votre propre copie privée, indépendante du dépôt d'origine.

> **Important** : un dépôt public permet à d'autres étudiants de copier votre travail. Tout dépôt public au moment de la correction entraînera une note de zéro.

### Étape 2 — Inviter le professeur

Pour que le professeur puisse corriger votre travail, vous devez lui donner accès à votre dépôt privé :

1. Dans **Settings** → **Collaborators** → **Add people**
2. Ajoutez le compte GitHub du professeur
3. Accordez le rôle **Read**

> Cette invitation doit être faite **avant la date de remise**. Un dépôt privé sans accès professeur ne pourra pas être corrigé.

---

## Données

Deux sources sont à utiliser :

**1. Portail de données ouvertes de la Ville de Sherbrooke**
Données vecteur accessibles via l'API REST ArcGIS.

**2. ESA WorldCover 10 m (2021)**
Données raster à l'échelle mondiale (souvent obtenues par indicateurs de végétation, ce détail est important).
Le fichier ZIP contenant les tuiles GeoTIFF couvrant la région de Sherbrooke est disponible sur Google Drive.

---

## Installation de l'environnement

### Prérequis

- Python 3.11+
- `git`
- Conda ou pip (au choix)

---

### Option A — Conda (recommandé)

Conda gère les dépendances système de GeoPandas et Rasterio, ce qui évite la majorité des problèmes d'installation sur Windows, macOS et Linux.

```bash
conda env create -f environment.yml
conda activate gmq580td1
```

Pour mettre à jour l'environnement si `environment.yml` change :

```bash
conda env update -f environment.yml --prune
```

**`environment.yml`**

```yaml
name: gmq580td1
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  - geopandas>=1.0
  - rasterio>=1.3
  - shapely>=2.0
  - numpy>=2.0
  - matplotlib>=3.9
  - pyyaml>=6.0
  - pip
  - pip:
      - requests>=2.32
```

---

### Option B — pip + venv

```bash
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# ou
.venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

**`requirements.txt`**

```
requests>=2.32
geopandas>=1.0
rasterio>=1.3
pyyaml>=6.0
shapely>=2.0
numpy>=2.0
matplotlib>=3.9
```

> **Note** : sur Windows, l'installation de GeoPandas et Rasterio via pip peut nécessiter des étapes supplémentaires (GDAL, Fiona). Préférez l'option Conda dans ce cas.

> **Important** : Les bibliothèques listées ci-dessus sont suffisantes pour réaliser l'ensemble du travail. Toute dépendance supplémentaire doit être approuvée par le professeur avant d'être ajoutée.

> Il peut arriver sous Windows que la lib rasterio soit mal installée
> Vous allez avoir une erreur avec le DLL (comme *ImportError: DLL load failed while importing _rasterio: The specified module could not be found.*)
> Vous pouvez essayer ces 2 options :
```bash
conda install -c conda-forge rasterio
# ou
pip install --force-reinstall rasterio
```
---

## Prise en main des modules fournis

### Explorer les données disponibles

```python
from src.downloader import SherbrookePortal

portal = SherbrookePortal(format="gpkg")

# Rechercher des jeux de données par mot-clé
results = portal.search("districts_de_sherbrooke")

# Inspecter les couches d'un service
portal.inspect(results[0]["url"])

# Télécharger une couche
portal.download(results[0]["url"] + "/0")
```

### Lancer l'ingestion complète via la configuration

Le fichier `config.yaml` centralise les paramètres (couches à télécharger, répertoires, projection, etc.). La fonction `ingest()` du module `src/ingest.py` l'utilise pour automatiser les téléchargements :

```python
from src.ingest import ingest

ingest("config.yaml")
```

---

## Travail à réaliser

À partir des données téléchargées, vous devez implémenter un pipeline complet organisé en **modules Python distincts** (notamment `src/analyze.py` et `src/export.py`).

### Ce que le pipeline doit accomplir

- **Traitement raster** : les données WorldCover couvrent plusieurs tuiles. Il faut les découper, les fusionner et les reprojeter dans la projection appropriée.
- **Analyse spatiale** : choisissez un arrondissement de la ville. Pour cet arrondissement, identifiez les adresses situées à proximité de zones inondables et analysez les classes de couverture du sol dans ces zones à risque.
- **Export** : produisez un rapport synthétique (PDF ou autre format structuré) présentant vos résultats.

### Plus précisément

Le travail réalisé n'est pas complet, vous devez terminer les modules. Voici la liste de ce qui manque :

* Disposer d'un log permettant de sauvegarder une trace des opérations du pipeline
* Valider les données avant de les analyser (à vous de définir les règles)
* Extraire la zone inondable (uniquement pour l'arrondissement sélectionné dans le fichier config.yaml)
* Définir une zone tampon sur cette zone inondable (paramètre dans le fichier config.yaml)
* Afficher la taille de la zone tampon (en km²)
* Disposer des statistiques suivantes (dans un fichier):
  * Obtenir la liste des arrondissements avec leur superficie (en km²)
  * Obtenir la surface totale des arrondissements de Sherbrooke (en km²)
  * Obtenir le nombre d'adresses dans chaque arrondissement
  * Obtenir le nombre d'adresses se trouvant dans la zone inondable (uniquement pour l'arondissement sélectionné dans le fichier config.yaml)
  * Obtenir les 3 rues les plus affectées (par le nombre d'adresses)
  * Obtenir la superficie de chaque classe d'occupation du sol (en km²)
* Disposer d'un document PDF présentant une carte (en MTM) avec les éléments suivants:
  * un titre
  * la zone inondable
  * la zone tampon
  * les points des adresses affectés
  * une échelle
  * une légende
  * une grille
  * le nord

### Ce que l'on souhaite

- La **qualité et la clarté du pipeline** : chaque étape doit être distincte, reproductible, et les fichiers intermédiaires correctement gérés.
- Les **validations** : vérifiez que les fichiers existent avant de les lire, que les CRS sont compatibles avant toute opération, que les couches contiennent bien des données, etc.
- La **structure du code** : découpez votre travail en modules cohérents et réutilisables.
- La **reproductibilité** : un utilisateur qui clone le dépôt et exécute votre code doit obtenir les mêmes résultats.

### Vous avez certaines libertés

La structure interne du pipeline, les choix d'implémentation, la gestion de la configuration, les métriques produites — tout cela vous appartient. Il n'y a pas une seule bonne réponse.

---

## Structure suggérée

```
.
├── config.yaml
├── requirements.txt
├── main.py               # point d'entrée du pipeline
├── data/
│   ├── raw/              # données brutes téléchargées
│   └── processed/        # données traitées
└── src/
    ├── downloader.py     # fourni
    ├── ingest.py         # fourni
    ├── ...               # vos modules
```

---

## Conseils

- Commencez par explorer le portail avant d'automatiser quoi que ce soit.
- Identifiez les données utiles à votre analyse.
- Un pipeline qui s'interrompt avec un message d'erreur clair vaut mieux qu'un pipeline sans traces qui produit un résultat incorrect.
- Testez chaque étape indépendamment avant de les enchaîner.
- Versionner votre travail avec git régulièrement.

---

## Notation

| # | Critère | Points |
|---|---|:---:|
| **1** | **Pipeline et qualité du code** | **/5** |
|  | Logging, validations, modules distincts, fonctions cohérentes et réutilisables, ... |  |
| **2** | **Traitement des données** | **/4** |
|  | découpe, fusion et reprojection des tuiles WorldCover, extraction de la zone inondable pour l'arrondissement configuré, zone tampon, ... |  |
| **3** | **Analyse et statistiques** | **/6** |
|  | Superficie de chaque arrondissement (km²), surface totale et nombre d'adresses par arrondissement, Nombre d'adresses dans la zone inondable (arrondissement sélectionné), Top 3 des rues les plus affectées (par nombre d'adresses),  Superficie de chaque classe d'occupation du sol (km²), Qualité et lisibilité du fichier de sortie (format, en-têtes, unités), ... |  |
| **4** | **Rapport PDF — Carte** | **/4** |
|  | Projection MTM, présence de la zone inondable, du tampon et des adresses affectées, Titre, échelle, légende, grille et flèche du nord, lisibilité générale : couleurs, symbologie, hiérarchie visuelle |  |
| **5** | **Utilisation de Git et GitHub** | **/1** |
|  | Historique de commits régulier et progressif (plusieurs commits, pas un seul commit massif en fin de travail), messages de commit clairs et descriptifs, découpage logique des commits (une fonctionnalité ou une correction par commit), dépôt privé correctement configuré avec accès professeur accordé avant la remise |  |
| | **Total** | **/20** |
