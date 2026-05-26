"""
downloader.py
Téléchargement de données depuis le portail ouvert de la Ville de Sherbrooke
via l'API REST ArcGIS (FeatureService).

Usage simple :
    from src.downloader import SherbrookePortal

    portal = SherbrookePortal()
    portal.download("https://services3.arcgis.com/.../FeatureServer/0")

Usage CLI :
    python -m src.downloader --search "arrondissement"
    python -m src.downloader --inspect "https://…/FeatureServer"
    python -m src.downloader --url "https://…/FeatureServer/0" --format gpkg
"""

import argparse
import math
import time
import zipfile
import tempfile
from pathlib import Path

import requests
import geopandas as gpd

_PORTAL_SEARCH_URL = "https://donneesouvertes-sherbrooke.opendata.arcgis.com/api/search/v1/collections/all/items"
_PAGE_SIZE = 1000

_OUTPUT_FORMATS = {
    "geojson":   (".geojson", lambda gdf, p: gdf.to_file(p, driver="GeoJSON")),
    "gpkg":      (".gpkg",    lambda gdf, p: gdf.to_file(p, driver="GPKG")),
    "shapefile": (".zip",     "_save_shapefile"),
    "csv":       (".csv",     lambda gdf, p: gdf.drop(columns="geometry").to_csv(p, index=False, encoding="utf-8")),
}


