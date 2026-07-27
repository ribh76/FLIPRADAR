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


class ServiceDatabaseError(ServiceError):
    def __init__(self, message: str = "Database operation failed") -> None:
        super().__init__(message=message, status_code=500)
