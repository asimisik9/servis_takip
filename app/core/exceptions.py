class ServiceException(Exception):
    """Base class for service layer exceptions"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class ResourceNotFoundException(ServiceException):
    """Raised when a requested resource is not found"""
    pass

class BusinessRuleException(ServiceException):
    """Raised when a business rule is violated"""
    pass
