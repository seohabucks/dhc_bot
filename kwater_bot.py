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
KWATER_BOARD_URL = "https://www.kwater.or.kr/wis/wq/index.do?w2xPath=/wis/ui/index.xml&&ntfDivCd=SPORT&&targetMenuId=WISWS02131100&&tabId=203030"
SENT_POSTS_FILE = "sent_posts.txt"

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

# --- [3] 수자원공사 게시판 날짜 기반 감시 로직 ---
def kwater_board_loop():
    global running
    print("🚀 수자원공사 게시판 날짜 기반 감시 시작")
    
    while running:
        # 프로그램 실행 시점부터 즉시 감시 시작 (업무 시간 외에도 작동하도록 설정)
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d") # 오늘 날짜 (YYYY-MM-DD)
        sent_list = load_sent_posts()
        
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        driver = webdriver.Chrome(options=options)
        
        try:
            driver.get(KWATER_BOARD_URL)
            wait = WebDriverWait(driver, 20)
            
            # iframe 진입 시도
            try:
                wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "mf_wframe_content")))
            except: pass
            
            # 모든 행(tr) 로드 대기
            rows = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table[id*='grdCsntRegistSttusList_body_table'] tr")))
            
            found_new_count = 0
            for i in range(len(rows)):
                try:
                    # 이미지 7, 8 분석 결과: 제목(index 2), 날짜(index 5)
                    title_el = driver.find_element(By.CSS_SELECTOR, f"td[id*='cell_{i}_2']")
                    date_el = driver.find_element(By.CSS_SELECTOR, f"td[id*='cell_{i}_5']")
                    
                    title = title_el.text.strip()
                    post_date = date_el.text.strip() # 공고일 (예: 2026-04-13)

                    # 오늘 날짜와 공고일이 일치하고, 아직 알림을 보내지 않은 제목인 경우만 발송
                    if post_date == today_str and title not in sent_list:
                        msg = f"🔔 *[수자원공사 오늘 공고]*\n📅 날짜: {post_date}\n📌 제목: {title}\n🔗 [바로가기]({KWATER_BOARD_URL})"
                        send_telegram_msg(msg)
                        save_sent_post(title)
                        sent_list.add(title)
                        found_new_count += 1
                except: continue
                
            print(f"✅ [{now.strftime('%H:%M')}] 체크 완료 (신규 발송: {found_new_count}건)")
            
        except Exception as e:
            print(f"❌ 게시판 감시 중 오류: {e}")
        finally:
            driver.quit()
        
        time.sleep(3600) # 1시간 간격으로 반복 실행

# --- [4] 메인 실행부 ---
if __name__ == "__main__":
    # 프로그램 실행 시 즉시 감시 쓰레드 시작
    t = threading.Thread(target=kwater_board_loop, daemon=True)
    t.start()
    
    # 프로그램이 종료되지 않도록 유지
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        running = False
        print("🛑 감시 시스템 종료")