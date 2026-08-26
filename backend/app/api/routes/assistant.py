from __future__ import annotations

import asyncio
import base64
import logging

from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.agents.specs import ALL_AGENT_SPECS
from app.api.dependencies import (
    get_attachment_repository,
    get_attachment_service,
    get_conversation_repository,
    get_export_storage,
    get_message_repository,
    get_orchestrator,
    get_voice_provider,
)
from app.attachments.service import AttachmentService
from app.core.config import Settings, get_settings
from app.core.envelope import new_request_id, success
from app.core.errors import ValidationError
from app.core.security import Principal, get_principal
from app.infrastructure.export_storage import ExportStorage
from app.infrastructure.rate_limit import limiteaza
from app.orchestration.orchestrator import Orchestrator
from app.providers.voice import MicrosoftVoiceProvider
from app.repositories.attachment_repository import AttachmentRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.assistant import (
    AgentCapabilityOut,
    AttachmentOut,
    CapabilitiesResponse,
    CitationOut,
    ConversationOut,
    GeneratedFileOut,
    MessageOut,
    QuickActionOut,
    SendMessageRequest,
    SendMessageResponse,
    VoiceMessageResponse,
)

logger = logging.getLogger("libra.assistant")

router = APIRouter(prefix="/assistant")


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID") or new_request_id()


def _quick_action_out(data: dict | None) -> QuickActionOut | None:
    return QuickActionOut(**data) if data else None


def _quick_action_out_from_result(quick_action) -> QuickActionOut | None:
    if quick_action is None:
        return None
    return QuickActionOut(
        kind=quick_action.kind,
        accounts=[
            {"id": account.id, "name": account.name, "iban": account.iban, "currency": account.currency}
            for account in quick_action.accounts
        ],
        url=quick_action.url,
    )


async def _sinteza_optionala(text: str, locale: str) -> str | None:
    """Sinteza vocala, la cerere, pentru un mesaj text (SendMessageRequest.tts).

    Best-effort: daca Azure AI Speech nu e configurat sau esueaza, raspunsul
    text tot ajunge la utilizator — doar fara audio, nu se pierde intreg
    mesajul pentru o functie optionala."""
    if not text.strip():
        return None
    try:
        voice_provider = get_voice_provider()
        audio = await voice_provider.synthesize(text, locale)
        return base64.b64encode(audio).decode("ascii")
    except Exception:
        logger.exception("sinteza vocala optionala a esuat; raspunsul merge doar ca text")
        return None


def _limiteaza_mesaje_asistent(user_id: str) -> None:
    """Aceeasi cheie pentru text si voce (GUARDRAILS.md #29) — altfel un
    utilizator ar putea ocoli limita trecand pe celalalt canal, desi ambele
    consuma acelasi buget de apeluri LLM. 30/300s, nu 5/300s ca la login-match:
    aici utilizatorul e deja autentificat si poate trimite legitim mai multe
    intrebari rapide la rand, dar fiecare mesaj costa un apel LLM real."""
    limiteaza(f"assistant-messages:user:{user_id}", max_incercari=30, fereastra_secunde=300)


