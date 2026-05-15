import requests
from bs4 import BeautifulSoup
import time
import telegram
import asyncio

# --- 설정 구간 ---
TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
CHAT_ID = 'YOUR_CHAT_ID'
KEYWORDS = ['부단수', '특정 공법', '라인스토핑', '핫태핑', '열수송관', '열배관']
BASE_URL = "https://www.jeonbuk.go.kr/board/list.jeonbuk?menuCd=DOM_000000102002005000&boardId=BBS_0000129&searchType=DATA_TITLE"

# 최근에 확인한 공고 제목이나 ID를 저장 (중복 알림 방지)
last_notified_titles = set()

async def send_telegram_msg(text):
    bot = telegram.Bot(token=TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=text)

def check_new_notices():
    global last_notified_titles
    new_found = []

    for kw in KEYWORDS:
        # URL에 키워드 적용 (한글 인코딩은 requests가 자동 처리)
        search_url = f"{BASE_URL}&keyword={kw}"
        
        try:
            response = requests.get(search_url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 전북도청 게시판 목록의 제목 요소를 선택 (사이트 구조에 맞게 조정 필요)
            # 보통 <td> 안의 <a title="..."> 혹은 클래스명을 찾습니다.
            notice_list = soup.select('table.board_list tbody tr')
            
            for item in notice_list:
                title_tag = item.select_one('td.al a')
                if title_tag:
                    title = title_tag.get_text(strip=True)
                    link = "https://www.jeonbuk.go.kr" + title_tag['href']
                    
                    if title not in last_notified_titles:
                        message = f"🔔 [전북 신규 공고]\n키워드: {kw}\n제목: {title}\n링크: {link}"
                        new_found.append(message)
                        last_notified_titles.add(title)
        except Exception as e:
            print(f"에러 발생 ({kw}): {e}")
            
    return new_found

async def main():
    print("모니터링 시작...")
    # 처음 실행 시 현재 목록을 '이미 읽음' 처리하려면 아래 주석 해제
    # check_new_notices() 
    
    while True:
        messages = check_new_notices()
        for msg in messages:
            await send_telegram_msg(msg)
            print(f"알림 전송: {msg}")
            time.sleep(1) # 전송 부하 방지
            
        # 1시간(3600초)마다 체크 (원하는 주기로 변경)
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())