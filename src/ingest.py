from pathlib import Path

import yaml

from src.downloader import SherbrookePortal, WorldCoverDownloader


def ingest(config: dict | str | Path = "config.yaml") -> None:
    """Importe des données à partir de différentes sources.

        Parameters
        ----------
        config : dict | str | Path, optional
            Configuration d'ingestion, soit un dictionnaire, soit un chemin vers un fichier YAML.

        Returns
        -------
        None
        """
    if isinstance(config, dict):
        cfg = config
    else:
        with open(config) as f:
            cfg = yaml.safe_load(f)

    _ingest_portal(cfg["portal"])
    _ingest_worldcover(cfg.get("worldcover", {}))

# ── Méthodes internes ─────────────────────────────────────────────
# Ces fonctions sont utilisées uniquement à l'intérieur de ce module pour organiser le code d'ingestion.

def _ingest_portal(cfg: dict) -> None:
    """ Importe des données à partir du portail de Sherbrooke.

        Parameters
        ----------
        config : dict
            Configuration d'ingestion pour le portail, doit contenir une clé "layers" avec une liste de mots-clés.    
        
        Returns
        -------
        None
        """

    portal = SherbrookePortal(
        output_dir=cfg.get("output_dir", "data/raw"),
        format=cfg.get("format", "geojson"),
    )
    for keywords in cfg.get("layers", []):
        results = portal.search(keywords)
        if results:
            portal.download(results[0]["url"] + "/0")
        else:
            print(f"  Aucun résultat pour '{keywords}'.")


def _ingest_worldcover(cfg: dict) -> None:
    """ Importe des données de couverture terrestre à partir d'une URL de Google Drive.

        Parameters
        ----------
        config : dict
            Configuration d'ingestion pour la couverture terrestre, doit contenir une clé "drive_url" avec l'URL du fichier à télécharger.
        Returns
        -------
        None
        """
    drive_url = cfg.get("drive_url")
    if not drive_url:
        return
    dl = WorldCoverDownloader(output_dir=cfg.get("output_dir", "data/raw"))
    dl.download(drive_url)


if __name__ == "__main__":
    ingest()
