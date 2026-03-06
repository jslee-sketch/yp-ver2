"""
비밀번호 재설정 이메일 발송 서비스
- SMTP 설정이 있으면 이메일 발송
- SMTP 미설정 시 콘솔 fallback (URL 출력)
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", "sales@tellustech.co.kr")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "역핑 (Yeokping)")


def _build_reset_html(reset_url: str) -> str:
    return f"""\
<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;margin:40px auto;background:#1a1a2e;border-radius:16px;overflow:hidden;">
    <tr>
      <td style="padding:36px 32px 24px;text-align:center;">
        <div style="font-size:28px;font-weight:900;letter-spacing:-1px;">
          <span style="color:#00e676;">역핑</span>
        </div>
        <div style="font-size:12px;color:#78909c;margin-top:4px;">원하는 가격으로, 함께</div>
      </td>
    </tr>
    <tr>
      <td style="padding:0 32px 24px;">
        <h2 style="color:#e8eaed;font-size:18px;margin:0 0 12px;">비밀번호 재설정 안내</h2>
        <p style="color:#adb5bd;font-size:14px;line-height:1.6;margin:0 0 24px;">
          아래 버튼을 클릭하면 새 비밀번호를 설정할 수 있습니다.<br>
          이 링크는 <strong style="color:#00e5ff;">30분</strong> 후 만료됩니다.
        </p>
        <div style="text-align:center;margin-bottom:24px;">
          <a href="{reset_url}"
             style="display:inline-block;padding:14px 36px;border-radius:12px;
                    background:linear-gradient(135deg,#00e676,#00e5ff);
                    color:#0a0a0f;font-size:15px;font-weight:800;
                    text-decoration:none;">
            비밀번호 재설정하기
          </a>
        </div>
        <p style="color:#78909c;font-size:12px;line-height:1.5;margin:0;">
          본인이 요청하지 않았다면 이 이메일을 무시해주세요.<br>
          버튼이 작동하지 않으면 아래 URL을 브라우저에 붙여넣기 해주세요:
        </p>
        <p style="color:#00e5ff;font-size:11px;word-break:break-all;margin:8px 0 0;">
          {reset_url}
        </p>
      </td>
    </tr>
    <tr>
      <td style="padding:20px 32px;border-top:1px solid rgba(255,255,255,0.06);text-align:center;">
        <span style="color:#78909c;font-size:11px;">&copy; 역핑 Yeokping &middot; tellustech.co.kr</span>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_reset_email(to_email: str, reset_url: str) -> bool:
    """
    비밀번호 재설정 이메일 발송.
    SMTP 미설정 시 콘솔에 URL 출력 후 True 반환.
    """
    if not SMTP_HOST or not SMTP_PASSWORD:
        print(f"[PASSWORD_RESET] SMTP not configured — console fallback")
        print(f"[PASSWORD_RESET] to={to_email}")
        print(f"[PASSWORD_RESET] url={reset_url}")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "[역핑] 비밀번호 재설정 안내"
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg["To"] = to_email

        plain = f"비밀번호 재설정 링크: {reset_url}\n이 링크는 30분 후 만료됩니다."
        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(_build_reset_html(reset_url), "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM_EMAIL, [to_email], msg.as_string())

        print(f"[PASSWORD_RESET] Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[PASSWORD_RESET] Email failed: {e}")
        print(f"[PASSWORD_RESET] Fallback URL for {to_email}: {reset_url}")
        return False
