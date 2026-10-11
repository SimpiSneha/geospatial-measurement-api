from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi import File as FormFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import File as FileRecord
from app.models import new_id
from app.schemas import FileOut
from app.services.processing import process_file
from app.services.storage import FileTooLarge, InvalidUpload, save_upload

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/", response_model=FileOut, status_code=status.HTTP_201_CREATED)
def upload_file(file: UploadFile = FormFile(...), db: Session = Depends(get_db)):
    file_id = new_id()

    try:
        save_upload(file, file_id)
    except FileTooLarge as e:
        raise HTTPException(status_code=413, detail=str(e))
    except InvalidUpload as e:
        raise HTTPException(status_code=400, detail=str(e))

    record = FileRecord(
        id=file_id,
        filename=Path(file.filename).name,
        status="PROCESSING",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    process_file(db, record)
    db.refresh(record)
    return record