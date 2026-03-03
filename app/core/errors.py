# app/core/errors.py
"""
역핑 표준 에러 코드.
"""
from __future__ import annotations
from fastapi import HTTPException
from typing import Any, Optional, Dict


class AppError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, detail: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status_code,
            detail={
                "code": code,
                "message": message,
                **({"detail": detail} if detail else {}),
            }
        )


class NotFound(AppError):
    def __init__(self, entity: str, entity_id: Any = None):
        d = {f"{entity}_id": entity_id} if entity_id is not None else None
        super().__init__(404, "NOT_FOUND", f"{entity}을(를) 찾을 수 없습니다", d)


class Conflict(AppError):
    def __init__(self, code: str, message: str, detail: Optional[Dict] = None):
        super().__init__(409, code, message, detail)


class Forbidden(AppError):
    def __init__(self, code: str = "FORBIDDEN", message: str = "권한이 없습니다"):
        super().__init__(403, code, message)


class BadRequest(AppError):
    def __init__(self, code: str, message: str, detail: Optional[Dict] = None):
        super().__init__(400, code, message, detail)


class AccountBanned(Forbidden):
    def __init__(self):
        super().__init__("ACCOUNT_BANNED", "계정이 정지되었습니다")


class AccountWithdrawn(Forbidden):
    def __init__(self):
        super().__init__("ACCOUNT_WITHDRAWN", "탈퇴한 계정입니다")
