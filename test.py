import asyncio
from telegram import Bot

async def test_msg():
    # 1. 본인의 정보로 수정
    TOKEN = '8682869478:AAGHyOOpeZtuAlDV9JMmg3eXQTFhswydFaw'
    CHAT_ID = '8456543788'
    
    bot = Bot(token=TOKEN)
    
    try:
        print("메시지 전송 시도 중...")
        await bot.send_message(chat_id=CHAT_ID, text="🔔 테스트 메시지입니다! 이 메시지가 오면 성공입니다.")
        print("✅ 전송 성공! 이제 원래 스크립트를 사용하셔도 됩니다.")
    except Exception as e:
        print(f"❌ 전송 실패! 에러 내용: {e}")

if __name__ == "__main__":
    asyncio.run(test_msg())