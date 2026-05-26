# importe les bibliothèques nécessaires
import yaml

# importe les fonctions d'ingestion, de traitement, d'analyse et d'exportation
from src.ingest import ingest

# ── Point d'entrée principal ─────────────────────────────────────────────
def main() -> None:
    """ Point d'entrée principal du pipeline de données.

        Cette fonction lit la configuration d'ingestion à partir d'un fichier YAML, puis appelle les fonctions d'ingestion, de traitement, d'analyse et d'exportation dans l'ordre.
    """

    # Lecture de la configuration d'ingestion à partir du fichier YAML
    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)
    # Appel de la fonction d'ingestion avec la configuration lue
    ingest(cfg)

    # TODO: Appeler les fonctions de traitement, d'analyse et d'exportation ici


if __name__ == "__main__":
    main()
