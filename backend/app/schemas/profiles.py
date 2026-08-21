from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class ProfileResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    nume: str
    cnp: str
    telefon: str
    email: EmailStr
    iban_cont: str
    creat_la: datetime
    modificat_la: datetime
