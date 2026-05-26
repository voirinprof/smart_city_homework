from pathlib import Path

import geopandas as gpd
import rasterio
from rasterio.mask import mask as rio_mask
from rasterio.merge import merge
from rasterio.transform import array_bounds
from rasterio.warp import Resampling, calculate_default_transform, reproject
from shapely.geometry import box


class WorldCoverProcessor:
    """Découpe, fusionne et reprojette les tuiles ESA WorldCover.

    Pipeline en trois étapes — chacune conserve son résultat sur disque :
      1. Découpe de chaque tuile sur la bbox des arrondissements  → *_clipped.tif
      2. Fusion des tuiles découpées                              → *_merged.tif
      3. Reprojection du fichier fusionné                        → *.tif

    Si le fichier final existe déjà, tout le preprocessing est ignoré.

    Parameters
    ----------
    input_dir : str | Path
        Dossier contenant les .tif WorldCover et le .gpkg arrondissements.
    output_dir : str | Path
        Dossier de destination de tous les fichiers intermédiaires et finaux.
    epsg : int
        Code EPSG de la projection de sortie.

    Example
    -------
    >>> proc = WorldCoverProcessor(epsg=32187)
    >>> proc.process()
    """

    _WORLDCOVER_GLOB = "ESA_WorldCover_10m_2021_v200_*_Map.tif"

    def __init__(
        self,
        input_dir: str | Path = "data/raw",
        output_dir: str | Path = "data/processed",
        epsg: int = 32187,
    ) -> None:
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.epsg = epsg

    def process(self, output_name: str = "worldcover_sherbrooke") -> Path:
        """Exécute le pipeline complet : découpe → fusion → reprojection.

        Parameters
        ----------
        output_name : str
            Préfixe des fichiers de sortie (sans extension).

        Returns
        -------
        Path
            Chemin du GeoTIFF final reprojeté.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / f"{output_name}.tif"

        if output_path.exists():
            print(f"  Fichier déjà existant — preprocessing ignoré : {output_path}")
            return output_path

        tif_paths = sorted(self.input_dir.glob(self._WORLDCOVER_GLOB))
        if not tif_paths:
            raise FileNotFoundError(
                f"Aucun fichier ESA WorldCover (_MAP) trouvé dans {self.input_dir}"
            )

        bbox_geom = self._get_arrondissements_bbox()

        clipped_paths = self._clip_tiles(tif_paths, bbox_geom, output_name)
        merged_path = self._merge_tiles(clipped_paths, output_name)
        self._reproject_and_save(merged_path, output_path)

        size_mb = output_path.stat().st_size // 1048576
        print(f"  Sauvegardé : {output_path}  ({size_mb} Mo)")
        return output_path

    # ── Étape 1 : découpage ───────────────────────────────────────────

    def _clip_tiles(
        self, tif_paths: list[Path], bbox_geom: list, output_name: str
    ) -> list[Path]:
        """Découpe chaque tuile sur la bbox et sauvegarde dans output_dir."""
        print(f"\nÉtape 1 — Découpage de {len(tif_paths)} tuile(s)…")
        clipped_paths = []
        for tif_path in tif_paths:
            out_path = self.output_dir / f"{output_name}_{tif_path.stem}_clipped.tif"
            with rasterio.open(tif_path) as src:
                data, transform = rio_mask(src, bbox_geom, crop=True)
                meta = src.meta.copy()
                meta.update({
                    "height":    data.shape[1],
                    "width":     data.shape[2],
                    "transform": transform,
                })
                colormap = src.colormap(1)
            with rasterio.open(out_path, "w", **meta) as dst:
                dst.write(data)
                dst.write_colormap(1, colormap)
            size_mb = out_path.stat().st_size // 1048576
            print(f"  {out_path.name}  ({size_mb} Mo)")
            clipped_paths.append(out_path)
        return clipped_paths

    # ── Étape 2 : fusion ──────────────────────────────────────────────

    def _merge_tiles(self, clipped_paths: list[Path], output_name: str) -> Path:
        """Fusionne les tuiles découpées et sauvegarde le résultat."""
        print("\nÉtape 2 — Fusion des tuiles découpées…")
        merged_path = self.output_dir / f"{output_name}_merged.tif"
        datasets = [rasterio.open(p) for p in clipped_paths]
        try:
            data, transform = merge(datasets)
            meta = datasets[0].meta.copy()
            meta.update({
                "driver":    "GTiff",
                "height":    data.shape[1],
                "width":     data.shape[2],
                "transform": transform,
            })
            colormap = datasets[0].colormap(1)
        finally:
            for ds in datasets:
                ds.close()
        with rasterio.open(merged_path, "w", **meta) as dst:
            dst.write(data)
            dst.write_colormap(1, colormap)
        size_mb = merged_path.stat().st_size // 1048576
        print(f"  {merged_path.name}  ({size_mb} Mo)")
        return merged_path

    # ── Étape 3 : reprojection ────────────────────────────────────────

    def _reproject_and_save(self, src_path: Path, output_path: Path) -> None:
        """Reprojette src_path vers self.epsg et écrit output_path."""
        print(f"\nÉtape 3 — Reprojection vers EPSG:{self.epsg}…")
        with rasterio.open(src_path) as src:
            dst_crs = f"EPSG:{self.epsg}"
            dst_transform, dst_width, dst_height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height,
                *array_bounds(src.height, src.width, src.transform),
            )
            dst_meta = src.meta.copy()
            dst_meta.update({
                "crs":       dst_crs,
                "transform": dst_transform,
                "width":     dst_width,
                "height":    dst_height,
                "compress":  "lzw",
            })
            colormap = src.colormap(1)
            with rasterio.open(output_path, "w", **dst_meta) as dst:
                for i in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, i),
                        destination=rasterio.band(dst, i),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=dst_transform,
                        dst_crs=dst_crs,
                        resampling=Resampling.bilinear,
                    )
                dst.write_colormap(1, colormap)

    # ── Utilitaire ────────────────────────────────────────────────────

    def _get_arrondissements_bbox(self) -> list:
        """Retourne la bbox de la couche arrondissements en WGS84."""
        candidates = [
            f for f in self.input_dir.glob("*.gpkg")
            if "arrondissement" in f.name.lower()
        ]
        if not candidates:
            raise FileNotFoundError(
                f"Aucun fichier arrondissements (.gpkg) trouvé dans {self.input_dir}"
            )
        gdf = gpd.read_file(candidates[0])
        minx, miny, maxx, maxy = gdf.to_crs("EPSG:4326").total_bounds
        print(f"  Bbox arrondissements (WGS84) : {minx:.4f}, {miny:.4f}, {maxx:.4f}, {maxy:.4f}")
        return [box(minx, miny, maxx, maxy)]
