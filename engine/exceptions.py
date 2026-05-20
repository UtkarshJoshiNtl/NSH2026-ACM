class AstrosisError(Exception):
    pass


class PropagationError(AstrosisError):
    pass


class TLEError(AstrosisError):
    pass


class ConjunctionError(AstrosisError):
    pass


class BackendError(AstrosisError):
    pass