def _save_shapefile(gdf: gpd.GeoDataFrame, output_path: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        shp_folder = Path(tmp_dir) / output_path.stem
        shp_folder.mkdir()
        gdf.to_file(shp_folder / f"{output_path.stem}.shp", driver="ESRI Shapefile")
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in shp_folder.iterdir():
                zf.write(f, f.name)


_OUTPUT_FORMATS["shapefile"] = (".zip", _save_shapefile)


class SherbrookePortal:
    """Client pour le portail de données ouvertes de la Ville de Sherbrooke.

    Parameters
    ----------
    output_dir : str | Path
        Dossier de destination des fichiers téléchargés (défaut : data/raw).
    format : str
        Format par défaut : 'geojson', 'gpkg', 'shapefile' ou 'csv'.

    Examples
    --------
    >>> portal = SherbrookePortal()
    >>> portal.download("https://services3.arcgis.com/.../FeatureServer/0")

    >>> portal = SherbrookePortal(format="gpkg")
    >>> results = portal.search("arrondissement")
    >>> portal.inspect("https://…/FeatureServer")
    """

    def __init__(
        self,
        output_dir: str | Path = "data/raw",
        format: str = "geojson",
    ) -> None:
        if format not in _OUTPUT_FORMATS:
            raise ValueError(f"Format inconnu : '{format}'. Choix : {list(_OUTPUT_FORMATS)}")
        self.output_dir = Path(output_dir)
        self.format = format

    # ── API publique ──────────────────────────────────────────────────

    def download(
        self,
        url: str,
        where: str = "1=1",
        format: str | None = None,
        name: str | None = None,
    ) -> Path | None:
        """Télécharge une couche FeatureService et la sauvegarde dans output_dir.

        Parameters
        ----------
        url : str
            URL d'une couche FeatureService (ex. https://…/FeatureServer/0).
        where : str
            Filtre SQL optionnel (ex. "TYPE='Parc'").
        format : str | None
            Remplace le format par défaut de l'instance pour cet appel.
        name : str | None
            Nom du fichier de sortie (sans extension). Déduit de l'URL si omis.

        Returns
        -------
        Path | None
            Chemin du fichier créé, ou None si aucune entité reçue.
        """
        fmt = format or self.format
        if fmt not in _OUTPUT_FORMATS:
            raise ValueError(f"Format inconnu : '{fmt}'. Choix : {list(_OUTPUT_FORMATS)}")

        dataset_name = name or self._name_from_url(url)
        print(f"\nTéléchargement : {dataset_name}")
        print(f"  Source  : {url}")
        if where != "1=1":
            print(f"  Filtre  : {where}")

        # si le fichier existe déjà, on ne retélécharge pas
        ext, _ = _OUTPUT_FORMATS[fmt]
        output_path = self.output_dir / f"{dataset_name}{ext}"
        if output_path.exists():
            print(f"  Fichier déjà existant : {output_path}")
            return output_path

        gdf = self._fetch_layer(url, where=where)
        if gdf.empty:
            print("  Aucune donnée reçue.")
            return None

        return self._save(gdf, dataset_name, fmt)

    def search(self, keywords: str, max_results: int = 50) -> list[dict]:
        """Recherche des Feature Services sur le portail de Sherbrooke.

        Parameters
        ----------
        keywords : str
            Termes de recherche (ex. "arrondissement").
        max_results : int
            Nombre maximum de résultats.

        Returns
        -------
        list[dict]
            Liste de résultats avec titre, url, type, date de modification.
        """
        response = requests.get(
            _PORTAL_SEARCH_URL,
            params={"q": keywords, "limit": min(max_results, 100)},
            timeout=30,
        )
        response.raise_for_status()

        results = []
        for feature in response.json().get("features", []):
            props = feature.get("properties", {})
            if props.get("type") not in ("Feature Service", "Map Service"):
                continue
            results.append({
                "id":       feature.get("id", ""),
                "title":    props.get("title", "(sans titre)"),
                "type":     props.get("type", ""),
                "url":      props.get("url", ""),
                "modified": str(props.get("modified", ""))[:10],
            })

        self._print_search_results(results)
        return results

    def inspect(self, service_url: str) -> dict:
        """Récupère et affiche les couches disponibles d'un FeatureService.

        Parameters
        ----------
        service_url : str
            URL racine du service (ex. https://…/FeatureServer).

        Returns
        -------
        dict
            Métadonnées : nom, couches disponibles, code EPSG.
        """
        response = requests.get(service_url.rstrip("/"), params={"f": "json"}, timeout=30)
        response.raise_for_status()
        meta = response.json()

        layers = [
            {"id": l.get("id"), "name": l.get("name", ""), "type": l.get("type", "")}
            for l in meta.get("layers", []) + meta.get("tables", [])
        ]
        info = {
            "name":   meta.get("serviceDescription") or meta.get("name", ""),
            "layers": layers,
            "epsg":   meta.get("spatialReference", {}).get("wkid", "?"),
            "url":    service_url,
        }

        print(f"\nService : {info['name'] or service_url}")
        print(f"CRS     : EPSG:{info['epsg']}")
        print(f"\n{'ID':<5} {'Nom':<50} {'Type'}")
        print("-" * 70)
        for layer in layers:
            print(f"{layer['id']:<5} {layer['name'][:48]:<50} {layer['type']}")
        print(f"\nPour télécharger la couche 0 :")
        print(f"  portal.download('{service_url.rstrip('/')}/0')")

        return info

    # ── Méthodes internes ─────────────────────────────────────────────

    def _fetch_layer(self, layer_url: str, where: str = "1=1") -> gpd.GeoDataFrame:
        query_url = layer_url.rstrip("/") + "/query"

        response = requests.get(query_url, params={
            "where": where, "returnCountOnly": "true", "f": "json"
        }, timeout=30)
        response.raise_for_status()
        total_count = response.json().get("count", 0)
        print(f"  Entités à télécharger : {total_count}")

        if total_count == 0:
            return gpd.GeoDataFrame()

        all_features = []
        page_count = math.ceil(total_count / _PAGE_SIZE)

        for page in range(page_count):
            offset = page * _PAGE_SIZE
            print(f"\r  Page {page + 1}/{page_count} ({offset}/{total_count})…", end="", flush=True)
            response = requests.get(query_url, params={
                "where":             where,
                "outFields":         "*",
                "outSR":             "4326",
                "resultOffset":      offset,
                "resultRecordCount": _PAGE_SIZE,
                "f":                 "geojson",
            }, timeout=60)
            response.raise_for_status()
            all_features.extend(response.json().get("features", []))
            if page < page_count - 1:
                time.sleep(0.2)

        print(f"\r  {len(all_features)} entités reçues.              ")

        if not all_features:
            return gpd.GeoDataFrame()

        return gpd.GeoDataFrame.from_features(
            {"type": "FeatureCollection", "features": all_features},
            crs="EPSG:4326",
        )

    def _save(self, gdf: gpd.GeoDataFrame, name: str, fmt: str) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        clean_name = name.replace(" ", "_").replace("/", "-")
        ext, save_fn = _OUTPUT_FORMATS[fmt]
        output_path = self.output_dir / f"{clean_name}{ext}"
        save_fn(gdf, output_path)
        size_kb = output_path.stat().st_size // 1024
        print(f"  Sauvegarde : {output_path}  ({len(gdf)} entités, {size_kb} Ko)")
        return output_path

    @staticmethod
    def _name_from_url(url: str) -> str:
        parts = url.rstrip("/").split("/")
        return f"{parts[-3]}_{parts[-2]}" if len(parts) >= 3 else "dataset"

    @staticmethod
    def _print_search_results(results: list[dict]) -> None:
        if not results:
            print("Aucun résultat.")
            return
        print(f"\n{'#':<4} {'Titre':<55} {'Type':<18} {'Modifié'}")
        print("-" * 95)
        for i, item in enumerate(results, 1):
            print(f"{i:<4} {item['title'][:53]:<55} {item['type'][:16]:<18} {item['modified']}")
            if item["url"]:
                print(f"     {item['url']}")
        print(f"\n{len(results)} résultat(s).")


# ── WorldCover ────────────────────────────────────────────────────────

class WorldCoverDownloader:
    """Télécharge un ZIP depuis Google Drive contenant des GeoTIFFs ESA WorldCover.

    Le téléchargement est ignoré si les fichiers .tif sont déjà présents.
    Après extraction, lit les métadonnées rasterio pour confirmer l'intégrité.

    Parameters
    ----------
    output_dir : str | Path
        Dossier de destination (défaut : data/raw).

    Example
    -------
    >>> dl = WorldCoverDownloader()
    >>> dl.download("https://drive.google.com/file/d/ABC123/view?usp=sharing")
    """

    _GDRIVE_URL = "https://drive.usercontent.google.com/download"

    def __init__(self, output_dir: str | Path = "data/raw") -> None:
        self.output_dir = Path(output_dir)

    def download(self, drive_url: str) -> list[Path]:
        """Télécharge, extrait et vérifie les GeoTIFFs.

        Parameters
        ----------
        drive_url : str
            URL de partage Google Drive du fichier ZIP.

        Returns
        -------
        list[Path]
            Chemins des fichiers .tif extraits (ou déjà présents).
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        existing = sorted(self.output_dir.glob("*.tif"))
        if existing:
            print(f"Fichiers déjà présents ({len(existing)}) — téléchargement ignoré.")
            self._verify(existing)
            return existing

        file_id = self._parse_file_id(drive_url)
        zip_path = self._download_zip(file_id)
        tif_paths = self._extract(zip_path)
        zip_path.unlink()
        self._verify(tif_paths)
        return tif_paths

    # ── Méthodes internes ─────────────────────────────────────────────

    def _parse_file_id(self, url: str) -> str:
        if "/file/d/" in url:
            return url.split("/file/d/")[1].split("/")[0]
        from urllib.parse import urlparse, parse_qs
        params = parse_qs(urlparse(url).query)
        if "id" in params:
            return params["id"][0]
        raise ValueError(f"Impossible d'extraire l'ID depuis l'URL : {url}")

    def _download_zip(self, file_id: str) -> Path:
        # drive.usercontent.google.com + confirm=t contourne la page de confirmation
        response = requests.get(
            self._GDRIVE_URL,
            params={"id": file_id, "export": "download", "confirm": "t", "authuser": "0"},
            stream=True,
            timeout=120,
        )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            raise RuntimeError(
                "Google Drive a retourné une page HTML. "
                "Vérifiez que le fichier est partagé en mode 'Tout le monde avec le lien'."
            )

        zip_path = self.output_dir / "worldcover_sherbrooke.zip"
        total = int(response.headers.get("content-length", 0))
        downloaded = 0

        print("  Téléchargement du ZIP…")
        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    print(f"\r  {pct}%  ({downloaded // 1048576} / {total // 1048576} Mo)…", end="", flush=True)

        size_mb = zip_path.stat().st_size // 1048576
        print(f"\r  ZIP téléchargé : {zip_path}  ({size_mb} Mo)    ")
        return zip_path

    def _extract(self, zip_path: Path) -> list[Path]:
        tif_paths = []
        with zipfile.ZipFile(zip_path) as zf:
            tif_names = [n for n in zf.namelist() if n.lower().endswith(".tif")]
            print(f"  Extraction de {len(tif_names)} GeoTIFF(s)…")
            for name in tif_names:
                dest = self.output_dir / Path(name).name
                with zf.open(name) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                tif_paths.append(dest)
        return tif_paths

    def _verify(self, paths: list[Path]) -> None:
        import rasterio
        print("\n  Métadonnées des GeoTIFFs :")
        for path in paths:
            with rasterio.open(path) as ds:
                print(f"\n  {path.name}")
                print(f"    Dimensions  : {ds.width} x {ds.height} px")
                print(f"    Bandes      : {ds.count}  |  dtype : {ds.dtypes[0]}")
                print(f"    CRS         : {ds.crs}")
                print(f"    Résolution  : {ds.res[0]:.6f} deg/px")
                print(f"    Emprise     : {ds.bounds}")


# ── Interface CLI ─────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Données ouvertes Ville de Sherbrooke (ArcGIS REST)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--search",  metavar="KEYWORDS",    help="Rechercher des jeux de données")
    group.add_argument("--inspect", metavar="SERVICE_URL", help="Lister les couches d'un FeatureService")
    group.add_argument("--url",     metavar="LAYER_URL",   help="Télécharger une couche")
    parser.add_argument("--format", default="geojson", choices=list(_OUTPUT_FORMATS))
    parser.add_argument("--output", default="data/raw", metavar="DIR")
    parser.add_argument("--where",  default="1=1",     metavar="SQL")
    args = parser.parse_args()

    portal = SherbrookePortal(output_dir=args.output, format=args.format)

    if args.search:
        portal.search(args.search)
    elif args.inspect:
        portal.inspect(args.inspect)
    elif args.url:
        portal.download(args.url, where=args.where)


if __name__ == "__main__":
    main()
