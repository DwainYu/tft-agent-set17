from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Base application exception with HTTP status code and detail message."""

    def __init__(self, status_code: int = 500, detail: str = "Internal server error"):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class AuthException(AppException):
    """Raised when authentication or authorization fails (401)."""

    def __init__(self, detail: str = "Authentication required"):
        super().__init__(status_code=401, detail=detail)


class NotFoundException(AppException):
    """Raised when a requested resource is not found (404)."""

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=404, detail=detail)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """FastAPI exception handler that converts AppException into a JSON response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )
