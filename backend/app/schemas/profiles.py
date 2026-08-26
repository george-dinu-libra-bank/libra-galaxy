from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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


class CerereStergereRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Optional in mod deliberat: nu conditionam plecarea unui client de o
    # explicatie. Cine vrea sa spuna de ce, spune.
    motiv: str | None = Field(default=None, max_length=500)


class CerereStergereResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    status: str
    motiv: str | None = None
    creat_la: datetime
    decis_la: datetime | None = None
    motiv_refuz: str | None = None


class StareStergereResponse(BaseModel):
    """Ce poate face clientul acum, si de ce.

    `motive_blocare` e o lista de fraze gata de afisat, nu coduri: ecranul le
    arata ca atare, iar cine citeste raspunsul in Postman intelege fara sa aiba
    tabelul de coduri la indemana.
    """

    cerere: CerereStergereResponse | None = None
    poate_cere: bool
    motive_blocare: list[str] = []
