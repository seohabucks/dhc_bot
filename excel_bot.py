import os
import time
import asyncio
from datetime import datetime
from telegram import Bot

# --- 설정 구간 ---
TOKEN = '8682869478:AAGHyOOpeZtuAlDV9JMmg3eXQTFhswydFaw'
CHAT_ID = '8456543788'

# 감시할 파일 리스트 (r을 붙이고 경로를 계속 추가하세요)
WATCH_LIST = [
    r"\\Dhcmain\(주)대호스토퍼\0영업사항(견적서)\●영업관리\1. 계약건(21).xlsx",
    r"\\Dhcmain\(주)대호스토퍼\0영업사항(견적서)\●영업관리\2. 특허,공고,입찰.xlsx"
    # r"\\Dhcmain\(주)대호스토퍼\다른_폴더\다른_파일.xlsx",
]

# 체크 주기 (초 단위) -> 테스트 시에는 10으로 바꿔서 해보세요!
CHECK_INTERVAL = 40 * 60  
# ------------------

def format_time_12h(timestamp):
    """타임스탬프를 오전/오후 12시간제로 변환"""
    dt = datetime.fromtimestamp(timestamp)
    # %p는 AM/PM을 출력하므로 한국어 오전/오후로 치환
    time_str = dt.strftime('%p %I:%M:%S')
    return time_str.replace('AM', '오전').replace('PM', '오후')

async def send_telegram_msg(text):
    try:
        bot = Bot(token=TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text=text)
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 전송 오류: {e}")

async def monitor_files():
    last_mtimes = {}
    initial_status = []
    
    print("--- 엑셀 파일 감시 프로그램 시작 ---")
    
    # 1. 초기 상태 확인 및 메시지 구성
    for path in WATCH_LIST:
        if os.path.exists(path):
            mtime = os.path.getmtime(path)
            last_mtimes[path] = mtime
            file_name = os.path.basename(path)
            formatted_time = format_time_12h(mtime)
            initial_status.append(f"📄 {file_name}\n(최근 수정: {formatted_time})")
        else:
            print(f"⚠️ 파일을 찾을 수 없음: {path}")

    if not last_mtimes:
        print("❌ 감시할 수 있는 파일이 없습니다.")
        return

    # 시작 알림 (최근 수정 시간 포함)
    start_msg = "🚀 [영업관리] 감시 시작\n\n" + "\n\n".join(initial_status)
    await send_telegram_msg(start_msg)
    print("시작 알림 전송 완료")

    try:
        while True:
            await asyncio.sleep(CHECK_INTERVAL)
            
            updated_files = []
            now_12h = format_time_12h(time.time())

            for path in WATCH_LIST:
                try:
                    current_mtime = os.path.getmtime(path)
                    
                    if current_mtime != last_mtimes[path]:
                        file_name = os.path.basename(path)
                        updated_files.append(file_name)
                        last_mtimes[path] = current_mtime
                except Exception as e:
                    print(f"파일 접근 오류: {e}")

            # 업데이트 알림
            if updated_files:
                msg = f"🔔 [업데이트 알림]\n확인 시간: {now_12h}\n"
                for f in updated_files:
                    msg += f"\n✅ {f}"
                
                await send_telegram_msg(msg)
                print(f"[{now_12h}] 업데이트 알림 전송 완료")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 변동 없음")
                
    except asyncio.CancelledError:
        # 프로그램이 강제로 취소되었을 때 (예: 프로세스 종료)
        await send_telegram_msg("🛑 [영업관리] 감시 프로그램이 중단되었습니다.")
    except KeyboardInterrupt:
        # 사용자가 Ctrl + C를 눌렀을 때
        await send_telegram_msg("👋 [영업관리] 사용자에 의해 감시가 종료되었습니다.")
    except Exception as e:
        # 기타 에러 발생 시
        await send_telegram_msg(f"⚠️ [영업관리] 시스템 오류로 중단됨: {e}")
    finally:
        # 어떤 이유든 종료될 때 최종적으로 한 번 더 확인 메시지 (선택 사항)
        print("프로그램을 종료합니다.")

if __name__ == "__main__":
    asyncio.run(monitor_files())