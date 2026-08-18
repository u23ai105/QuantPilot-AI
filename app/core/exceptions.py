import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


class QuantPilotException(Exception):
    def __init__(self, message: str, status_code: int, error_code: str):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class ValidationError(QuantPilotException):
    def __init__(self, message: str):
        super().__init__(message, 400, "VALIDATION_ERROR")


class AuthenticationError(QuantPilotException):
    def __init__(self, message: str = "Not authenticated"):
        super().__init__(message, 401, "AUTHENTICATION_ERROR")


class AuthorizationError(QuantPilotException):
    def __init__(self, message: str = "Not authorized"):
        super().__init__(message, 403, "AUTHORIZATION_ERROR")


class NotFoundError(QuantPilotException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, 404, "NOT_FOUND_ERROR")


class ConflictError(QuantPilotException):
    def __init__(self, message: str = "Resource already exists"):
        super().__init__(message, 409, "CONFLICT")


class DataProviderError(QuantPilotException):
    def __init__(self, message: str = "Data provider error"):
        super().__init__(message, 502, "DATA_PROVIDER_ERROR")


async def quantpilot_exception_handler(request: Request, exc: QuantPilotException):
    logger.warning("app_exception", error_code=exc.error_code, message=exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.error_code, "message": exc.message}},
    )


async def global_exception_handler(request: Request, exc: Exception):
    logger.error("internal_error", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal server error occurred",
            }
        },
    )
