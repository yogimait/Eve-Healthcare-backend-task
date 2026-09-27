class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: object = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


ERROR_STATUS = {
    "VALIDATION_ERROR": 422,
    "UNAUTHORIZED": 401,
    "INVALID_CREDENTIALS": 401,
    "INVALID_TOKEN": 401,
    "WEBHOOK_INVALID_SIGNATURE": 401,
    "FORBIDDEN": 403,
    "ADMIN_REQUIRED": 403,
    "BOOKING_NOT_OWNED": 403,
    "NOT_FOUND": 404,
    "CENTRE_NOT_FOUND": 404,
    "TEST_NOT_FOUND": 404,
    "BOOKING_NOT_FOUND": 404,
    "PAYMENT_NOT_FOUND": 404,
    "EMAIL_TAKEN": 409,
    "TEST_ALREADY_OFFERED": 409,
    "TEST_NOT_AVAILABLE": 409,
    "SLOT_UNAVAILABLE": 409,
    "INVALID_STATE_TRANSITION": 409,
    "BOOKING_NOT_PENDING": 409,
    "PAYMENT_ALREADY_IN_PROGRESS": 409,
    "INVALID_APPOINTMENT": 422,
    "RATE_LIMITED": 429,
    "INTERNAL_ERROR": 500,
    "NOT_IMPLEMENTED": 501,
}


def app_error(code: str, message: str, details: object = None) -> AppError:
    status = ERROR_STATUS.get(code, 400)
    return AppError(code=code, message=message, status_code=status, details=details)
