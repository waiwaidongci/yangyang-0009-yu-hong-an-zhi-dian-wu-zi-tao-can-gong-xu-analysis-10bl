from datetime import date
from pydantic import BaseModel, Field


class IntakeLot(BaseModel):
    item_id: int = Field(gt=0)
    label: str = Field(pattern=r"^[A-Z0-9-]{3,35}$")
    use_by: date
    units: int = Field(ge=1,le=3600)


class ArrivalDay(BaseModel):
    arrival_day: date
