# app/llm_client.py
from __future__ import annotations

import os
from typing import Any, Optional

# 한 번 만들어두고 계속 재사용할 전역 클라이언트
_client: Optional[Any] = None


def get_client() -> Any:
    """
    OpenAI 클라이언트를 lazy하게 생성해서 반환한다.

    - openai 패키지가 없거나
    - OPENAI_API_KEY 환경 변수가 없으면
      RuntimeError 를 명확한 메시지와 함께 발생시킨다.

    이 함수는 실제로 LLM을 쓸 때만 호출되므로,
    서버 import 시점에는 에러를 일으키지 않는다.
    """
    global _client
    if _client is not None:
        return _client

    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        raise RuntimeError(
            "openai 패키지가 설치되어 있지 않습니다. "
            "가상환경(venv)에서 `pip install openai` 실행 후 다시 시도하세요."
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY 환경 변수가 설정되어 있지 않습니다.\n"
            "PowerShell 예시:  $env:OPENAI_API_KEY=\"sk-...\""
        )

    _client = OpenAI(api_key=api_key)
    return _client