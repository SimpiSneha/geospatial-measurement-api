from pydantic import BaseModel, ConfigDict


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    status: str
    crs: str | None = None
    feature_count: int = 0
    error_message: str | None = None