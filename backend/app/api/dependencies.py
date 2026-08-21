"""Compunerea aplicatiei: cladeste orchestratorul o singura data, din setari validate.

Nu e un singleton la nivel de modul (interzis de docs/PATTERN_ADOPTION.md) —
e o functie de fabrica, apelata prin FastAPI Depends, testabila prin
dependency_overrides.

Autentificarea principala (JWT/JWKS + modul cu cheie interna) nu e aici —
traieste in core/security.py, singurul loc care decodeaza un token pentru
Principal. `get_current_user`/`get_user_supabase` de mai jos sunt o a doua
cale, complementara: intorc un client Supabase scopat pe utilizator (pastreaza
contextul RLS), pentru cod care are nevoie explicit de asta — azi doar
adaptorul financial_advisor (vezi agents/financial_advisor.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

from anyio import to_thread
from fastapi import Depends, Header, HTTPException, status
from supabase import Client

from app.agents.compliance_kyc import ComplianceKycAgent
from app.agents.document_intelligence import DocumentIntelligenceAgent
from app.agents.engagement import EngagementAgent
from app.agents.financial_advisor import FinancialAdvisorAgent
from app.agents.transaction_intelligence import TransactionIntelligenceAgent
from app.attachments.service import AttachmentService
from app.services.credit_service import CreditService
from app.core.config import Settings, get_settings
from app.infrastructure.attachment_storage import AttachmentStorage
from app.infrastructure.supabase import (
    create_auth_client,
    create_user_client,
    get_admin_client,
)
from app.infrastructure.supabase_client import get_service_client
from app.ml.neregularitati import DetectorNeregularitati
from app.orchestration.orchestrator import Orchestrator
from app.orchestration.routing import AgentRouter
from app.providers.foundry import MicrosoftFoundryChatProvider, MicrosoftFoundryEmbeddingProvider
from app.providers.voice import MicrosoftVoiceProvider
from app.rag.retrieval import RetrievalService
from app.repositories.attachment_repository import AttachmentRepository
from app.repositories.banking_read_repository import BankingReadRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.credit_repository import CreditRepository
from app.repositories.embedding_cache_repository import EmbeddingCacheRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.summary_repository import SummaryRepository
from app.repositories.telemetry_repository import TelemetryRepository
from app.tools.banking_tools import build_banking_tools
from app.tools.knowledge_tools import build_knowledge_tools
from app.tools.registry import ToolRegistry
from app.tools.scenario_tools import SCENARIO_TOOL


@lru_cache
def get_orchestrator() -> Orchestrator:
    settings = get_settings()
    client = get_service_client()

    conversations = ConversationRepository(client)
    messages = MessageRepository(client)
    summaries = SummaryRepository(client)
    memories = MemoryRepository(client)
    telemetry = TelemetryRepository(client)
    banking = BankingReadRepository(client)
    knowledge = KnowledgeRepository(client)
    embedding_cache = EmbeddingCacheRepository(client)
    attachments = AttachmentRepository(client)
    attachment_storage = AttachmentStorage(client, settings.attachments_bucket)

    chat_provider = MicrosoftFoundryChatProvider(settings)
    embedding_provider = MicrosoftFoundryEmbeddingProvider(settings)
    retrieval_service = RetrievalService(embedding_provider, knowledge, embedding_cache, settings.embedding_key)

    tools = ToolRegistry([*build_banking_tools(banking), SCENARIO_TOOL, *build_knowledge_tools(retrieval_service)])

    agents = {
        "financial_advisor": FinancialAdvisorAgent(),
        "transaction_intelligence": TransactionIntelligenceAgent(),
        "document_intelligence": DocumentIntelligenceAgent(),
        "engagement": EngagementAgent(),
        "compliance_kyc": ComplianceKycAgent(),
    }

    return Orchestrator(
        conversations=conversations, messages=messages, summaries=summaries, memories=memories,
        telemetry=telemetry, attachments=attachments, attachment_storage=attachment_storage,
        tool_registry=tools, agents=agents, router=AgentRouter(),
        chat_provider=chat_provider, environment=settings.environment,
        chat_price_in=settings.chat_price_per_million_input, chat_price_out=settings.chat_price_per_million_output,
    )


@lru_cache
def get_credit_service() -> CreditService:
    """Serviciul de creditare, construit o data.

    Primeste clientul cu service_role: tabelele credit_* nu accepta scrieri de la
    'authenticated', iar RPC-urile de operatiuni sunt revocate pentru orice alt rol.
    Detectorul de neregularitati e cel cu model de pe disc — acelasi artefact pe
    care il foloseste analiza de alerte, refolosit ca factor de scoring.
    """
    return CreditService(
        CreditRepository(get_service_client()),
        DetectorNeregularitati.cu_model_de_pe_disc(),
    )


@lru_cache
def get_conversation_repository() -> ConversationRepository:
    return ConversationRepository(get_service_client())


@lru_cache
def get_message_repository() -> MessageRepository:
    return MessageRepository(get_service_client())


@lru_cache
def get_attachment_service() -> AttachmentService:
    settings = get_settings()
    client = get_service_client()
    storage = AttachmentStorage(client, settings.attachments_bucket)
    return AttachmentService(storage, AttachmentRepository(client), settings.max_attachment_bytes)


def get_voice_provider() -> MicrosoftVoiceProvider:
    """Nu e cache-uit: constructorul verifica speech_configured la fiecare apel, ca o
    lipsa de configurare sa produca AI_PROVIDER_UNAVAILABLE curat, nu o eroare la pornire."""
    return MicrosoftVoiceProvider(get_settings())


# Valorile de rol acceptate ca administrator. Vezi este_admin() pentru de ce
# sunt doua, si migrarea 0011 pentru perechea corespunzatoare din SQL.
ROLURI_ADMIN = ("admin", "administrator")


@dataclass(frozen=True, slots=True)
class UserContext:
    user_id: UUID
    access_token: str


def _bearer_token(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Lipseste tokenul de autentificare.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


async def get_current_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> UserContext:
    token = _bearer_token(authorization)
    client = create_auth_client(settings)

    try:
        response = await to_thread.run_sync(client.auth.get_user, token)
        user = response.user
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesiunea este invalida sau a expirat.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilizator invalid.")

    return UserContext(user_id=UUID(str(user.id)), access_token=token)


def get_user_supabase(
    user: UserContext = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Client:
    return create_user_client(settings, user.access_token)


def get_admin_supabase() -> Client:
    """Clientul privilegiat, ca dependinta — ca sa poata fi inlocuit in teste."""
    return get_admin_client()


async def este_admin(user_id: UUID | str, client: Client) -> bool:
    """Are utilizatorul un rol de administrator in public.user_roles?

    Interogarea merge cu service-role dinadins: verificarea de drepturi nu
    trebuie sa depinda de politicile pe care tot ea le deblocheaza. Fiindca
    ocoleste RLS, raspunsul e folosit numai ca sa se decida daca cererea trece
    mai departe — datele propriu-zise se citesc dupa aceea cu clientul
    utilizatorului, unde RLS ramane a doua bariera.

    Se accepta doua valori fiindca ambele circula prin proiect: randurile reale,
    puse din consola, au 'admin', iar migrarea 0008 vorbeste despre
    'administrator'. Aceeasi pereche e acceptata si de public.este_administrator()
    in baza de date (0011), ca sa nu existe cont pe care Python il refuza si SQL
    il lasa sa treaca, sau invers.
    """

    def interogare() -> list[dict]:
        raspuns = (
            client.table("user_roles")
            .select("role")
            .eq("user_id", str(user_id))
            .in_("role", list(ROLURI_ADMIN))
            .limit(1)
            .execute()
        )
        return raspuns.data or []

    return bool(await to_thread.run_sync(interogare))


async def cere_administrator(
    user: UserContext = Depends(get_current_user),
    client_admin: Client = Depends(get_admin_supabase),
) -> UserContext:
    """Lasa sa treaca numai administratorii. Verificarea e mereu pe server.

    Ascunderea butonului in interfata nu e o bariera; oricine poate chema ruta
    direct. Rolul se citeste din baza de date la fiecare cerere, nu din token:
    un rol pus in JWT ar ramane valabil pana expira tokenul, inclusiv dupa ce
    i-a fost luat cuiva dreptul.

    Chiar daca verificarea de aici ar fi ocolita, RLS ramane bariera reala:
    politicile de pe credit_* si de pe identity_verifications cer
    public.este_administrator() in baza de date.

    Nota istorica: pana la unificare, functia citea din `profiles.rol` — o
    coloana care nu exista in proiectul real, fiindca migrarea 0008 n-a fost
    niciodata aplicata. Toate rutele de admin erau deci inchise pentru toata
    lumea. Rolurile traiesc in public.user_roles, si acolo se citesc.
    """
    try:
        admin = await este_admin(user.user_id, client_admin)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nu am putut verifica drepturile contului.",
        ) from exc

    if not admin:
        # Acelasi raspuns si cand contul nu are rol, si cand nu exista deloc:
        # cine incearca ruta nu trebuie sa afle ce a nimerit.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aceasta zona e disponibila numai administratorilor.",
        )

    return user
