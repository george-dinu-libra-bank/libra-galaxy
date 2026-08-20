"""Azure AI Speech (REST) — transcribe si synthesize, canal separat de Foundry (PROJECT_CONTEXT.md #33).

O singura implementare, fara fallback, la fel ca celelalte provideri
(docs/decisions/0003-no-provider-fallback.md). Foloseste REST direct (cu
cheia de subscriptie), nu SDK-ul nativ, ca sa evite dependinte binare
suplimentare pentru un serviciu opțional.
"""

from __future__ import annotations

import html

import httpx

from app.core.config import Settings
from app.core.errors import AiProviderError, AiProviderUnavailableError

_LOCALE_TO_VOICE_LANGUAGE = {"ro": "ro-RO", "en": "en-US"}


class MicrosoftVoiceProvider:
    def __init__(self, settings: Settings) -> None:
        if not settings.speech_configured:
            raise AiProviderUnavailableError("Azure AI Speech nu este configurat.")

        self._key = settings.speech_key
        self._region = settings.speech_region
        self._endpoint_override = settings.speech_endpoint
        self._voice_name = settings.speech_voice_name

    def _stt_url(self, locale: str) -> str:
        language = _LOCALE_TO_VOICE_LANGUAGE.get(locale, "ro-RO")
        base = self._regional_base("stt")
        return f"{base}/speech/recognition/conversation/cognitiveservices/v1?language={language}"

    def _tts_url(self) -> str:
        return f"{self._regional_base('tts')}/cognitiveservices/v1"

    def _regional_base(self, service: str) -> str:
        # Endpoint-ul de resursa (cognitiveservices.azure.com) nu raspunde pe
        # aceste cai REST (404, verificat live) — doar domeniul regional
        # functioneaza, deci regiunea are prioritate cand exista.
        if self._region:
            return f"https://{self._region}.{service}.speech.microsoft.com"
        return self._endpoint_override.rstrip("/")

    async def transcribe(self, audio_bytes: bytes, content_type: str, locale: str) -> str:
        headers = {"Ocp-Apim-Subscription-Key": self._key, "Content-Type": content_type, "Accept": "application/json"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(self._stt_url(locale), headers=headers, content=audio_bytes)
            except httpx.HTTPError as exc:
                raise AiProviderUnavailableError("Azure AI Speech este inaccesibil.") from exc

        if response.status_code != 200:
            raise AiProviderError(f"Azure AI Speech (STT) a raspuns cu status {response.status_code}.")

        payload = response.json()
        return payload.get("DisplayText", "")

    async def synthesize(self, text: str, locale: str) -> bytes:
        language = _LOCALE_TO_VOICE_LANGUAGE.get(locale, "ro-RO")
        ssml = (
            f"<speak version='1.0' xml:lang='{language}'>"
            f"<voice name='{self._voice_name}'>{html.escape(text)}</voice></speak>"
        )
        headers = {
            "Ocp-Apim-Subscription-Key": self._key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(self._tts_url(), headers=headers, content=ssml.encode("utf-8"))
            except httpx.HTTPError as exc:
                raise AiProviderUnavailableError("Azure AI Speech este inaccesibil.") from exc

        if response.status_code != 200:
            raise AiProviderError(f"Azure AI Speech (TTS) a raspuns cu status {response.status_code}.")

        return response.content
