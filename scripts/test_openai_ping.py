# scripts/test_openai_ping.py
from openai import OpenAI, RateLimitError
import os

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경변수가 비어 있습니다.")

    client = OpenAI()

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input="역핑 백엔드에서 보내는 테스트야. 'pong' 이라는 단어만 답해줘.",
        )
        text = resp.output[0].content[0].text
        print("✅ OpenAI 응답:", text)

    except RateLimitError as e:
        print("❌ RateLimitError 발생 (쿼터 부족):")
        print(e)
    except Exception as e:
        print("❌ 기타 에러:", repr(e))

if __name__ == "__main__":
    main()