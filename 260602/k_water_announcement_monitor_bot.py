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
TELEGRAM_CHAT_ID = "8456543788"      # 본인의 텔레그램 Chat ID (숫자)
CHECK_INTERVAL_MINUTES = 40                         # 모니터링 주기 (단위: 분)
TARGET_URL = "https://www.kwater.or.kr/wis/wq/index.do?w2xPath=/wis/ui/index.xml&&ntfDivCd=SPORT&&targetMenuId=WISWS02131100&&tabId=203030"

# 한국 표준시(KST) 구하기 위한 타임존 설정
KST = timezone(timedelta(hours=9))

# 정규표현식 패턴 정의
EXACT_DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$') # 2026-06-02 형식 단독 컬럼 매칭
ANN_NUM_PATTERN = re.compile(r'^[A-Z]{2,}-?\d+$')       # WS260058 또는 WS-260058 형식 매칭

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
    filename = now.strftime("%y%m%d") + "_k-물산업_공고리스트.json"
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

def is_valid_title(title, num, date_val, ann_num):
    """문자열이 실제 유효한 공고 제목인지 정교하게 판별합니다."""
    if not title:
        return False
    title_strip = title.strip()
    
    # 기본 구분용 기호 또는 제외 대상과 정확히 일치하면 제외
    if title_strip in (num, date_val, ann_num, "~", "-", "상세보기"):
        return False
        
    # 조회수 거르기 (짧은 숫자형 데이터)
    if title_strip.isdigit() and len(title_strip) <= 4:
        return False
        
    # 날짜 범위/기간 형식 거르기 (예: 2026-06-01~2026-06-15, 2026.06.01 등 숫자가 지배적인 패턴)
    if re.match(r'^[\d\s\-~.:/()]+$', title_strip):
        return False
        
    # 단순 상태 표시나 짧은 태그성 단어 거르기
    if title_strip in ["공고중", "마감", "진행중", "접수중", "대기", "종료", "접수마감", "첨부파일"]:
        return False
        
    # 특수문자/공백 제외 글자 수가 너무 적으면 실질적인 제목이 아님
    clean = re.sub(r'[^a-zA-Z0-9가-힣]', '', title_strip)
    if len(clean) < 3:
        return False
        
    return True

def scrape_kwater():
    """Playwright를 이용해 동적 웹페이지의 공고 목록을 수집합니다."""
    notices = []
    
    with sync_playwright() as p:
        # 헤드리스(화면 없음) 브라우저 실행
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            print(f"[{get_now_str()}] K-물산업 페이지 접속 중...")
            page.goto(TARGET_URL, timeout=60000)
            
            # 페이지 로딩 및 네트워크 대기
            page.wait_for_load_state("networkidle")
            time.sleep(5)  # 웹스퀘어 그리드 렌더링을 위한 안전 대기시간
            
            # WebSquare GridView의 실제 본문 테이블 행만 타겟팅합니다.
            # 클래스명이 w2grid_body_table인 테이블 아래의 tr 요소를 가져오며,
            # 없을 경우를 대비해 기존의 범용 tr 요소 수집을 백업으로 둡니다.
            rows = page.query_selector_all(".w2grid_body_table tr")
            if not rows:
                rows = page.query_selector_all("tr")
            
            for row in rows:
                # 화면에 보이지 않는 숨겨진 행(가상 템플릿 행 등)은 필터링합니다.
                if not row.is_visible():
                    continue
                    
                tds = row.query_selector_all("td")
                # 유효한 행 데이터는 컬럼 수가 최소 4개 이상이어야 합니다.
                if len(tds) < 4:
                    continue
                
                # 가시적인 td만 필터링하여 불필요한 숨김 데이터를 배제합니다.
                visible_tds = [td for td in tds if td.is_visible()]
                if len(visible_tds) < 3:
                    continue
                    
                cells = [td.inner_text().strip() for td in visible_tds]
                num = cells[0]
                
                # 첫 번째 칸이 숫자가 아니거나 '공고', '공지' 등이 아니면 데이터 행이 아님 (헤더 등 제외)
                if not (num.isdigit() or "공고" in num or "공지" in num):
                    continue
                
                # 1) 엄격한 등록 날짜 찾기 (단독 날짜만 매칭하며, 날짜 범위인 2025-02-01~2026-12-31 등은 제외)
                date_val = ""
                for cell in cells:
                    if EXACT_DATE_PATTERN.match(cell):
                        date_val = cell
                        break
                
                # 2) 공고번호 찾기 (예: WS260058)
                ann_num = ""
                for cell in cells:
                    if ANN_NUM_PATTERN.match(cell):
                        ann_num = cell
                        break
                
                # 3) 진짜 공고제목 걸러내기 (유효한 제목 필터 적용)
                candidates = [cell for cell in cells if is_valid_title(cell, num, date_val, ann_num)]
                
                # 유효한 제목 후보군이 없다면 가짜 행이므로 건너뜁니다.
                if not candidates:
                    continue
                
                # 남은 후보군 중 가장 길고 온전한 문자열을 '공고제목'으로 임명
                title = max(candidates, key=len)
                
                # 고유식별자 ID 생성 (공고번호가 있다면 공고번호를 활용)
                unique_id = f"{ann_num if ann_num else num}_{title[:20]}"
                
                notices.append({
                    "id": unique_id,
                    "num": num,
                    "ann_num": ann_num if ann_num else "확인불가",
                    "title": title,
                    "date": date_val if date_val else "확인불가"
                })
                        
        except Exception as e:
            print(f"[{get_now_str()}] 스크래핑 중 에러 발생: {e}")
        finally:
            browser.close()
            
    return notices

