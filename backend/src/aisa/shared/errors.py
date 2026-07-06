class AppError(Exception):
    """Base for domain/application errors. Mapped to RFC 9457 problem+json at the API edge."""

    code: str = "internal_error"
    title: str = "Internal error"
    status: int = 500

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail
        super().__init__(detail or self.title)


class NotFoundError(AppError):
    code = "not_found"
    title = "Resource not found"
    status = 404


class ConflictError(AppError):
    code = "conflict"
    title = "Conflict"
    status = 409


class InvalidStateError(AppError):
    code = "invalid_state"
    title = "Invalid state transition"
    status = 409


class UnsupportedOperationError(AppError):
    code = "unsupported_operation"
    title = "Unsupported operation"
    status = 400
