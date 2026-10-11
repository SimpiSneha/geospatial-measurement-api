
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio

logger = logging.getLogger(__name__)


class ParseError(Exception):
    """The file could not be read. The message is safe to show to the client."""


def read_features(path: Path) -> gpd.GeoDataFrame:
    """Read a .kml or .shp into one GeoDataFrame (a table with a geometry column)."""
    try:
        if path.suffix.lower() == ".kml":
            # A KML can hold several layers (one per Folder), so read all of them.
            layer_names = [name for name, _ in pyogrio.list_layers(path)]
            frames = [
                gpd.read_file(path, layer=name, engine="pyogrio")
                for name in layer_names
            ]
            frames = [f for f in frames if len(f) > 0]
            if not frames:
                return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
            combined = pd.concat(frames, ignore_index=True)
            return gpd.GeoDataFrame(combined, crs=frames[0].crs)

        return gpd.read_file(path, engine="pyogrio")
    except Exception as exc:
        logger.exception("Failed to read %s", path)
        raise ParseError(
            "Could not read the file. Make sure it is a valid KML or shapefile."
        ) from exc


def crs_label(crs) -> str:
    """Turn a CRS object into a readable label such as 'EPSG:4326'."""
    epsg = crs.to_epsg()
    return f"EPSG:{epsg}" if epsg else crs.to_string()