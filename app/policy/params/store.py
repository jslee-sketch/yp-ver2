# 읽기 API (get_param, require_param)


from __future__ import annotations
from typing import Any, Optional, cast

from .loader import PolicyParamsLoader
from .errors import PolicyParamNotFoundError, PolicyParamTypeError

_loader = PolicyParamsLoader()

def set_loader(loader: PolicyParamsLoader) -> None:
    global _loader
    _loader = loader

def get_param_spec(key: str):
    loaded = _loader.load()
    spec = loaded.parsed.params.get(key)
    if spec is None:
        raise PolicyParamNotFoundError(key)
    return spec

def get_value(key: str) -> Any:
    return get_param_spec(key).value

def get_int(key: str) -> int:
    spec = get_param_spec(key)
    if spec.type != "int":
        raise PolicyParamTypeError(key, expected="int", got=spec.type)
    return cast(int, spec.value)

def get_float(key: str) -> float:
    spec = get_param_spec(key)
    if spec.type not in ("float", "int"):
        raise PolicyParamTypeError(key, expected="float|int", got=spec.type)
    return float(spec.value)

def get_bool(key: str) -> bool:
    spec = get_param_spec(key)
    if spec.type != "bool":
        raise PolicyParamTypeError(key, expected="bool", got=spec.type)
    return cast(bool, spec.value)

def get_str(key: str) -> str:
    spec = get_param_spec(key)
    if spec.type not in ("str", "enum"):
        raise PolicyParamTypeError(key, expected="str|enum", got=spec.type)
    return cast(str, spec.value)

def get_version_hash() -> str:
    loaded = _loader.load()
    return loaded.content_hash