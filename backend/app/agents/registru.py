"""Asambleaza agentii pentru un request.

Un singur loc in care se decide cine exista. Cand un agent se implementeaza,
se schimba o linie aici si restul aplicatiei nu simte nimic.
"""

from uuid import UUID

from supabase import Client

from app.agents import actiuni, document, financiar, rag
from app.agents.baza import Agent
from app.agents.orchestrator import Orchestrator
from app.infrastructure.config import Settings
from app.infrastructure.llm import ClientModel
from app.ml.neregularitati import DetectorNeregularitati
from app.repositories.card_repository import CardRepository
from app.repositories.cont_repository import ContRepository
from app.repositories.tranzactie_repository import TranzactieRepository
from app.services.analiza_service import AnalizaService


def construieste_analiza(client_supabase: Client, settings: Settings) -> AnalizaService:
    return AnalizaService(
        TranzactieRepository(client_supabase),
        CardRepository(client_supabase),
        ContRepository(client_supabase),
        DetectorNeregularitati.cu_model_de_pe_disc(),
        settings.analiza_limita_randuri,
    )


def construieste_orchestrator(
    client: ClientModel,
    client_supabase: Client,
    settings: Settings,
    user_id: UUID,
) -> Orchestrator:
    analiza = construieste_analiza(client_supabase, settings)

    agenti: list[Agent] = [
        financiar.construieste(client, settings, analiza, user_id),
        actiuni.construieste(),
        rag.construieste(),
        document.construieste(),
    ]

    return Orchestrator(client, settings, agenti, user_id)
