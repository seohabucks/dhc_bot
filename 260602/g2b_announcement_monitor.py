import time
import json
import os
import requests
from datetime import datetime, timedelta, timezone

# ==========================================
# [설정 정보] - 본인의 정보에 맞게 수정해주세요.
# ==========================================
TELEGRAM_BOT_TOKEN = "8682869478:AAGHyOOpeZtuAlDV9JMmg3eXQTFhswydFaw"  # 텔레그램 BotFather에게 받은 토큰
TELEGRAM_CHAT_ID = "8456543788" 
CHECK_INTERVAL_MINUTES = 40

# 공공데이터포털(data.go.kr)에서 발급받은 일반 인증키 (Decoding 또는 Encoding 키 중 작동하는 것 사용)
SERVICE_KEY = "b6f3dcb33a0e5b9651bd8b90d8b7e108bf24d17d587a9d8f2682f3c50fc39fb0"

# 📌 추출하고 싶은 키워드 목록 (이 중 하나라도 공고명에 포함되면 알림 전송)
KEYWORDS = ["부단수", "상수도", "단수", "관로", "이설공사"] 

# KST (한국 표준시)
KST = timezone(timedelta(hours=9))

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[{get_now_str()}] 텔레그램 전송 중 오류 발생: {e}")

def get_now_str():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

def is_active_time():
    now = datetime.now(KST)
    return 8 <= now.hour < 18

def get_daily_filename():
    """지정된 경로에 오늘 날짜와 요일 기반의 폴더를 생성하고 파일 경로를 반환합니다."""
    base_dir = r"C:\Users\PC_1M\Desktop\python\공고리스트"
    
    now = datetime.now(KST)
    weekdays = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
    weekday_ko = weekdays[now.weekday()]
    
    # 폴더명 생성 (예: 260602 화요일)
    folder_name = now.strftime("%y%m%d ") + weekday_ko
    target_dir = os.path.join(base_dir, folder_name)
    
    # 폴더가 없으면 자동으로 생성
    os.makedirs(target_dir, exist_ok=True)
    
    # 파일명 생성
    filename = now.strftime("%y%m%d") + "_나라장터 공고리스트.json"
    return os.path.join(target_dir, filename)

def load_previous_notices():
    daily_file = get_daily_filename()
    if os.path.exists(daily_file):
        try:
            with open(daily_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_current_notices(notices):
    daily_file = get_daily_filename()
    try:
        with open(daily_file, "w", encoding="utf-8") as f:
            json.dump(notices, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[{get_now_str()}] 파일 저장 오류: {e}")

def fetch_g2b_notices():
    """공공데이터포털 나라장터 입찰공고 API를 호출하여 데이터를 가져옵니다."""
    # 조달청_나라장터 공사 입찰공고 API 엔드포인트 (용역이나 물품의 경우 URL이 다를 수 있습니다)
    url = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwk"
    
    # 오늘 자정부터 현재 시간까지의 공고를 조회합니다.
    now = datetime.now(KST)
    start_dt = now.strftime("%Y%m%d0000") # 오늘 00:00
    end_dt = now.strftime("%Y%m%d2359")   # 오늘 23:59
    
    params = {
        "serviceKey": SERVICE_KEY,
        "numOfRows": "100",          # 한 번에 가져올 데이터 수
        "pageNo": "1",               # 페이지 번호
        "inqryDiv": "1",             # 1: 등록일시 기준, 2: 입찰일시 기준
        "inqryBgnDt": start_dt,      # 조회 시작일시
        "inqryEndDt": end_dt,        # 조회 종료일시
        "type": "json"               # JSON 형태로 응답 요청
    }
    
    notices = []
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            items = data.get("response", {}).get("body", {}).get("items", [])
            
            for item in items:
                title = item.get("bidNtceNm", "")
                
                # 📌 지정한 키워드 중 하나라도 제목에 포함되어 있는지 검사
                if any(keyword in title for keyword in KEYWORDS):
                    notices.append({
                        "공고번호": item.get("bidNtceNo", ""),
                        "공고명": title,
                        "공고일": item.get("bidNtceDt", ""),
                        "발주기관": item.get("ntceInsttNm", ""),
                        "링크": item.get("bidNtceDtlUrl", "")
                    })
        else:
            print(f"[{get_now_str()}] API 호출 실패: 상태코드 {response.status_code}")
    except Exception as e:
        print(f"[{get_now_str()}] API 요청 중 에러 발생: {e}")
        
    return notices

def run_monitor():
    print(f"[{get_now_str()}] 나라장터 키워드 모니터링을 시작합니다. (키워드: {', '.join(KEYWORDS)})")
    send_telegram_message(f"<b>[나라장터 모니터링 비서]</b>")
    
    while True:
        try:
            if is_active_time():
                print(f"[{get_now_str()}] 나라장터 신규 공고 확인 중...")
                filtered_notices = fetch_g2b_notices()
                
                if filtered_notices:
                    previous_notices = load_previous_notices()
                    daily_file = get_daily_filename()
                    file_exists = os.path.exists(daily_file)
                    
                    # 중복 확인을 위한 이전 공고번호 세트 생성
                    prev_ids = {n.get("공고번호") for n in previous_notices if n.get("공고번호")}
                    new_notices_found = []
                    
                    for notice in filtered_notices:
                        if notice["공고번호"] not in prev_ids:
                            new_notices_found.append(notice)
                            # 기존 파일이 있을 때(즉, 당일 두 번째 이후 조회일 때)만 알림 전송
                            if file_exists:
                                message = (
                                    f"🎯 <b>[나라장터 키워드 매칭 공고!]</b>\n\n"
                                    f"📌 <b>공고번호:</b> {notice['공고번호']}\n"
                                    f"📝 <b>공고명:</b> {notice['공고명']}\n"
                                    f"🏢 <b>발주기관:</b> {notice['발주기관']}\n"
                                    f"📅 <b>공고일:</b> {notice['공고일']}\n\n"
                                    f"👉 <a href='{notice['링크']}'>상세보기 링크</a>"
                                )
                                send_telegram_message(message)
                                print(f"[{get_now_str()}] 알림 전송: {notice['공고명']}")
                    
                    # 새로운 내용이 추가되었다면 JSON 파일 업데이트 (기존 내역 + 새로운 내역)
                    if new_notices_found or not file_exists:
                        # 저장 형식: 공고번호 추가
                        save_data = [{"공고번호": n.get("공고번호", "기존데이터"), "공고명": n.get("공고명", ""), "공고일": n.get("공고일", "")} for n in (previous_notices + new_notices_found)]
                        save_current_notices(save_data)
                        print(f"[{get_now_str()}] 나라장터_확인 완료 (신규 키워드 공고: {len(new_notices_found)}개)")
                else:
                    print(f"[{get_now_str()}] 나라장터_조건에 맞는 공고가 없거나 데이터를 가져오지 못했습니다.")
            else:
                print(f"[{get_now_str()}] 활성 시간(08:00~18:00)이 아닙니다. 대기 중...")
                
        except Exception as e:
            print(f"[{get_now_str()}] 나라장터_루프 실행 중 에러: {e}")
            
        time.sleep(CHECK_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    run_monitor()