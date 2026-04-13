import time
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- 설정 구간 ---
TELEGRAM_TOKEN = '8682869478:AAGHyOOpeZtuAlDV9JMmg3eXQTFhswydFaw'
CHAT_ID = '8456543788'
URL = "https://www.kwater.or.kr/wis/wq/index.do?w2xPath=/wis/ui/index.xml&&ntfDivCd=SPORT&&targetMenuId=WISWS02131100&&tabId=203030"
SENT_POSTS_FILE = "sent_posts.txt" # 이미 알림 보낸 목록 저장

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text})

def load_sent_posts():
    try:
        with open(SENT_POSTS_FILE, "r", encoding="utf-8") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()

def save_sent_post(title):
    with open(SENT_POSTS_FILE, "a", encoding="utf-8") as f:
        f.write(title + "\n")

def check_kwater():
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d") # 예: 2026-04-13
    
    # 오전 9:00 ~ 오후 17:30 사이인지 체크
    start_time = now.replace(hour=9, minute=0, second=0)
    end_time = now.replace(hour=17, minute=30, second=0)
    
    if not (start_time <= now <= end_time):
        print(f"[{now.strftime('%H:%M')}] 대기 모드 (운영시간 아님)")
        return

    print(f"[{now.strftime('%H:%M')}] 오늘 날짜({today_str}) 공고 탐색 중...")
    
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)
    sent_list = load_sent_posts()

    try:
        driver.get(URL)
        try:
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "mf_wframe_content")))
        except: pass

        # 표의 모든 행(tr)을 가져옵니다. 
        # 웹스퀘어 그리드 본체 테이블 ID 패턴 사용
        rows = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table[id*='grdCsntRegistSttusList_body_table'] tr")))
        
        found_new = False
        for i in range(len(rows)):
            try:
                # 제목과 날짜 추출 (행 번호 i를 이용하여 각 셀 접근)
                title_el = driver.find_element(By.CSS_SELECTOR, f"td[id*='cell_{i}_2']")
                date_el = driver.find_element(By.CSS_SELECTOR, f"td[id*='cell_{i}_5']")
                
                title = title_el.text.strip()
                post_date = date_el.text.strip()

                # 조건: 공고일이 오늘이고, 아직 알림을 보내지 않은 제목인 경우
                if post_date == today_str and title not in sent_list:
                    print(f"✨ 새 공고 발견: {title}")
                    msg = f"🔔 [K-water 신규 공고]\n날짜: {post_date}\n제목: {title}\n\n링크: {URL}"
                    send_telegram(msg)
                    save_sent_post(title)
                    sent_list.add(title)
                    found_new = True
            except:
                continue # 빈 행이거나 로딩 중이면 패스
        
        if not found_new:
            print("새로운 오늘자 공고가 없습니다.")

    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    while True:
        check_kwater()
        # 1시간(3600초) 대기
        time.sleep(3600)