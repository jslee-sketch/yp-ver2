# 에러 타입


class PolicyConfigError(RuntimeError):
    pass

class PolicyConfigValidationError(PolicyConfigError):
    pass

class PolicyParamNotFoundError(KeyError):
    def __init__(self, key: str):
        super().__init__(f"policy param not found: {key}")
        self.key = key

class PolicyParamTypeError(TypeError):
    def __init__(self, key: str, expected: str, got: str):
        super().__init__(f"policy param type mismatch: {key} expected={expected} got={got}")
        self.key = key
        self.expected = expected
        self.got = got