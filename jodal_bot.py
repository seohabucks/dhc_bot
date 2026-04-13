import requests
import datetime
import time
import threading
import sys
import signal
import xmltodict  # XML 응답 대비 설치 필요: pip install xmltodict

# --- 설정 정보 ---
SERVICE_KEY = 'b6f3dcb33a0e5b9651bd8b90d8b7e108bf24d17d587a9d8f2682f3c50fc39fb0'
TELEGRAM_TOKEN = '8682869478:AAGHyOOpeZtuAlDV9JMmg3eXQTFhswydFaw'
CHAT_ID = '8456543788'

KEYWORDS = ["부단수", "특정 공법", "차단", "라인스토핑", "핫태핑", "열수송관", "열배관", "공법선정", "공법" , "기법"]
sent_bids = set()
running = True

def safe_format_date(raw_val):
    if not raw_val: return "정보없음"
    s_val = str(raw_val).replace("-", "").replace(":", "").replace(" ", "").strip()
    if len(s_val) >= 12:
        return f"{s_val[:4]}-{s_val[4:6]}-{s_val[6:8]} {s_val[8:10]}:{s_val[10:12]}"
    elif len(s_val) >= 8:
        return f"{s_val[:4]}-{s_val[4:6]}-{s_val[6:8]}"
    return raw_val

def send_telegram_msg(msg):
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    try: requests.post(send_url, data=payload, timeout=10)
    except: pass

def get_kwater_all_types(target_month):
    """수자원공사 최신 tndr3 규격 반영 조회"""
    # 이미지 6에서 확인된 정확한 기본 주소
    base_url = "https://apis.data.go.kr/B500001/ebid/tndr3"
    endpoints = {'공사': '/cntrwkList', '물품': '/gdsList', '용역': '/servcList', '내자': '/dmscptList'}
    k_combined = []
    
    for type_name, path in endpoints.items():
        if not running: break
        # 필수 항목 searchDt 포함 및 인증키 보호를 위해 URL 직접 조립
        full_url = f"{base_url}{path}?serviceKey={SERVICE_KEY}&pageNo=1&numOfRows=200&_type=json&searchDt={target_month}"
        
        try:
            res = requests.get(full_url, timeout=12).json()
            # 수자원 API 특유의 response -> body -> items 구조 파싱
            body = res.get('response', {}).get('body', {})
            items = body.get('items', {}).get('item', [])
            
            if not items: continue
            if isinstance(items, dict): items = [items]
            
            for i in items:
                k_combined.append({
                    'source': f'💧 수자원({type_name})',
                    'title': i.get('bid_nm'),
                    'id': i.get('bid_no'),
                    'org': '한국수자원공사',
                    'date': i.get('bid_pblanc_dt'),
                    'url': "https://ebid.kwater.or.kr/"
                })
        except: continue
    return k_combined

def get_all_combined_bids(start_time, end_time):
    combined = []
    # 1. 나라장터 조회
    g2b_url = 'https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwk'
    g2b_params = {
        'serviceKey': SERVICE_KEY, 'numOfRows': '300', 'pageNo': '1', 
        'inqryDiv': '1', 'inqryBgnDt': start_time, 'inqryEndDt': end_time, 'type': 'json'
    }
    try:
        res = requests.get(g2b_url, params=g2b_params, timeout=15).json()
        items = res['response']['body'].get('items', [])
        if isinstance(items, dict): items = [items]
        for i in items:
            combined.append({
                'source': '🏢 나라장터', 'title': i.get('bidNtceNm'), 
                'id': i.get('bidNtceNo'), 'org': i.get('dminsttNm'), 
                'date': i.get('bidNtceDt'), 'url': i.get('bidNtceDtlUrl')
            })
    except: pass

    # 2. 수자원공사 조회 (YYYYMM 형식 필요)
    months = list(set([start_time[:6], end_time[:6]]))
    for m in months:
        if not running: break
        k_items = get_kwater_all_types(m)
        for i in k_items:
            b_date = str(i.get('date', '')).replace("-", "").replace(":", "").replace(" ", "")[:12]
            # 시간 범위 내 공고만 필터링
            if start_time <= b_date <= end_time:
                combined.append(i)
    return combined

