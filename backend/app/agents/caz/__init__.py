"""Cei trei agenti ai investigatiei de frauda.

Nu se cheama intre ei. Orchestratorul lor e masina de stari din
`app/services/caz_service.py`, care stie in ce moment al cazului cine scrie ce.
Un agent care ar chema alt agent ar face ordinea pasilor invizibila si
imposibil de auditat.
"""

from app.agents.caz.analist import AnalistCaz
from app.agents.caz.extractor import ExtractorCaz
from app.agents.caz.fapte import FapteCaz, RaspunsClient, RaspunsExtras, TranzactieCaz
from app.agents.caz.redactor import RedactorCaz

__all__ = [
    "AnalistCaz",
    "ExtractorCaz",
    "RedactorCaz",
    "FapteCaz",
    "RaspunsClient",
    "RaspunsExtras",
    "TranzactieCaz",
]
