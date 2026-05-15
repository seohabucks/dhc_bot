import requests
from bs4 import BeautifulSoup
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import re
from urllib.parse import quote

def fetch_search_page(keyword, page_num):
    """특정 키워드로 검색된 결과 페이지를 수집합니다."""
    # 국토매일 사이트 검색 URL 구조 (euc-kr 인코딩 사용)
    encoded_keyword = quote(keyword.encode('euc-kr'))
    url = f"http://www.cenews.co.kr/news/articleList.html?page={page_num}&total=21454&sc_section_code=&sc_sub_section_code=&sc_serial_code=&sc_area=A&sc_level=&sc_article_type=&sc_view_level=&sc_sdate=&sc_edate=&sc_serial_number=&sc_word={encoded_keyword}&view_type=sm"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.encoding = 'euc-kr' 
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                articles = []
                
                # 검색 결과 리스트 추출
                titles = soup.select('.list-titles a')
                summaries = soup.select('.list-summary')
                times = soup.select('.list-times')
                
                if not titles: 
                    return None
                
                date_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")
                
                for i in range(len(titles)):
                    title_text = titles[i].get_text(strip=True)
                    summary_text = summaries[i].get_text(strip=True) if i < len(summaries) else ""
                    link = "http://www.cenews.co.kr" + titles[i]['href']
                    
                    raw_date_text = times[i].get_text(strip=True) if i < len(times) else ""
                    date_match = date_pattern.search(raw_date_text)
                    clean_date = date_match.group() if date_match else ""
                    
                    if title_text:
                        articles.append({
                            "검색키워드": keyword,
                            "날짜": clean_date,
                            "기사제목": title_text,
                            "요약문": summary_text,
                            "링크": link
                        })
                return articles
        except Exception as e:
            time.sleep(1)
            continue
    return []

def main():
    include_keywords = ["상수도", "아리수", "관로", "단수", "노후관", "부단수", "라인스토핑", "수자원공사", "水公", "정수장", "용수관", "열수송관", "열배관", "상하수도", "무단수"]
    exclude_keywords = ["협약", "칼럼", "MOU", "포럼", "세미나", "기념식", "시상식", "체결", "간담회", "캠페인", "홍보", "서포터즈", "워크숍", "심포지엄", "행사", "개최", "참석", "기부", "봉사", "인터뷰", "CEO", "유충", "활성탄"]

    all_data = []
    start_time = time.time()

    print(f"🚀 [키워드별 정밀 수집] 시작합니다. (총 {len(include_keywords)}개 키워드)")

    for kw in include_keywords:
        print(f"🔍 키워드 검색 중: [{kw}]")
        kw_data = []
        
        # 각 키워드당 최대 20페이지 수집
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_page = {executor.submit(fetch_search_page, kw, p): p for p in range(1, 21)}
            
            for future in as_completed(future_to_page):
                res = future.result()
                if res:
                    kw_data.extend(res)
        
        print(f"   -> [{kw}] 검색 결과: {len(kw_data)}개 발견")
        all_data.extend(kw_data)

    if not all_data:
        print("❌ 수집된 데이터가 없습니다.")
        return

    df = pd.DataFrame(all_data)
    
    # 링크 기준으로 중복 제거 (여러 키워드에 걸린 경우 첫 번째 키워드만 남음)
    df = df.drop_duplicates(subset=['링크'])

    neg_pattern = '|'.join([re.escape(k) for k in exclude_keywords])
    mask = ~(df['기사제목'].str.contains(neg_pattern, case=False, na=False, regex=True))
    filtered_df = df[mask].copy()

    if not filtered_df.empty:
        # 날짜순 정렬
        result_df = filtered_df.sort_values(by='날짜', ascending=False)
        
        # '검색키워드' 컬럼을 포함하여 최종 데이터프레임 구성
        final_df = result_df[['검색키워드', '날짜', '기사제목', '링크']]
        
        file_name = "뉴스기사_스크랩_결과.xlsx"
        try:
            final_df.to_excel(file_name, index=False)
            print(f"\n✅ 정밀 스크랩 완료!")
            print(f"⏱ 총 소요 시간: {time.time() - start_time:.2f}초")
            print(f"📊 최종 수집 기사: {len(final_df)}개 (홍보성 기사 제외됨)")
            print(f"💾 파일 저장 완료: {file_name}")
        except Exception as e:
            print(f"❌ 파일 저장 중 오류 발생: {e}")
    else:
        print("\n🔍 조건에 맞는 기사가 없습니다.")

if __name__ == "__main__":
    main()