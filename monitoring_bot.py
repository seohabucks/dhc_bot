import os
import time
import datetime
import threading
import requests
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- [1] 통합 설정 정보 ---
TELEGRAM_TOKEN = '8682869478:AAGHyOOpeZtuAlDV9JMmg3eXQTFhswydFaw'
CHAT_ID = '8456543788'
KWATER_URL = "https://www.kwater.or.kr/wis/wq/index.do?w2xPath=/wis/ui/index.xml&&ntfDivCd=SPORT&&targetMenuId=WISWS02131100&&tabId=203030"
SENT_POSTS_FILE = "sent_posts.txt"

# 감시할 엑셀 파일 리스트
WATCH_LIST = [
    r"\\Dhcmain\(주)대호스토퍼\0영업사항(견적서)\●영업관리\1. 계약건(21).xlsx",
    r"\\Dhcmain\(주)대호스토퍼\0영업사항(견적서)\●영업관리\2. 특허,공고,입찰.xlsx"
]

running = True

# --- [2] 유틸리티 함수 ---
def send_telegram_msg(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'}
    try: requests.post(url, data=payload, timeout=10)
    except: pass

def load_sent_posts():
    if os.path.exists(SENT_POSTS_FILE):
        with open(SENT_POSTS_FILE, "r", encoding="utf-8") as f:
            return set(f.read().splitlines())
    return set()

def save_sent_post(title):
    with open(SENT_POSTS_FILE, "a", encoding="utf-8") as f:
        f.write(title + "\n")

# --- [3] 수자원공사 게시판 감시 (정확한 ID 반영) ---
def kwater_board_loop():
    global running
    # 이미지 11에서 확인된 테이블 ID 직접 지정
    TABLE_ID = "mf_wframe_content_wframeCsntRegist_grdCsntRegistSttusList_body_table"
    
    print("🚀 수자원공사 게시판 실시간 감시 시작...")
    
    while running:
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d") 
        sent_list = load_sent_posts()
        
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        driver = webdriver.Chrome(options=options)
        
        try:
            driver.get(KWATER_URL)
            wait = WebDriverWait(driver, 30)
            
            # 1. 프레임 진입 (프레임 ID가 테이블 ID의 앞부분과 일치)
            try:
                wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "mf_wframe_content")))
            except: pass
            
            # 2. 테이블 로딩 대기
            time.sleep(7) # 안정적인 로딩을 위해 시간 연장
            
            # 3. 행(tr) 탐색
            rows = driver.find_elements(By.CSS_SELECTOR, f"table#{TABLE_ID} tr")
            
            found_count = 0
            for i in range(len(rows)):
                try:
                    # 이미지 9, 10의 인덱스 반영 (제목 2번 셀, 날짜 5번 셀)
                    # ID가 매우 길기 때문에 끝자리 패턴으로 매칭
                    title_el = driver.find_element(By.CSS_SELECTOR, f"td[id$='cell_{i}_2']")
                    date_el = driver.find_element(By.CSS_SELECTOR, f"td[id$='cell_{i}_5']")
                    
                    title = title_el.get_attribute("innerText").strip()
                    post_date = date_el.get_attribute("innerText").strip()

                    # 오늘 날짜 확인 및 중복 제거
                    if post_date == today_str and title not in sent_list:
                        msg = f"💧 *[수자원공사 신규]*\n📌 제목: {title}\n📅 날짜: {post_date}\n🔗 [바로가기]({KWATER_URL})"
                        send_telegram_msg(msg)
                        save_sent_post(title)
                        sent_list.add(title)
                        found_count += 1
                except: continue
                
            print(f"✅ [{now.strftime('%H:%M')}] 체크 완료 (신규: {found_count}건)")
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
        finally:
            driver.quit()
        
        time.sleep(3600) # 1시간 간격

# --- [4] 엑셀 파일 감시 ---
def excel_monitor_loop():
    global running
    last_mtimes = {path: os.path.getmtime(path) for path in WATCH_LIST if os.path.exists(path)}
    
    while running:
        for path in WATCH_LIST:
            try:
                if os.path.exists(path):
                    mtime = os.path.getmtime(path)
                    if mtime != last_mtimes.get(path):
                        file_name = os.path.basename(path)
                        send_telegram_msg(f"📂 *[영업관리 업데이트]*\n✅ {file_name}")
                        last_mtimes[path] = mtime
            except: pass
        time.sleep(2400) # 40분 간격

# --- [5] 메인 실행 ---
if __name__ == "__main__":
    send_telegram_msg("✅ *통합 모니터링 시스템 가동*")
    
    # 두 기능을 독립된 쓰레드로 실행
    threading.Thread(target=kwater_board_loop, daemon=True).start()
    threading.Thread(target=excel_monitor_loop, daemon=True).start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        running = False
        print("🛑 시스템 종료")