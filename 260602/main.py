import threading

# 기존 파일들을 모듈로 불러옵니다 (확장자 .py 제외)
import arisu_announcement_monitor
import g2b_announcement_monitor
import k_water_announcement_monitor_bot
import lh_announcement_monitor
import gh_announcement_monitor

def main():
    print("🚀 [통합 모니터링 시스템] 5개 기관 감시를 동시에 시작합니다.")
    
    # 각 스크립트의 모니터링 함수를 개별 스레드(백그라운드 작업)로 실행
    threads = [
        threading.Thread(target=arisu_announcement_monitor.run_monitor, daemon=True),
        threading.Thread(target=g2b_announcement_monitor.run_monitor, daemon=True),
        threading.Thread(target=k_water_announcement_monitor_bot.run_monitor, daemon=True),
        threading.Thread(target=lh_announcement_monitor.run_monitor, daemon=True),
        threading.Thread(target=gh_announcement_monitor.run_monitor, daemon=True)
    ]
    
    # 모든 스레드 시작
    for t in threads:
        t.start()
        
    # 메인 프로그램이 꺼지지 않도록 무한 대기
    # while True 안에서 예외를 잡을 수 있도록 수정
    while True:
        for t in threads:
            t.join(1) # 1초씩 대기하며 메인 스레드가 블로킹되지 않게 함

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 관리자의 요청으로 모니터링 시스템을 안전하게 종료합니다.")