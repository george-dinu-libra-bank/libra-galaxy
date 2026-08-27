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
from app.agents.credit_advisor import CreditAdvisorAgent
from app.agents.financial_advisor import FinancialAdvisorAgent
from app.agents.transaction_intelligence import TransactionIntelligenceAgent
from app.attachments.service import AttachmentService
from app.credit.ai.etape.explicatie import fabrica_explica
from app.credit.ai.pipeline import CreditAiPipeline
from app.services.credit_service import CreditService
from app.core.config import Settings, get_settings
from app.infrastructure.attachment_storage import AttachmentStorage
from app.infrastructure.export_storage import ExportStorage
from app.infrastructure.supabase import create_auth_client, create_user_client
from app.infrastructure.supabase_client import get_service_client
from app.ml.neregularitati import DetectorNeregularitati
from app.orchestration.orchestrator import Orchestrator
from app.orchestration.routing import AgentRouter
from app.agents.caz import AnalistCaz, ExtractorCaz, RedactorCaz
from app.providers.foundry import MicrosoftFoundryChatProvider, MicrosoftFoundryEmbeddingProvider
from app.repositories.admin_repository import AdminRepository, AnalizaRepository
from app.repositories.caz_repository import CazRepository
from app.services.caz_service import CazService
from app.providers.voice import MicrosoftVoiceProvider
from app.rag.retrieval import RetrievalService
from app.repositories.attachment_repository import AttachmentRepository
from app.repositories.banking_read_repository import BankingReadRepository
from app.repositories.card_repository import CardRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.credit_ai_repository import CreditAiRepository
from app.repositories.credit_repository import CreditRepository
from app.repositories.notificare_repository import NotificareRepository
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
from app.tools.notificari_tools import build_notificari_tools
from app.tools.credit_tools import build_credit_tools
from app.tools.knowledge_tools import build_knowledge_tools
from app.tools.registry import ToolRegistry
from app.tools.scenario_tools import SCENARIO_TOOL

# Valoarea din public.user_roles.role care da drepturi de administrator.
# Aceeasi in trei locuri care trebuie sa spuna acelasi lucru: aici, in
# frontend/src/lib/admin.ts si in public.este_administrator() din baza de date.
# Cand au fost diferite, oamenii intrau in interfata de admin si primeau 403 la
# fiecare apel.
ROL_ADMIN = "admin"


