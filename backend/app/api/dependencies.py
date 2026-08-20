"""Compunerea aplicatiei: cladeste orchestratorul o singura data, din setari validate.

Nu e un singleton la nivel de modul (interzis de docs/PATTERN_ADOPTION.md) —
e o functie de fabrica, apelata prin FastAPI Depends, testabila prin
dependency_overrides.

Autentificarea (JWT/JWKS + modul cu cheie interna) nu e aici — traieste in
core/security.py, singurul loc care decodeaza un token in tot backend-ul.
"""

from __future__ import annotations

from functools import lru_cache

from app.agents.compliance_kyc import ComplianceKycAgent
from app.agents.document_intelligence import DocumentIntelligenceAgent
from app.agents.engagement import EngagementAgent
from app.agents.financial_advisor import FinancialAdvisorAgent
from app.agents.transaction_intelligence import TransactionIntelligenceAgent
from app.attachments.service import AttachmentService
from app.core.config import get_settings
from app.infrastructure.attachment_storage import AttachmentStorage
from app.infrastructure.supabase_client import get_service_client
from app.orchestration.orchestrator import Orchestrator
from app.orchestration.routing import AgentRouter
from app.providers.foundry import MicrosoftFoundryChatProvider, MicrosoftFoundryEmbeddingProvider
from app.providers.voice import MicrosoftVoiceProvider
from app.rag.retrieval import RetrievalService
from app.repositories.attachment_repository import AttachmentRepository
from app.repositories.banking_read_repository import BankingReadRepository
from app.repositories.conversation_repository import ConversationRepository
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