@router.post("/messages")
async def send_message(
    request: Request,
    body: SendMessageRequest,
    principal: Principal = Depends(get_principal),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    _limiteaza_mesaje_asistent(principal.user_id)
    result = await orchestrator.handle_message(
        principal, body.conversation_id, body.text, attachment_ids=body.attachment_ids, channel="text"
    )
    audio_base64 = await _sinteza_optionala(result.text, principal.locale) if body.tts else None

    response = SendMessageResponse(
        conversation_id=result.conversation_id, message_id=result.message_id, text=result.text,
        citations=[CitationOut(**citation) for citation in result.citations], confidence=result.confidence,
        agent_id=result.agent_id,
        file=GeneratedFileOut(url=result.generated_file.url, filename=result.generated_file.filename,
                               kind=result.generated_file.kind) if result.generated_file else None,
        quick_action=_quick_action_out_from_result(result.quick_action),
        audio_base64=audio_base64,
    )
    return success(response.model_dump(), request_id=_request_id(request))


@router.post("/voice-messages")
async def send_voice_message(
    request: Request,
    audio: UploadFile = File(...),
    conversation_id: str | None = None,
    principal: Principal = Depends(get_principal),
    orchestrator: Orchestrator = Depends(get_orchestrator),
    voice_provider: MicrosoftVoiceProvider = Depends(get_voice_provider),
):
    _limiteaza_mesaje_asistent(principal.user_id)
    audio_bytes = await audio.read()
    text = await voice_provider.transcribe(audio_bytes, audio.content_type or "audio/wav", principal.locale)

    if not text.strip():
        raise ValidationError("Nu am inteles nimic din inregistrare — incearca din nou.")

    result = await orchestrator.handle_message(principal, conversation_id, text, channel="voce")
    audio_reply = await voice_provider.synthesize(result.text, principal.locale)

    response = VoiceMessageResponse(
        conversation_id=result.conversation_id, message_id=result.message_id, text=result.text,
        citations=[CitationOut(**citation) for citation in result.citations], confidence=result.confidence,
        agent_id=result.agent_id, audio_base64=base64.b64encode(audio_reply).decode("ascii"),
        quick_action=_quick_action_out_from_result(result.quick_action),
    )
    return success(response.model_dump(), request_id=_request_id(request))


@router.post("/attachments")
async def upload_attachment(
    request: Request,
    file: UploadFile = File(...),
    principal: Principal = Depends(get_principal),
    service: AttachmentService = Depends(get_attachment_service),
):
    content = await file.read()
    attachment = await service.upload(principal.user_id, file.filename or "fisier", file.content_type or "", content)

    response = AttachmentOut(
        id=attachment.id, kind=attachment.kind, filename=attachment.filename, size_bytes=attachment.size_bytes
    )
    return success(response.model_dump(), request_id=_request_id(request))


@router.get("/conversations")
async def list_conversations(
    request: Request,
    principal: Principal = Depends(get_principal),
    conversations: ConversationRepository = Depends(get_conversation_repository),
):
    rows = await conversations.list_for_user(principal.user_id)
    body = [ConversationOut(id=row.id, title=row.title, updated_at=row.updated_at).model_dump() for row in rows]
    return success(body, request_id=_request_id(request))


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    request: Request,
    conversation_id: str,
    principal: Principal = Depends(get_principal),
    conversations: ConversationRepository = Depends(get_conversation_repository),
):
    await conversations.delete_owned(principal.user_id, conversation_id)
    return success({"deleted": True}, request_id=_request_id(request))


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(
    request: Request,
    conversation_id: str,
    principal: Principal = Depends(get_principal),
    conversations: ConversationRepository = Depends(get_conversation_repository),
    messages: MessageRepository = Depends(get_message_repository),
    attachments: AttachmentRepository = Depends(get_attachment_repository),
    export_storage: ExportStorage = Depends(get_export_storage),
    settings: Settings = Depends(get_settings),
):
    await conversations.get_owned(principal.user_id, conversation_id)  # ridica RESOURCE_NOT_FOUND daca nu e a lui
    rows = await messages.list_for_conversation(conversation_id)

    # URL-ul semnat nu se persista (ar expira la o reincarcare mai tarzie) —
    # se remintuieste proaspat la fiecare citire, exact tiparul
    # identity_repository.url_semnat pentru pozele de buletin/selfie.
    generated = await attachments.list_generated_for_messages([row.id for row in rows])
    urls = await asyncio.gather(
        *(export_storage.create_signed_url(record.storage_path, settings.export_signed_url_seconds)
          for record in generated)
    )
    files_by_message = {
        record.message_id: GeneratedFileOut(url=url, filename=record.filename, kind="pdf")
        for record, url in zip(generated, urls)
    }

    body = [
        MessageOut(
            id=row.id, role=row.role, text=row.text,
            citations=[CitationOut(**citation) for citation in row.citations],
            confidence=row.confidence, channel=row.channel, created_at=row.created_at,
            file=files_by_message.get(row.id),
            quick_action=_quick_action_out(row.quick_action),
        ).model_dump()
        for row in rows
    ]
    return success(body, request_id=_request_id(request))


@router.get("/capabilities")
async def capabilities(request: Request, _principal: Principal = Depends(get_principal)):
    body = CapabilitiesResponse(
        agents=[
            AgentCapabilityOut(agent_id=spec.agent_id, purpose=spec.purpose, tools=sorted(spec.tool_names))
            for spec in ALL_AGENT_SPECS
        ]
    )
    return success(body.model_dump(), request_id=_request_id(request))
