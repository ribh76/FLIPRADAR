from dataclasses import dataclass


@dataclass(eq=False)
class ServiceError(Exception):
    message: str
    status_code: int = 400

    def __str__(self) -> str:
        return self.message


class ServiceNotFoundError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=404)


class ServiceConflictError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=409)


class ServiceValidationError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=400)


class ServiceIncompleteDataError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=422)


class ServiceProviderError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=502)


class ServiceProviderUnavailableError(ServiceError):
    """The requested provider is disabled or has no usable credentials."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=503)


class ServiceEmailDeliveryError(ServiceError):
    """A required transactional email could not be accepted for delivery."""

    def __init__(
        self, message: str = "We couldn't deliver the email. Please try again."
    ) -> None:
        super().__init__(message=message, status_code=503)


class ServiceProviderTimeoutError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=504)


class ServiceDatabaseError(ServiceError):
    def __init__(self, message: str = "Database operation failed") -> None:
        super().__init__(message=message, status_code=500)
