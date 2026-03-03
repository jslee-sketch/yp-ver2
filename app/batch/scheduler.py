# app/batch/scheduler.py
"""역핑 통합 배치 스케줄러. python -m app.batch.scheduler"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime

try:
    import schedule
except ImportError:
    print("[SCHEDULER] 'schedule' 패키지가 없습니다. pip install schedule 후 재실행하세요.")
    raise


def run_sync(name: str, func):
    print(f"[SCHEDULER] {datetime.now()} — {name}")
    try:
        func()
    except Exception as e:
        print(f"[SCHEDULER] {name} 실패: {e}")


def run_async(name: str, coro_func):
    print(f"[SCHEDULER] {datetime.now()} — {name}")
    try:
        asyncio.run(coro_func())
    except Exception as e:
        print(f"[SCHEDULER] {name} 실패: {e}")


def job_expire_reservations():
    try:
        import requests
        requests.post("http://127.0.0.1:9000/v3_6/maintenance/reservations/expire", timeout=5)
    except Exception:
        pass

def job_close_expired_deals():
    try:
        import requests
        requests.post("http://127.0.0.1:9000/deals/dev/close_expired", timeout=5)
    except Exception:
        pass

def job_refresh_settlements():
    try:
        import requests
        requests.post("http://127.0.0.1:9000/settlements/refresh-ready", timeout=10)
    except Exception:
        pass

def job_auto_approve_settlements():
    try:
        import requests
        requests.post("http://127.0.0.1:9000/settlements/batch-auto-approve", timeout=10)
    except Exception:
        pass

def job_delivery_check():
    from app.batch.delivery_check import check_deliveries
    run_async("delivery_check", check_deliveries)

def job_auto_arrival():
    from app.batch.auto_arrival_confirm import auto_confirm_arrivals
    run_sync("auto_arrival_confirm", auto_confirm_arrivals)

def job_review_request():
    from app.batch.review_request import send_review_requests
    run_sync("review_request", send_review_requests)

def job_daily_report():
    from app.batch.daily_report import generate_daily_report
    run_sync("daily_report", generate_daily_report)


def setup_schedule():
    schedule.every(10).minutes.do(job_expire_reservations)
    schedule.every(1).hours.do(job_close_expired_deals)
    schedule.every(2).hours.do(job_delivery_check)
    schedule.every(6).hours.do(job_refresh_settlements)
    schedule.every().day.at("02:00").do(job_auto_approve_settlements)
    schedule.every().day.at("03:00").do(job_auto_arrival)
    schedule.every().day.at("04:00").do(job_expire_reservations)
    schedule.every().day.at("10:00").do(job_review_request)
    schedule.every().day.at("08:00").do(job_daily_report)


if __name__ == "__main__":
    setup_schedule()
    print("[SCHEDULER] 역핑 배치 스케줄러 시작")
    while True:
        schedule.run_pending()
        time.sleep(30)
