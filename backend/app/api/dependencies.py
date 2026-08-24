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
from app.infrastructure.export_storage import ExportStorage
from app.infrastructure.supabase import create_auth_client, create_user_client
from app.infrastructure.supabase_client import get_service_client
from app.ml.neregularitati import DetectorNeregularitati
from app.orchestration.orchestrator import Orchestrator
from app.orchestration.routing import AgentRouter
from app.providers.foundry import MicrosoftFoundryChatProvider, MicrosoftFoundryEmbeddingProvider
from app.providers.voice import MicrosoftVoiceProvider
from app.rag.retrieval import RetrievalService
from app.repositories.attachment_repository import AttachmentRepository
from app.repositories.banking_read_repository import BankingReadRepository
from app.repositories.card_repository import CardRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.credit_repository import CreditRepository
from app.repositories.embedding_cache_repository import EmbeddingCacheRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.summary_repository import SummaryRepository
from app.repositories.telemetry_repository import TelemetryRepository
from app.services.transaction_export_service import TransactionExportService
from app.tools.banking_tools import build_banking_tools
from app.tools.card_tools import build_card_tools
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
    cards = CardRepository(client)
    profiles = ProfileRepository(client)
    knowledge = KnowledgeRepository(client)
    embedding_cache = EmbeddingCacheRepository(client)
    attachments = AttachmentRepository(client)
    attachment_storage = AttachmentStorage(client, settings.attachments_bucket)
    export_storage = ExportStorage(client, settings.export_bucket)
    export_service = TransactionExportService(banking, export_storage, settings.export_signed_url_seconds)

    chat_provider = MicrosoftFoundryChatProvider(settings)
    embedding_provider = MicrosoftFoundryEmbeddingProvider(settings)
    retrieval_service = RetrievalService(embedding_provider, knowledge, embedding_cache, settings.embedding_key)

    tools = ToolRegistry([
        *build_banking_tools(banking), *build_card_tools(cards), SCENARIO_TOOL, *build_knowledge_tools(retrieval_service),
    ])

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
        export_service=export_service, banking=banking, profiles=profiles,
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


@lru_cache
def get_attachment_repository() -> AttachmentRepository:
    return AttachmentRepository(get_service_client())


@lru_cache
def get_export_storage() -> ExportStorage:
    settings = get_settings()
    return ExportStorage(get_service_client(), settings.export_bucket)


def get_voice_provider() -> MicrosoftVoiceProvider:
    """Nu e cache-uit: constructorul verifica speech_configured la fiecare apel, ca o
    lipsa de configurare sa produca AI_PROVIDER_UNAVAILABLE curat, nu o eroare la pornire."""
    return MicrosoftVoiceProvider(get_settings())


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


async def cere_administrator(
    user: UserContext = Depends(get_current_user),
    client: Client = Depends(get_user_supabase),
) -> UserContext:
    """Lasa sa treaca numai administratorii.

    Verificarea intreaba baza de date, nu tokenul: rolul sta in profiles si e
    inghetat de trigger, deci nu poate fi ridicat din aplicatie. Un rol pus in
    JWT ar fi mai ieftin de citit, dar ar ramane valabil pana expira tokenul,
    inclusiv dupa ce i-a fost luat cuiva dreptul.

    Chiar daca cineva ar ocoli verificarea de aici, RLS ramane bariera reala:
    politicile de la 0008 cer public.este_administrator() in baza de date.
    """

    def interogare() -> str | None:
        raspuns = (
            client.table("profiles")
            .select("rol")
            .eq("id", str(user.user_id))
            .maybe_single()
            .execute()
        )
        date = raspuns.data if raspuns else None
        return date.get("rol") if date else None

    try:
        rol = await to_thread.run_sync(interogare)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nu am putut verifica drepturile contului.",
        ) from exc

    if rol != "administrator":
        # Acelasi raspuns si cand contul nu exista, si cand exista dar e client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aceasta zona e disponibila numai administratorilor.",
        )

    return user