def auto_checker():
    global running
    is_first = True
    while running:
        now = datetime.datetime.now()
        # 처음 실행 시 오전 9시부터, 이후에는 최근 3시간 내 공고 체크
        start_time = now.strftime('%Y%m%d') + "0900" if is_first else (now - datetime.timedelta(hours=3)).strftime('%Y%m%d%H%M')
        end_time = now.strftime('%Y%m%d%H%M')
        
        print(f"🔄 [{now.strftime('%H:%M')}] 신규 공고 확인 중... ({start_time} ~ {end_time})")
        items = get_all_combined_bids(start_time, end_time)
        
        for item in items:
            if not running: break
            if any(k in item['title'] for k in KEYWORDS) and item['id'] not in sent_bids:
                msg = (f"🎯 *새 공고!* [{item['source']}]\n"
                       f"📌 {item['title']}\n"
                       f"🏢 {item['org']}\n"
                       f"⏰ {safe_format_date(item['date'])}\n"
                       f"🔗 [상세보기]({item['url']})")
                send_telegram_msg(msg)
                sent_bids.add(item['id'])
                time.sleep(0.5)
        
        is_first = False
        for _ in range(240): # 40분 대기
            if not running: return
            time.sleep(10)

def handle_commands():
    global running
    last_id = 0
    while running:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_id+1}&timeout=5"
            res = requests.get(url, timeout=10).json()
            for update in res.get('result', []):
                last_id = update['update_id']
                if 'message' not in update or 'text' not in update['message']: continue
                text = update['message']['text']
                
                if text.startswith('/검색'):
                    query = text.replace('/검색', '').strip()
                    if not query: continue
                    now = datetime.datetime.now()
                    # 최근 7일치 검색
                    last_week = now - datetime.timedelta(days=7)
                    start_str, end_str = last_week.strftime('%Y%m%d') + "0000", now.strftime('%Y%m%d%H%M')
                    
                    send_telegram_msg(f"🔍 '{query}' 통합 검색 시작 (최근 7일)...")
                    all_items = get_all_combined_bids(start_str, end_str)
                    results = [i for i in all_items if query in i['title']]
                    
                    if not results: send_telegram_msg("❌ 결과 없음.")
                    else:
                        for i in results[:10]:
                            if not running: break
                            send_telegram_msg(f"📂 *[{i['source']}]*\n📌 {i['title']}\n⏰ {safe_format_date(i['date'])}\n🔗 [링크]({i['url']})")
                            time.sleep(0.3)
        except: pass
        time.sleep(1)

def exit_gracefully(signum, frame):
    """Control+C 또는 종료 신호 발생 시 호출되는 함수"""
    global running
    print("\n🛑 종료 신호를 받았습니다. 안전하게 종료합니다...")
    
    # [추가] 텔레그램 종료 메시지 전송
    send_telegram_msg("🛑 *나라장터 + 수자원 통합 알리미가 종료되었습니다.*")
    
    running = False
    # 쓰레드들이 정리될 시간을 잠시 준 뒤 종료
    time.sleep(1)
    sys.exit(0)

if __name__ == "__main__":
    # 종료 신호 감지 설정
    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)
    
    # [추가] 텔레그램 시작 메시지 전송
    send_telegram_msg("✅ *나라장터 + 수자원 통합 알리미가 가동되었습니다.*")
    
    print("🚀 나라장터 + 수자원 통합 알리미 가동 중... (종료: Ctrl+C)")
    
    # 자동 체크 쓰레드 시작
    checker_thread = threading.Thread(target=auto_checker, daemon=True)
    checker_thread.start()
    
    try:
        handle_commands()
    except KeyboardInterrupt:
        exit_gracefully(None, None)
    except Exception as e:
        send_telegram_msg(f"⚠️ *알 수 없는 오류로 프로그램이 중단되었습니다: {e}*")
        exit_gracefully(None, None)