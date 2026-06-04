import os
import time
import requests
from datetime import datetime, timedelta, timezone

# ==========================================
# [설정 정보]
# ==========================================
TELEGRAM_BOT_TOKEN = "8682869478:AAGHyOOpeZtuAlDV9JMmg3eXQTFhswydFaw"
TELEGRAM_CHAT_ID = "8456543788"
CHECK_INTERVAL_MINUTES = 40  # 40분 주기

# 감시할 파일 리스트
WATCH_LIST = [
    r"\\Dhcmain\(주)대호스토퍼\0영업사항(견적서)\●영업관리\1. 계약건(21).xlsx",
    r"\\Dhcmain\(주)대호스토퍼\0영업사항(견적서)\●영업관리\2. 특허,공고,입찰.xlsx"
]

# 한국 표준시(KST) 구하기 위한 타임존 설정
KST = timezone(timedelta(hours=9))

def send_telegram_message(message):
    """텔레그램 봇을 통해 메시지를 전송합니다."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[{get_now_str()}] 엑셀 봇 텔레그램 발송 실패: {e}")

def get_now_str():
    return datetime.now(KST).strftime("%H:%M:%S")

def format_time_12h(timestamp):
    """타임스탬프를 날짜(YY-MM-DD)와 오전/오후 12시간제로 변환"""
    dt = datetime.fromtimestamp(timestamp, tz=KST)
    # %y-%m-%d 를 추가하여 '26-06-04' 형태의 날짜를 맨 앞에 붙입니다.
    time_str = dt.strftime('%y-%m-%d %p %I:%M:%S') 
    return time_str.replace('AM', '오전').replace('PM', '오후')

def run_monitor(refresh_event=None):
    """엑셀 파일 모니터링 핵심 루프"""
    last_mtimes = {}
    initial_status = []
    
    print(f"[{get_now_str()}] 영업관리 엑셀 감시를 시작합니다.")
    
    # 1. 초기 상태 확인
    for path in WATCH_LIST:
        if os.path.exists(path):
            try:
                mtime = os.path.getmtime(path)
                last_mtimes[path] = mtime
                file_name = os.path.basename(path)
                formatted_time = format_time_12h(mtime)
                initial_status.append(f"📄 <b>{file_name}</b>\n(최근 수정: {formatted_time})")
            except Exception as e:
                print(f"[{get_now_str()}] {os.path.basename(path)} 접근 권한 오류: {e}")
        else:
            print(f"[{get_now_str()}] ⚠️ 파일을 찾을 수 없음: {path}")

    if not last_mtimes:
        msg = "❌ <b>[영업관리]</b> 감시할 수 있는 파일이 없습니다. 회사 네트워크 연결을 확인해주세요."
        send_telegram_message(msg)
        print(msg)
        return

    # 시작 알림 전송
    start_msg = "🚀 <b>[영업관리 엑셀] 감시 시작</b>\n\n" + "\n\n".join(initial_status)
    send_telegram_message(start_msg)
    
    while True:
        try:
            # 다른 봇들과 동일하게 알람벨(refresh_event) 연동!
            if refresh_event:
                refresh_event.wait(CHECK_INTERVAL_MINUTES * 60)
            else:
                time.sleep(CHECK_INTERVAL_MINUTES * 60)
            
            updated_files = []
            now_12h = format_time_12h(time.time())

            for path in WATCH_LIST:
                if os.path.exists(path):
                    try:
                        current_mtime = os.path.getmtime(path)
                        # 수정 시간이 기존 기록과 다르면 업데이트된 것으로 간주
                        if path not in last_mtimes or current_mtime != last_mtimes[path]:
                            file_name = os.path.basename(path)
                            updated_files.append(file_name)
                            last_mtimes[path] = current_mtime
                    except Exception as e:
                        print(f"[{get_now_str()}] 파일 접근 오류: {e}")
                else:
                    # 네트워크 드라이브 끊김 등 예외 처리
                    pass

            # 업데이트 발생 시 알림 발송
            if updated_files:
                msg = f"🔔 <b>[영업관리 업데이트 알림]</b>\n확인 시간: {now_12h}\n"
                for f in updated_files:
                    msg += f"\n✅ {f}"
                send_telegram_message(msg)
                print(f"[{get_now_str()}] 엑셀 업데이트 발견 및 전송 완료")
            else:
                print(f"[{get_now_str()}] 엑셀 파일 변동 없음")
                
        except Exception as e:
            print(f"[{get_now_str()}] 엑셀 루프 실행 중 에러: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_monitor()