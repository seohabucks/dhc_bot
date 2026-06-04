import threading
import time
import requests

import arisu_announcement_monitor
import g2b_announcement_monitor
import k_water_announcement_monitor_bot
import lh_announcement_monitor
import gh_announcement_monitor
import excel_bot


# 봇 토큰과 채팅 ID 설정
TELEGRAM_BOT_TOKEN = "8682869478:AAGHyOOpeZtuAlDV9JMmg3eXQTFhswydFaw" 
TELEGRAM_CHAT_ID = "8456543788" 

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def telegram_listener(refresh_event):
    """텔레그램 메시지를 감시하고 새로고침 명령을 처리하는 전담 비서"""
    last_update_id = 0
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    
    print("🎧 [명령어 수신 대기] 텔레그램 봇이 '/새로고침' 명령어를 기다립니다...")
    
    while True:
        try:
            # 텔레그램 서버에 새로운 메시지가 있는지 확인 (Long Polling)
            params = {"offset": last_update_id + 1, "timeout": 30}
            response = requests.get(url, params=params, timeout=35).json()
            
            if response.get("ok"):
                for result in response["result"]:
                    last_update_id = result["update_id"]
                    text = result.get("message", {}).get("text", "")
                    
                    # '새로고침' 관련 명령어를 입력받았을 때
                    if text in ["/새로고침", "새로고침", "/refresh"]:
                        print("\n🔄 [수동 새로고침] 텔레그램 명령을 수신했습니다!")
                        send_telegram_message("🔄 <b>[명령 수신]</b> 즉시 전체 기관 공고 모니터링을 재실행합니다.")
                        
                        # 40분을 기다리며 자고 있는 5개의 스레드(비서)들에게 기상 알람 울림!
                        refresh_event.set()
                        time.sleep(2) # 비서들이 깰 수 있도록 2초 대기
                        refresh_event.clear() # 다음 40분 대기를 위해 알람벨 초기화
                        
        except Exception as e:
            time.sleep(5) # 네트워크 오류 시 잠시 대기
            
        time.sleep(1)

def main():
    print("🚀 [통합 모니터링 시스템] 5개 기관 감시를 동시에 시작합니다.")
    
    # 5명의 비서를 깨울 수 있는 '알람벨' 객체 생성
    refresh_event = threading.Event()
    
    # 각 스크립트에 refresh_event를 전달하여 실행
    threads = [
        threading.Thread(target=arisu_announcement_monitor.run_monitor, args=(refresh_event,), daemon=True),
        threading.Thread(target=g2b_announcement_monitor.run_monitor, args=(refresh_event,), daemon=True),
        threading.Thread(target=k_water_announcement_monitor_bot.run_monitor, args=(refresh_event,), daemon=True),
        threading.Thread(target=lh_announcement_monitor.run_monitor, args=(refresh_event,), daemon=True),
        threading.Thread(target=gh_announcement_monitor.run_monitor, args=(refresh_event,), daemon=True),
        threading.Thread(target=excel_bot.run_monitor, args=(refresh_event,), daemon=True),
        
        threading.Thread(target=telegram_listener, args=(refresh_event,), daemon=True)
        
    ]
    
    # 모든 스레드 출근!
    for t in threads:
        t.start()
        
    # 메인 프로그램 무한 대기 (종료 방지)
    while True:
        for t in threads:
            t.join(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 관리자의 요청으로 모니터링 시스템을 안전하게 종료합니다.")