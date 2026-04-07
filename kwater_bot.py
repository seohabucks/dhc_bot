import requests
import datetime
import time
import threading
import sys
import signal
import xmltodict

# --- 설정 정보 ---
# 이미지 6에서 확인된 실제 작동하는 인증키입니다.
RAW_SERVICE_KEY = 'b6f3dcb33a0e5b9651bd8b90d8b7e108bf24d17d587a9d8f2682f3c50fc39fb0' # 실제 키의 앞부분 (보안상 이미지 참고)
TELEGRAM_TOKEN = '8682869478:AAGHyOOpeZtuAlDV9JMmg3eXQTFhswydFaw'
CHAT_ID = '8456543788'

KEYWORDS = ["부단수", "특정 공법", "라인스토핑", "핫태핑", "열수송관", "열배관", "공법선정", "신기술", "기법"]
sent_bids = set()
running = True

def send_telegram_msg(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'}
    try: requests.post(url, data=payload, timeout=10)
    except: pass

def get_kwater_data(target_month):
    """
    이미지 6의 실제 Request URL 구조를 따릅니다.
    주소 형식: https://apis.data.go.kr/B500001/ebid/tndr3/{상세경로}
    """
    results = []
    # 이미지 2의 상세기능 목록 기준
    categories = {
        '공사': 'cntrwkList',
        '물품': 'gdsList',
        '용역': 'servcList'
    }

    for name, path in categories.items():
        if not running: break
        
        # 이미지 6에서 확인된 최신 ebid/tndr3 경로 적용
        base_url = f"https://apis.data.go.kr/B500001/ebid/tndr3/{path}"
        # 인증키 인코딩 방지를 위해 URL 직접 조립
        full_url = f"{base_url}?serviceKey={RAW_SERVICE_KEY}&pageNo=1&numOfRows=100&searchDt={target_month}&_type=xml"
        
        try:
            response = requests.get(full_url, timeout=15)
            
            if response.status_code != 200:
                print(f"⚠️ {name} API 응답 실패: {response.status_code}")
                continue

            content = response.text.strip()
            # 이미지 3의 JSON 파싱 오류 방지
            if not content or content.startswith('<html>') or 'OpenAPI_ServiceResponse' in content:
                continue
            
            # XML 파싱 (이미지 1의 요청변수 기준 xml 출력)
            data_dict = xmltodict.parse(content)
            
            # 수자원 API 일반적인 구조: response -> body -> items -> item 리스트
            items_raw = data_dict.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            
            if isinstance(items_raw, dict): items_raw = [items_raw]
            
            for i in items_raw:
                title = i.get('bid_nm')
                bid_id = i.get('bid_no')
                if title and bid_id:
                    results.append({
                        'source': f'💧 수자원({name})',
                        'title': title,
                        'id': bid_id,
                        'date': i.get('bid_pblanc_dt'),
                        'url': "https://ebid.kwater.or.kr/"
                    })
        except Exception as e:
            print(f"⚠️ {name} 처리 중 에러: {e}")
            
    return results

def auto_checker():
    global running
    while running:
        now = datetime.datetime.now()
        this_month = now.strftime('%Y%m') # 이미지 1, 6의 searchDt 형식
        today_str = now.strftime('%Y%m%d')
        
        items = get_kwater_data(this_month)
        
        for item in items:
            if not running: break
            # 날짜 형식 2026-04-07 -> 20260407 변환
            pub_date = str(item['date']).replace("-", "")[:8]
            if pub_date == today_str and item['id'] not in sent_bids:
                if any(k in item['title'] for k in KEYWORDS):
                    msg = (
                        f"🎯 *K-water 신규 공고!*\n"
                        f"━━━━━━━━━━━━━━\n"
                        f"📂 *분류:* {item['source']}\n"
                        f"📌 *공고명:* {item['title']}\n"
                        f"⏰ *게시:* {item['date']}\n"
                        f"🔗 [수자원공사 전자조달 바로가기]({item['url']})"
                    )
                    send_telegram_msg(msg)
                    sent_bids.add(item['id'])
        
        print(f"[{now.strftime('%H:%M')}] 수자원 통합 체크 완료 (조회: {len(items)}건)")
        for _ in range(240): # 40분 대기 (중간 종료 체크 가능)
            if not running: return
            time.sleep(10)

if __name__ == "__main__":
    # Ctrl+C 즉시 종료 설정
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    print("🚀 수자원공사 ebid/tndr3 통합 알리미 가동 중...")
    
    # 자동 체크 시작
    threading.Thread(target=auto_checker, daemon=True).start()
    
    # 명령어 루프 (메인 쓰레드)
    last_id = 0
    while running:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_id+1}&timeout=5").json()
            for update in res.get('result', []):
                last_id = update['update_id']
                text = update.get('message', {}).get('text', '')
                if text.startswith('/검색'):
                    query = text.replace('/검색', '').strip()
                    this_month = datetime.datetime.now().strftime('%Y%m')
                    all_items = get_kwater_data(this_month)
                    results = [i for i in all_items if query in i['title']]
                    if not results: send_telegram_msg(f"❌ '{query}' 검색 결과 없음.")
                    else:
                        for i in results[:5]:
                            send_telegram_msg(f"📂 *{i['source']}*\n📌 {i['title']}\n⏰ {i['date']}")
        except: pass
        time.sleep(1)