import time
import json
import os
import re
from datetime import datetime, timedelta, timezone
import requests
from playwright.sync_api import sync_playwright

# ==========================================
# [설정 정보] - 본인의 정보에 맞게 수정해주세요.
# ==========================================
TELEGRAM_BOT_TOKEN = "8682869478:AAGHyOOpeZtuAlDV9JMmg3eXQTFhswydFaw"  # 텔레그램 BotFather에게 받은 토큰
TELEGRAM_CHAT_ID = "8456543788" 
CHECK_INTERVAL_MINUTES = 40                         # 모니터링 주기 (단위: 분)

# 서울아리수본부 관련 웹페이지 주소
TARGET_URL = "https://arisu.seoul.go.kr/home/sub?menukey=7201"

# 📌 추출하고 싶은 키워드 목록 (이 중 하나라도 공고명에 포함되면 알림 전송)
KEYWORDS = ["공법"] 

# 한국 표준시(KST) 구하기 위한 타임존 설정
KST = timezone(timedelta(hours=9))

# 날짜 추출용 정규표현식 (YYYY-MM-DD, YYYY.MM.DD 등 모두 대응)
DATE_PATTERN = re.compile(r'\b\d{4}[-./]\d{2}[-./]\d{2}\b')

def send_telegram_message(message):
    """텔레그램 봇을 통해 메시지를 전송합니다."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"[{get_now_str()}] 텔레그램 발송 실패: {response.text}")
    except Exception as e:
        print(f"[{get_now_str()}] 텔레그램 전송 중 오류 발생: {e}")

def get_now_str():
    """현재 한국 시간을 문자열로 반환합니다."""
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

def is_active_time():
    """현재 시간이 오전 8시부터 오후 6시 사이인지 확인합니다."""
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
    filename = now.strftime("%y%m%d") + "_서울아리수본부.json"
    return os.path.join(target_dir, filename)

def load_previous_notices():
    """오늘자 공고 목록을 불러옵니다."""
    daily_file = get_daily_filename()
    if os.path.exists(daily_file):
        try:
            with open(daily_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_current_notices(notices):
    """현재 가져온 공고 목록을 파일에 저장합니다."""
    daily_file = get_daily_filename()
    
    # 요구사항에 맞게 데이터 형태 가공 (공고명, 공고일만 저장)
    export_data = [
        {
            "공고명": n["title"],
            "공고일": n["date"]
        }
        for n in notices
    ]
    
    try:
        with open(daily_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[{get_now_str()}] 파일 저장 오류: {e}")

def scrape_arisu():
    """Playwright를 이용해 서울아리수본부 공고 목록을 수집합니다."""
    notices = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            print(f"[{get_now_str()}] 서울아리수 페이지 접속 중...")
            page.goto(TARGET_URL, timeout=60000)
            
            # networkidle 대신 load 또는 domcontentloaded 사용
            page.wait_for_load_state("load") 
            time.sleep(3) # 추가적인 렌더링을 위한 대기
            
            # 일반적인 게시판 테이블의 행(tr) 탐색 (tbody 내의 tr을 우선 검색)
            rows = page.query_selector_all("table tbody tr")
            if not rows:
                rows = page.query_selector_all("table tr")
            
            for row in rows:
                if not row.is_visible():
                    continue
                    
                tds = row.query_selector_all("td")
                if len(tds) < 3:
                    continue
                
                cells = [td.inner_text().strip() for td in tds]
                
                # 1) 등록일 찾기
                date_val = "확인불가"
                for cell in cells:
                    date_match = DATE_PATTERN.search(cell)
                    if date_match:
                        date_val = date_match.group(0)
                        break
                
                # 2) 공고명 찾기
                # 보통 a 태그 안에 제목이 있으므로, a 태그를 먼저 탐색
                title = ""
                a_tag = row.query_selector("a")
                if a_tag:
                    title = a_tag.inner_text().strip()
                else:
                    # a 태그가 없다면 날짜, 조회수, 단순 번호를 제외한 가장 긴 텍스트를 제목으로 간주
                    candidates = [c for c in cells if len(c) > 5 and not DATE_PATTERN.search(c)]
                    if candidates:
                        title = max(candidates, key=len)
                
                if not title:
                    continue
                
                # 📌 키워드 필터링 적용 ("공법"이 제목에 포함되어 있는지)
                if any(keyword in title for keyword in KEYWORDS):
                    notices.append({
                        "title": title,
                        "date": date_val
                    })
                        
        except Exception as e:
            print(f"[{get_now_str()}] 스크래핑 중 에러 발생: {e}")
        finally:
            browser.close()
            
    return notices

def run_monitor():
    """모니터링 핵심 루프"""
    print(f"[{get_now_str()}] 서울아리수 공고 모니터링 (키워드: {', '.join(KEYWORDS)})")
    send_telegram_message(f"<b>[서울아리수 모니터링 비서]</b>")
    
    while True:
        try:
            if is_active_time():
                print(f"[{get_now_str()}] 아리수본부 공고 확인 중...")
                current_notices = scrape_arisu()
                
                if current_notices:
                    previous_notices = load_previous_notices()
                    daily_file = get_daily_filename()
                    file_exists = os.path.exists(daily_file)
                    
                    # 중복 확인용 키: "공고명_공고일" 조합
                    prev_keys = {f"{n.get('공고명', '')}_{n.get('공고일', '')}" for n in previous_notices}
                    
                    new_count = 0
                    for notice in current_notices:
                        notice_key = f"{notice['title']}_{notice['date']}"
                        
                        if notice_key not in prev_keys:
                            # 당일 기록용 파일이 생성된 이후(즉, 당일 두 번째 탐색부터)에만 새 알림 발송
                            if file_exists:
                                message = (
                                    f"🚨 <b>[서울아리수본부 키워드 공고!]</b>\n\n"
                                    f"📝 <b>제목:</b> {notice['title']}\n"
                                    f"📅 <b>등록일:</b> {notice['date']}"
                                )
                                send_telegram_message(message)
                                print(f"[{get_now_str()}] 새 키워드 공고 발견 알림 전송: {notice['title']}")
                            new_count += 1
                    
                    # 신규 공고가 발견되었거나 아직 당일 파일이 없는 경우 업데이트
                    if new_count > 0 or not file_exists:
                        # 기존 데이터 리스트에 새로운 데이터를 더해 한 번에 저장합니다.
                        new_data = [{"title": n["title"], "date": n["date"]} for n in current_notices if f"{n['title']}_{n['date']}" not in prev_keys]
                        
                        # load_previous_notices()는 {"공고명":..., "공고일":...} 형태로 반환하므로, 이를 내부 규격으로 맞춥니다.
                        formatted_prev = [{"title": n["공고명"], "date": n["공고일"]} for n in previous_notices]
                        
                        save_current_notices(formatted_prev + new_data)
                        print(f"[{get_now_str()}] 아리수_확인 완료 (신규 발견: {new_count}개 / 파일 갱신 완료)")
                else:
                    print(f"[{get_now_str()}] 아리수_조건에 맞는 공고가 없거나 데이터를 가져오지 못했습니다.")
            else:
                print(f"[{get_now_str()}] 활성 시간(08:00~18:00)이 아닙니다. 대기 중...")
                
        except Exception as e:
            print(f"[{get_now_str()}] 아리수_루프 실행 중 에러: {e}")
            
        time.sleep(CHECK_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    run_monitor()