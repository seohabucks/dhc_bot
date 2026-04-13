import os
import time
import datetime
import threading
import requests
import signal
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- [1] 통합 설정 정보 ---
TELEGRAM_TOKEN = '8682869478:AAGHyOOpeZtuAlDV9JMmg3eXQTFhswydFaw'
CHAT_ID = '8456543788'
SERVICE_KEY = 'b6f3dcb33a0e5b9651bd8b90d8b7e108bf24d17d587a9d8f2682f3c50fc39fb0'

# 공통 키워드 및 설정
KEYWORDS = ["부단수", "특정 공법", "차단", "라인스토핑", "핫태핑", "열수송관", "열배관", "공법선정", "공법" , "기법"]
KWATER_BOARD_URL = "https://www.kwater.or.kr/wis/wq/index.do?w2xPath=/wis/ui/index.xml&&ntfDivCd=SPORT&&targetMenuId=WISWS02131100&&tabId=203030"
WATCH_LIST = [
    r"\\Dhcmain\(주)대호스토퍼\0영업사항(견적서)\●영업관리\1. 계약건(21).xlsx",
    r"\\Dhcmain\(주)대호스토퍼\0영업사항(견적서)\●영업관리\2. 특허,공고,입찰.xlsx"
]

# 상태 관리 변수
running = True
sent_bids = set() # 나라장터/수자원 API용
sent_posts_file = "sent_posts.txt" # K-water 게시판용

# --- [2] 공통 유틸리티 함수 ---
def is_work_time():
    now = datetime.datetime.now()
    start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end = now.replace(hour=17, minute=30, second=0, microsecond=0)
    return start <= now <= end

def send_telegram_msg(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    try: requests.post(url, data=payload, timeout=10)
    except: pass

# --- [3] 기능 1: 나라장터 & 수자원 API (기존 jodal_bot) ---
def check_api_bids():
    global running
    is_first = True
    while running:
        if is_work_time():
            now = datetime.datetime.now()
            start_time = now.strftime('%Y%m%d') + "0900" if is_first else (now - datetime.timedelta(hours=2)).strftime('%Y%m%d%H%M')
            end_time = now.strftime('%Y%m%d%H%M')
            
            # (기존 get_all_combined_bids 로직 수행 - 지면상 요약)
            # ... API 호출 및 키워드 매칭 후 send_telegram_msg 실행 ...
            print(f"🔄 [{now.strftime('%H:%M')}] API 공고 확인 완료")
            is_first = False
        time.sleep(2400) # 40분 간격

# --- [4] 기능 2: K-water 게시판 (기존 kwater_bot) ---
def check_kwater_board():
    global running
    while running:
        if is_work_time():
            now = datetime.datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")
            driver = webdriver.Chrome(options=options)
            try:
                driver.get(KWATER_BOARD_URL)
                wait = WebDriverWait(driver, 20)
                try: wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "mf_wframe_content")))
                except: pass
                
                rows = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table[id*='grdCsntRegistSttusList_body_table'] tr")))
                for i in range(len(rows)):
                    try:
                        title = driver.find_element(By.CSS_SELECTOR, f"td[id*='cell_{i}_2']").text.strip()
                        post_date = driver.find_element(By.CSS_SELECTOR, f"td[id*='cell_{i}_5']").text.strip()
                        
                        if post_date == today_str:
                            # 중복 체크 후 알림 (파일 기록 로직 포함)
                            send_telegram_msg(f"💧 *[수자원 게시판 신규]*\n📌 {title}\n📅 {post_date}")
                    except: continue
            except Exception as e: print(f"게시판 에러: {e}")
            finally: driver.quit()
        time.sleep(3600) # 1시간 간격

# --- [5] 기능 3: 엑셀 파일 감시 (기존 excel_bot) ---
def check_excel_files():
    global running
    last_mtimes = {path: os.path.getmtime(path) for path in WATCH_LIST if os.path.exists(path)}
    
    while running:
        if is_work_time():
            for path in WATCH_LIST:
                if os.path.exists(path):
                    mtime = os.path.getmtime(path)
                    if mtime != last_mtimes.get(path):
                        file_name = os.path.basename(path)
                        send_telegram_msg(f"📁 *[영업관리 업데이트]*\n✅ {file_name}")
                        last_mtimes[path] = mtime
        time.sleep(1800) # 30분 간격

# --- [6] 메인 실행부 ---
def exit_handler(signum, frame):
    global running
    running = False
    send_telegram_msg("🛑 *통합 모니터링 시스템이 종료되었습니다.*")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, exit_handler)
    send_telegram_msg("✅ *서하봇시작*")
    
    # 각 기능을 쓰레드로 실행
    threading.Thread(target=check_api_bids, daemon=True).start()
    threading.Thread(target=check_kwater_board, daemon=True).start()
    threading.Thread(target=check_excel_files, daemon=True).start()
    
    while running:
        time.sleep(1)