@lru_cache
def get_retrieval_service() -> RetrievalService:
    """RAG peste galaxy-bank-knowledge, partajat intre orchestratorul asistentului
    si etapa 'brief' a pipeline-ului AI de credite (app/credit/ai/etape/brief.py)
    — o singura implementare (REGULI.md #2), nu doua cautari separate peste
    aceleasi chunk-uri indexate."""
    settings = get_settings()
    client = get_service_client()
    embedding_provider = MicrosoftFoundryEmbeddingProvider(settings)
    knowledge = KnowledgeRepository(client)
    embedding_cache = EmbeddingCacheRepository(client)
    return RetrievalService(embedding_provider, knowledge, embedding_cache, settings.embedding_key)


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
    retrieval_service = get_retrieval_service()

    tools = ToolRegistry([
        *build_banking_tools(banking), *build_card_tools(cards), SCENARIO_TOOL,
        *build_knowledge_tools(retrieval_service),
        # Creditele erau singurul produs necunoscut asistentului: "de ce mi-a fost
        # respinsa cererea" cadea pe RAG si primea brosura produsului, nu dosarul
        # omului. Tool-urile sunt read-only; deciziile raman in CreditService.
        *build_credit_tools(CreditRepository(client)),
        # Fara mesajele bancii, un om caruia tocmai i s-a blocat contul intreaba
        # "de ce?" si primeste o generalitate: get_accounts spune CA e blocat,
        # dar motivul e in notificarea scrisa de analist.
        *build_notificari_tools(NotificareRepository(client)),
    ])

    agents = {
        "financial_advisor": FinancialAdvisorAgent(),
        "credit_advisor": CreditAdvisorAgent(),
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

    `explica=` e etapa 4 a pipeline-ului AI (app/credit/ai/etape/explicatie.py):
    rescrie textul determinist mai cald, cand Foundry e configurat si
    `LIBRA_CREDIT_AI_ENABLED` nu e dezactivat explicit. Fara asta, serviciul ramane
    pe deplin functional — `explica=None` e valoarea implicita din constructor.
    """
    settings = get_settings()
    explica = None
    if settings.credit_ai_enabled and settings.foundry_configured:
        explica = fabrica_explica(
            MicrosoftFoundryChatProvider(settings),
            telemetry=TelemetryRepository(get_service_client()),
            environment=settings.environment,
            price_per_million_in=settings.chat_price_per_million_input,
            price_per_million_out=settings.chat_price_per_million_output,
        )
    return CreditService(
        CreditRepository(get_service_client()),
        DetectorNeregularitati.cu_model_de_pe_disc(),
        explica=explica,
    )


@lru_cache
def get_credit_ai_repository() -> CreditAiRepository:
    return CreditAiRepository(get_service_client())


@lru_cache
def get_credit_ai_pipeline() -> CreditAiPipeline:
    """Etapele 1-3 (documente, coerenta, brief) — vezi app/credit/ai/pipeline.py.

    `structured_provider`/`retrieval_service` raman None cand Foundry nu e
    configurat sau pipeline-ul e dezactivat: 'coerenta' tot ruleaza (nu are
    nevoie de model), 'documente'/'brief' se marcheaza 'sarit', niciodata nu
    darama fluxul de credit (ARCHITECTURE.md #10).
    """
    settings = get_settings()
    structured_provider = (
        MicrosoftFoundryChatProvider(settings)
        if settings.credit_ai_enabled and settings.foundry_configured
        else None
    )
    retrieval_service = get_retrieval_service() if structured_provider is not None else None

    return CreditAiPipeline(
        credit_service=get_credit_service(),
        repository=get_credit_ai_repository(),
        structured_provider=structured_provider,
        retrieval_service=retrieval_service,
        environment=settings.environment,
        price_per_million_in=settings.chat_price_per_million_input,
        price_per_million_out=settings.chat_price_per_million_output,
        max_semnale=settings.credit_ai_max_semnale,
    )



@lru_cache
def get_caz_service() -> CazService:
    """Investigatia de frauda, cu cei trei agenti ai ei (app/agents/caz/).

    Primeste clientul de service_role: `caz_investigatie`, `caz_tranzactie` si
    `caz_mesaj` au din 0051 doar politici de SELECT, deci nicio scriere nu poate
    veni de la un client, oricat ar avea tokenul lui valid.

    Agentii sunt None cand Foundry nu e configurat, si atunci fluxul merge fara
    ei: administratorul scrie singur mesajul catre client si citeste raspunsul
    cu ochii lui. Investigatia e o procedura a bancii, nu o functie a modelului
    — daca ar cadea odata cu providerul, ar fi construita gresit.
    """
    settings = get_settings()
    client = get_service_client()

    redactor = extractor = analist = None
    if settings.foundry_configured:
        provider = MicrosoftFoundryChatProvider(settings)
        redactor = RedactorCaz(provider)
        extractor = ExtractorCaz(provider)
        analist = AnalistCaz(provider)

    return CazService(
        CazRepository(client),
        AnalizaRepository(client),
        AdminRepository(client),
        redactor=redactor,
        extractor=extractor,
        analist=analist,
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


def get_admin_supabase() -> Client:
    """Clientul privilegiat, ca dependinta — ca sa poata fi inlocuit in teste.

    Trece peste RLS, deci orice ruta care il foloseste isi verifica singura
    drepturile: baza de date nu o mai face in locul ei. Folosit de rutele care
    scriu in tabele fara politica de insert (analize_cont, notificari), tocmai
    ca scrierea sa nu poata veni din alta parte.
    """
    return get_service_client()


async def cere_administrator(
    user: UserContext = Depends(get_current_user),
    client: Client = Depends(get_user_supabase),
) -> UserContext:
    """Lasa sa treaca numai administratorii.

    Rolul se citeste din `public.user_roles(user_id, role)`, singura sursa de
    adevar pentru drepturi (vezi ROL_ADMIN). Verificarea intreaba baza de date,
    nu tokenul: un rol pus in JWT ar fi mai ieftin de citit, dar ar ramane
    valabil pana expira tokenul, inclusiv dupa ce i-a fost luat cuiva dreptul.
    Varianta si mai veche citea `profiles.rol`, ramas in urma fata de user_roles
    si inghetat de trigger-ul `profiles_protejeaza_campuri`: aceiasi oameni erau
    'admin' intr-o parte si 'client' in cealalta, deci frontendul ii lasa in
    ecranul de administrare iar backendul le raspundea 403.

    Chiar daca cineva ar ocoli verificarea de aici, RLS ramane bariera reala:
    politicile din 0009 cer public.este_administrator(), care citeste aceeasi
    tabela si aceeasi valoare.

    Interogarea merge cu tokenul utilizatorului, deci trece prin politica
    "Enable users to view their own data only" de pe user_roles: fiecare isi
    vede doar propriul rand, iar cine n-are niciunul primeste zero randuri.

    Se filtreaza pe rol si se ia `limit(1)`, **nu** `maybe_single()`: tabela
    n-are index unic pe (user_id, role), deci acelasi om poate aparea de doua
    ori. S-a intamplat: un rand duplicat a facut `maybe_single()` sa arunce si
    l-a dat afara pe un administrator adevarat. `limit(1)` nu are cum.
    """

    def interogare() -> bool:
        raspuns = (
            client.table("user_roles")
            .select("role")
            .eq("user_id", str(user.user_id))
            .eq("role", ROL_ADMIN)
            .limit(1)
            .execute()
        )
        return bool(raspuns.data) if raspuns else False

    try:
        este_admin = await to_thread.run_sync(interogare)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nu am putut verifica drepturile contului.",
        ) from exc

    if not este_admin:
        # Acelasi raspuns si cand contul nu exista, si cand exista dar e client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aceasta zona e disponibila numai administratorilor.",
        )

    return user