def run_monitor(refresh_event=None):
    """모니터링 핵심 루프"""
    print(f"[{get_now_str()}] K-물산업 공고 모니터링을 시작합니다.")
    send_telegram_message(f"<b>[K-물산업 모니터링]</b>")
    
    while True:
        try:
            if is_active_time():
                print(f"[{get_now_str()}] K-물산업 공고 확인 중...")
                current_notices = scrape_kwater()
                
                if current_notices:
                    previous_notices = load_previous_notices()
                    daily_file = get_daily_filename()
                    file_exists = os.path.exists(daily_file)
                    
                    # 이전 데이터와 비교하기 위한 키 생성 (공고명 + 공고일)
                    prev_keys = {f"{n.get('공고명', '')}_{n.get('공고일', '')}" for n in previous_notices}
                    
                    new_count = 0
                    for notice in current_notices:
                        notice_key = f"{notice['title']}_{notice['date']}"
                        
                        if notice_key not in prev_keys:
                            # 오늘자 파일이 이미 존재할 때만 실시간 새 알림 발송 (첫 실행 시 폭탄 알림 방지)
                            if file_exists:
                                message = (
                                    f"🚨 <b>[K-물산업 새 공고 등록!]</b>\n\n"
                                    f"📌 <b>공고번호:</b> {notice['ann_num']}\n"
                                    f"📝 <b>제목:</b> {notice['title']}\n"
                                    f"📅 <b>등록일:</b> {notice['date']}"
                                )
                                send_telegram_message(message)
                                print(f"[{get_now_str()}] 새 공고 발견 알림 전송: {notice['title']}")
                            new_count += 1
                    
                    # 현재 가져온 목록을 최신 상태로 업데이트 저장
                    save_current_notices(current_notices)
                    print(f"[{get_now_str()}] K-물산업_확인 완료 (새로운 공고: {new_count}개 / 파일 갱신 완료)")
                else:
                    print(f"[{get_now_str()}] K-물산업_공고 데이터를 가져오지 못했습니다. (네트워크 지연 또는 구조 변경 가능성)")
            else:
                print(f"[{get_now_str()}] 활성 시간(08:00~18:00)이 아닙니다. 대기 중...")
                
        except Exception as e:
            print(f"[{get_now_str()}] 루프 실행 중 에러: {e}")
            
        # time.sleep 부분을 아래처럼 알람벨 대기 모드로 변경!
        if refresh_event:
            refresh_event.wait(CHECK_INTERVAL_MINUTES * 60)
        else:
            time.sleep(CHECK_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    run_monitor()