class ServiceError(Exception):
    pass


class ConfigNotFound(ServiceError):
    pass


class FlagNotFound(ServiceError):
    pass
