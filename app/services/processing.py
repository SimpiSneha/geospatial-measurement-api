import json
import logging

from sqlalchemy.orm import Session

from app.models import Feature
from app.models import File as FileRecord
from app.services.parser import ParseError, crs_label, read_features
from app.services.storage import find_source_file

logger = logging.getLogger(__name__)


def process_file(db: Session, record: FileRecord) -> None:
    """Read the uploaded file, store its features, and update the file's status."""
    try:
        gdf = read_features(find_source_file(record.id)).reset_index(drop=True)

        if gdf.crs is None:
            raise ParseError(
                "The file has no coordinate reference system "
                "(for a shapefile, the .prj file is missing)."
            )

        # to_json gives us JSON-safe geometry and properties (NaN becomes null,
        # dates become strings), still in the file's original CRS.
        features = json.loads(gdf.to_json(drop_id=True))["features"]
        geometry_types = gdf.geometry.geom_type.tolist()

        record.features = [
            Feature(
                feature_index=i,
                geometry_type=geometry_types[i],
                geometry=f["geometry"],
                properties=f["properties"],
            )
            for i, f in enumerate(features)
        ]
        record.crs = crs_label(gdf.crs)
        record.feature_count = len(features)
        record.status = "COMPLETED"
        db.commit()

    except ParseError as exc:
        db.rollback()
        record.status = "FAILED"
        record.error_message = str(exc)
        db.commit()
    except Exception:
        logger.exception("Unexpected error while processing file %s", record.id)
        db.rollback()
        record.status = "FAILED"
        record.error_message = "Unexpected error while processing the file."
        db.commit()