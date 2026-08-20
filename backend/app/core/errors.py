"""Ierarhie de erori -> cod stabil -> status HTTP (docs/API_CONVENTIONS.md #2)."""

from __future__ import annotations


class AppError(Exception):
    code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    status_code = 422


class AuthRequiredError(AppError):
    code = "AUTH_REQUIRED"
    status_code = 401


class AuthInvalidError(AppError):
    code = "AUTH_INVALID"
    status_code = 401


class PermissionDeniedError(AppError):
    code = "PERMISSION_DENIED"
    status_code = 403


class ResourceNotFoundError(AppError):
    code = "RESOURCE_NOT_FOUND"
    status_code = 404


class ConfigurationError(AppError):
    code = "CONFIGURATION_ERROR"
    status_code = 500


class PersistenceError(AppError):
    code = "PERSISTENCE_ERROR"
    status_code = 503


class AiProviderError(AppError):
    code = "AI_PROVIDER_ERROR"
    status_code = 502


class AiProviderUnavailableError(AppError):
    code = "AI_PROVIDER_UNAVAILABLE"
    status_code = 503


class AgentNotAvailableError(AppError):
    code = "AGENT_NOT_AVAILABLE"
    status_code = 503


class AgentExecutionError(AppError):
    code = "AGENT_EXECUTION_ERROR"
    status_code = 502


class ToolTimeoutError(AppError):
    code = "TOOL_TIMEOUT"
    status_code = 504


class ToolExecutionError(AppError):
    code = "TOOL_EXECUTION_ERROR"
    status_code = 502


class RetrievalError(AppError):
    code = "RETRIEVAL_ERROR"
    status_code = 503


class IdentityImageDownloadError(AppError):
    code = "IDENTITY_IMAGE_DOWNLOAD_FAILED"
    status_code = 502


class IdentityResultWriteError(AppError):
    code = "IDENTITY_RESULT_WRITE_FAILED"
    status_code = 502
