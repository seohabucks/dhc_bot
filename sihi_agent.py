from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
import streamlit as st
import re
import json
import os
from urllib.parse import urljoin


# Selenium 관련 라이브러리 임포트
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

SESSION_FILE = "crawler_session.json"

def save_session_state():
    """현재 크롤링 작업과 필터 키워드를 JSON 파일에 저장합니다."""
    if 'crawl_tasks' in st.session_state or 'filter_keywords' in st.session_state:
        state_to_save = {
            'crawl_tasks': st.session_state.get('crawl_tasks', []),
            'filter_keywords': st.session_state.get('filter_keywords', []),
            'exclude_keywords': st.session_state.get('exclude_keywords', []),
            'cycle_time': st.session_state.get('cycle_time', 10),
            'min_chars': st.session_state.get('min_chars', 0)
        }
        try:
            with open(SESSION_FILE, 'w', encoding='utf-8') as f:
                json.dump(state_to_save, f, ensure_ascii=False, indent=4)
        except Exception as e:
            st.warning(f"세션 저장 중 오류 발생: {e}")

def load_session_state():
    """JSON 파일이 존재하면 크롤링 작업과 필터 키워드를 불러옵니다."""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
                st.session_state.crawl_tasks = state.get('crawl_tasks', [])
                st.session_state.filter_keywords = state.get('filter_keywords', [])
                st.session_state.exclude_keywords = state.get('exclude_keywords', [])
                st.session_state.cycle_time = max(10, state.get('cycle_time', 10))
                st.session_state.min_chars = state.get('min_chars', 0)
        except (json.JSONDecodeError, FileNotFoundError):
            st.session_state.crawl_tasks = []
            st.session_state.filter_keywords = []
            st.session_state.exclude_keywords = []
            st.session_state.cycle_time = 10
            st.session_state.min_chars = 0
    else:
        st.session_state.crawl_tasks = []
        st.session_state.filter_keywords = []
        st.session_state.exclude_keywords = []
        st.session_state.cycle_time = 10
        st.session_state.min_chars = 0

class WebIntelligenceCrawler:
    def __init__(self):
        self.results = []

    def fetch_data(self, driver, url, selector=None):
        """
        특정 URL에서 텍스트를 추출합니다.
        셀렉터가 지정되면 해당 영역의 텍스트를, 아니면 페이지 전체 텍스트를 추출합니다.
        Selenium을 사용하여 동적으로 렌더링된 페이지의 데이터를 가져옵니다.
        """
        try:
            driver.get(url)
            
            # 동적 콘텐츠가 로딩될 때까지 최대 10초 대기
            try:
                if selector:
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                else:
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            except TimeoutException:
                pass # 시간 초과되어도 일단 진행 (데이터가 일부만 렌더링되었을 수 있음)
                
            # 추가 스크립트 실행 및 렌더링 완료를 위한 여유 시간 대기
            time.sleep(1.5) 
 
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            extracted_item = {'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'url': url}
 
            # 스크립트와 스타일 태그는 항상 제거
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose()
 
            texts = []
            links = []
            
            def is_valid_link(href):
                if not href or len(href) < 2:
                    return False
                href_lower = href.lower()
                # 가짜 링크(자바스크립트 실행, 빈 앵커 등) 필터링
                if href_lower.startswith('javascript:') or href_lower == '#':
                    return False
                return True

            def extract_hidden_url(element):
                """태그 내부에 다양한 형태로 숨겨진 URL을 찾아냅니다."""
                if not element: return ""
                # 1. 일반적인 href 속성 (a 태그 등)
                if element.has_attr('href') and is_valid_link(element.get('href')):
                    return urljoin(url, element.get('href'))
                # 2. data-url, data-href, data-link 등 커스텀 속성
                for attr in ['data-url', 'data-href', 'data-link', 'data-uri']:
                    if element.has_attr(attr) and is_valid_link(element.get(attr)):
                        return urljoin(url, element.get(attr))
                # 3. onclick 이벤트 내부에 숨겨진 주소 추출 (예: onclick="window.open('/path')")
                if element.has_attr('onclick'):
                    match = re.search(r"['\"](/[^'\"]+|http[^'\"]+)['\"]", element.get('onclick'))
                    if match and is_valid_link(match.group(1)):
                        return urljoin(url, match.group(1))
                return ""

            def process_elements(parent, use_fallback=False):
                fallback_link = ""
                if use_fallback:
                    curr = parent
                    for _ in range(4): # 자기 자신(0) + 상위 1, 2, 3단계
                        if curr is None or curr.name == 'body':
                            break
                        extracted = extract_hidden_url(curr)
                        if extracted:
                            fallback_link = extracted
                            break
                        curr = curr.parent
                        
                    if not fallback_link:
                        # 하위 모든 태그를 뒤져서 숨겨진 링크가 있는지 탐색
                        for el in parent.find_all(True):
                            extracted = extract_hidden_url(el)
                            if extracted:
                                fallback_link = extracted
                                break

                # 텍스트를 합치지 않고 모두 개별 조각으로 분리하여 처리
                for text_node in parent.find_all(string=True):
                    text = text_node.strip()
                    if text:
                        full_link = ""
                        for p_tag in text_node.parents:
                            extracted = extract_hidden_url(p_tag)
                            if extracted:
                                full_link = extracted
                                break
                            if p_tag == parent: # 설정한 블록 범위를 벗어나지 않도록 제한
                                break
                                
                        if not full_link:
                            full_link = fallback_link
                            
                        texts.append(text)
                        links.append(full_link)

            if selector:
                target_areas = soup.select(selector)
                if target_areas:
                    for area in target_areas:
                        process_elements(area, use_fallback=True)
                else:
                    texts.append(f"N/A (Selector '{selector}' not found)")
                    links.append("")
            else:
                if soup.body:
                    process_elements(soup.body, use_fallback=False)
                else:
                    texts.append("N/A (Body not found)")
                    links.append("")
 
            extracted_item['text_list'] = texts
            extracted_item['link_list'] = links

            return extracted_item
        except Exception as e:
            return {'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'url': url, 'error': str(e)}

    def run_batch(self, tasks, progress_bar=None):
        """
        여러 작업을 순회하며 데이터를 취합합니다.
        """
        self.results = []
        total = len(tasks)
        
        # Selenium Chrome 옵션 설정 (눈에 보이지 않는 헤드리스 모드)
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            st.error(f"Chrome WebDriver 실행 오류: {e}\n\n서버 환경에 Chrome 브라우저가 설치되어 있는지 확인해주세요.")
            return pd.DataFrame()

        for i, task in enumerate(tasks):
            url = task.get('url')
            selector = task.get('selector')
            if not url:
                continue
 
            data = self.fetch_data(driver, url, selector)
            self.results.append(data)
            
            if progress_bar:
                progress_bar.progress((i + 1) / total)
            
            time.sleep(0.5) # 서버 부하 방지
        
        driver.quit() # 취합 완료 후 브라우저 종료
        
        expanded_rows = []
        for res in self.results:
            ts = res.get('timestamp')
            u = res.get('url')
            err = res.get('error')
            if err:
                expanded_rows.append({'timestamp': ts, 'url': u, 'text_list': err, 'link_list': ''})
                continue
                
            texts = res.get('text_list', [])
            links = res.get('link_list', [])
            
            if not texts:
                expanded_rows.append({'timestamp': ts, 'url': u, 'text_list': '', 'link_list': ''})
            else:
                for t, l in zip(texts, links):
                    expanded_rows.append({'timestamp': ts, 'url': u, 'text_list': t, 'link_list': l})
                    
        df = pd.DataFrame(expanded_rows)
        return df

# --- Streamlit UI 구성 ---
def main():
    st.set_page_config(page_title="Mu Crawler Dashboard", layout="wide")

    # 세션 상태 초기화: 앱이 처음 로드될 때 파일에서 이전 상태를 불러옵니다.
    if 'crawl_tasks' not in st.session_state:
        load_session_state()
    if 'df_result' not in st.session_state:
        st.session_state.df_result = None
    if 'exclude_keywords' not in st.session_state:
        st.session_state.exclude_keywords = []
    if 'cycle_time' not in st.session_state:
        st.session_state.cycle_time = 10
    else:
        st.session_state.cycle_time = max(10, st.session_state.cycle_time)
    if 'is_running' not in st.session_state:
        st.session_state.is_running = False
    if 'last_crawl_time' not in st.session_state:
        st.session_state.last_crawl_time = 0
    if 'force_crawl' not in st.session_state:
        st.session_state.force_crawl = False
    if 'min_chars' not in st.session_state:
        st.session_state.min_chars = 0

    # 상단 메뉴 및 제목
    st.title("🌐 Hello World!")
    st.markdown("수집할 사이트의 URL을 추가하고, 한 번에 전체 텍스트를 취합하세요.")

    # --- 1. 작업 추가 입력 UI ---
    st.subheader("1. 작업 추가하기")
    # st.form을 사용해 입력 필드와 추가 버튼을 묶어 관리합니다.
    with st.form("task_form", clear_on_submit=True):
        url_input = st.text_input("대상 사이트 URL", placeholder="https://news.naver.com/...")
        selector_input = st.text_input(
            "대상 영역 CSS 셀렉터 (선택 사항)",
            placeholder="div.content_area",
            help="F12 개발자 도구에서 원하는 요소 우클릭 > Copy > Copy selector. 비워두면 페이지 전체를 대상으로 합니다."
        )
        add_button = st.form_submit_button("➕ 작업 목록에 추가", use_container_width=True)

    # '작업 추가' 버튼 클릭 시 로직
    if add_button:
        url = url_input.strip()
        selector = selector_input.strip()
        if not url:
            st.warning("URL을 입력해주세요.")
        else:
            new_task = {'url': url, 'selector': selector}
            if new_task in st.session_state.crawl_tasks:
                st.warning("이미 목록에 추가된 작업입니다.")
            else:
                st.session_state.crawl_tasks.append(new_task)
                save_session_state()
                st.success(f"작업이 추가되었습니다: {url}")

    st.divider()

    # --- 2. 추가된 작업 목록 및 실행 UI ---
    st.subheader("2. 데이터 취합 실행하기")
    
    if not st.session_state.crawl_tasks:
        st.info("1번 항목에서 작업을 추가하면 목록이 여기에 표시됩니다.")
    else:
        st.write(f"**총 {len(st.session_state.crawl_tasks)}개의 작업이 목록에 있습니다.**")
        indices_to_remove = []
        for i, task in enumerate(st.session_state.crawl_tasks):
            with st.expander(f"**작업 {i + 1}**: {task['url']}"):
                if task.get('selector'):
                    st.write(f"**대상 영역:** `{task['selector']}`")
                else:
                    st.info("이 작업은 페이지의 모든 텍스트를 추출합니다.")
                if st.button("➖ 이 작업 제거", key=f"remove_{i}", use_container_width=True):
                    indices_to_remove.append(i)

        if indices_to_remove:
            for index in sorted(indices_to_remove, reverse=True):
                st.session_state.crawl_tasks.pop(index)
            save_session_state()
            st.rerun()

    st.markdown("##### ⚙️ 수집 설정")
    col_cycle, col_min_chars = st.columns(2)
    with col_cycle:
        new_cycle = st.number_input("사이클 타임 (분 단위, 최소 10분)", min_value=10, step=1, value=st.session_state.cycle_time, disabled=st.session_state.is_running)
        if new_cycle != st.session_state.cycle_time:
            st.session_state.cycle_time = new_cycle
            save_session_state()
    with col_min_chars:
        new_min = st.number_input("텍스트 최소 글자수 필터 (해당 길이 이하는 저장 및 표시 제외)", min_value=0, step=1, value=st.session_state.min_chars)
        if new_min != st.session_state.min_chars:
            st.session_state.min_chars = new_min
            save_session_state()

    col_run, col_clear = st.columns(2)
    with col_run:
        if st.session_state.is_running:
            if st.button("⏹️ 데이터 취합 정지", use_container_width=True, type="secondary"):
                st.session_state.is_running = False
                st.rerun()
        else:
            if st.button("🚀 데이터 취합 시작", use_container_width=True, type="primary", disabled=not st.session_state.crawl_tasks):
                st.session_state.is_running = True
                st.session_state.force_crawl = True
                st.rerun()
    with col_clear:
        if st.button("🗑️ 모든 작업 지우기", use_container_width=True, disabled=not st.session_state.crawl_tasks or st.session_state.is_running):
            st.session_state.crawl_tasks = []
            save_session_state()
            st.rerun()

    do_crawl = False
    if st.session_state.is_running:
        cycle_seconds = st.session_state.cycle_time * 60
        time_since_last = time.time() - st.session_state.last_crawl_time
        if time_since_last >= cycle_seconds or st.session_state.force_crawl:
            do_crawl = True

    if do_crawl:
        st.session_state.force_crawl = False
        crawler = WebIntelligenceCrawler()
        my_bar = st.progress(0, text="데이터를 수집하는 중입니다. 잠시만 기다려주세요...")
        new_df = crawler.run_batch(st.session_state.crawl_tasks, my_bar)
        
        if not new_df.empty:
            # 컬럼 순서 재배치 (시간/URL/텍스트/링크 순서 보장)
            cols = ['timestamp', 'url', 'text_list', 'link_list']
            existing_cols = [c for c in cols if c in new_df.columns] + [c for c in new_df.columns if c not in cols]
            new_df = new_df[existing_cols]
            
            # 수집된 데이터를 누적
            if st.session_state.df_result is None or st.session_state.df_result.empty:
                # 앱 재시작 후 첫 수집 시 기존 로그가 있다면 불러와서 합침 (데이터 유실 방지)
                if os.path.exists("crawler_log.csv"):
                    try:
                        existing_df = pd.read_csv("crawler_log.csv")
                        if 'link_list' not in existing_df.columns:
                            existing_df['link_list'] = ""
                        st.session_state.df_result = pd.concat([existing_df, new_df], ignore_index=True)
                    except Exception:
                        st.session_state.df_result = new_df
                else:
                    st.session_state.df_result = new_df
            else:
                st.session_state.df_result = pd.concat([st.session_state.df_result, new_df], ignore_index=True)
                
            # 중복 데이터 처리: URL, 텍스트, 링크가 일치하는 경우 기존 항목을 지우고 최신 데이터(마지막 행)만 남김
            if 'text_list' in st.session_state.df_result.columns:
                subset_cols = ['url', 'text_list']
                if 'link_list' in st.session_state.df_result.columns:
                    subset_cols.append('link_list')
                st.session_state.df_result = st.session_state.df_result.drop_duplicates(subset=subset_cols, keep='last').reset_index(drop=True)
                
            # 타임스탬프 기준 내림차순 정렬 (가장 최근 시간이 위로)
            if 'timestamp' in st.session_state.df_result.columns:
                st.session_state.df_result = st.session_state.df_result.sort_values(by='timestamp', ascending=False).reset_index(drop=True)
                
            # 로그 파일 자동 저장 (최소 글자수 필터 적용 및 전체 덮어쓰기로 갱신)
            if 'text_list' in st.session_state.df_result.columns and st.session_state.min_chars > 0:
                log_df = st.session_state.df_result[st.session_state.df_result['text_list'].astype(str).str.len() > st.session_state.min_chars]
            else:
                log_df = st.session_state.df_result
                
            try:
                log_df.to_csv("crawler_log.csv", mode='w', index=False, encoding='utf-8-sig')
            except Exception as e:
                st.error(f"로그 파일 저장 중 오류 발생: {e}")

        my_bar.empty()
        st.session_state.last_crawl_time = time.time()
        
    # 수집된 데이터가 세션에 저장되어 있다면 결과와 필터 UI를 표시
    if st.session_state.df_result is not None:
        st.divider()
        st.subheader("📊 수집 데이터 결과")
        df_result = st.session_state.df_result
        
        if not df_result.empty:
            if 'text_list' in df_result.columns and st.session_state.min_chars > 0:
                filtered_df = df_result[df_result['text_list'].astype(str).str.len() > st.session_state.min_chars]
            else:
                filtered_df = df_result
                
            # --- 키워드 필터 추가 (OR 조건) ---
            st.markdown("##### 🔍 특정 키워드 포함 필터")
            col_kw, col_add = st.columns([4, 1])
            with col_kw:
                new_kw = st.text_input("추가할 키워드를 입력하세요", key="new_kw_input", label_visibility="collapsed", placeholder="포함할 키워드 입력...")
            with col_add:
                if st.button("Add++", use_container_width=True):
                    if new_kw and new_kw not in st.session_state.filter_keywords:
                        st.session_state.filter_keywords.append(new_kw)
                        save_session_state()
                        st.rerun()
                        
            if st.session_state.filter_keywords:
                active_keywords = st.multiselect(
                    "적용된 키워드 목록 (X를 누르면 필터에서 제거됩니다)",
                    options=st.session_state.filter_keywords,
                    default=st.session_state.filter_keywords
                )
                
                if active_keywords != st.session_state.filter_keywords:
                    st.session_state.filter_keywords = active_keywords
                    save_session_state()
                    st.rerun()
                    
                if 'text_list' in filtered_df.columns and active_keywords:
                    pattern = '|'.join([re.escape(kw) for kw in active_keywords])
                    filtered_df = filtered_df[filtered_df['text_list'].astype(str).str.contains(pattern, case=False, na=False)]

            # --- 제외 키워드 필터 추가 (NOT 조건) ---
            st.markdown("##### 🚫 특정 키워드 제외 필터")
            col_exkw, col_exadd = st.columns([4, 1])
            with col_exkw:
                new_exkw = st.text_input("제외할 키워드를 입력하세요", key="new_exkw_input", label_visibility="collapsed", placeholder="제외할 키워드 입력...")
            with col_exadd:
                if st.button("Add--", use_container_width=True):
                    if new_exkw and new_exkw not in st.session_state.exclude_keywords:
                        st.session_state.exclude_keywords.append(new_exkw)
                        save_session_state()
                        st.rerun()
                        
            if st.session_state.exclude_keywords:
                active_ex_keywords = st.multiselect(
                    "제외된 키워드 목록 (X를 누르면 필터에서 제거됩니다)",
                    options=st.session_state.exclude_keywords,
                    default=st.session_state.exclude_keywords,
                    key="active_ex_keywords"
                )
                
                if active_ex_keywords != st.session_state.exclude_keywords:
                    st.session_state.exclude_keywords = active_ex_keywords
                    save_session_state()
                    st.rerun()
                    
                if 'text_list' in filtered_df.columns and active_ex_keywords:
                    ex_pattern = '|'.join([re.escape(kw) for kw in active_ex_keywords])
                    filtered_df = filtered_df[~filtered_df['text_list'].astype(str).str.contains(ex_pattern, case=False, na=False)]

            # --- 화면 출력용 데이터프레임 복사본 생성 (키워드 빨간색 강조) ---
            display_df = filtered_df.copy()
            
            if 'text_list' in display_df.columns and st.session_state.filter_keywords:
                for kw in st.session_state.filter_keywords:
                    # 대소문자 구분 없이 키워드를 찾아 HTML 태그로 감쌈
                    regex = re.compile(f"({re.escape(kw)})", re.IGNORECASE)
                    display_df['text_list'] = display_df['text_list'].apply(
                        lambda x: regex.sub(r'<span style="color:red; font-weight:bold;">\1</span>', str(x))
                    )

            # 링크 하이퍼링크 처리 및 컬럼명 변경
            if 'link_list' in display_df.columns:
                display_df['link_list'] = display_df['link_list'].apply(
                    lambda x: f'<a href="{x}" target="_blank" style="color:blue; text-decoration:underline;">바로가기</a>' if pd.notna(x) and str(x).strip() else ""
                )

            display_df = display_df.rename(columns={
                'timestamp': '타임스탬프',
                'url': '검색 주소',
                'text_list': '제목',
                'link_list': '바로가기'
            })

            # CSV 내보내기 및 로그 지우기 버튼을 표 바로 위에 배치
            col_download, col_clear = st.columns(2)
            with col_download:
                csv = filtered_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button("📥 결과 CSV로 내보내기", csv, f"crawl_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 'text/csv', use_container_width=True)
            with col_clear:
                if st.button("🗑️ 누적 로그 모두 지우기", use_container_width=True, type="primary"):
                    st.session_state.df_result = None
                    if os.path.exists("crawler_log.csv"):
                        try:
                            os.remove("crawler_log.csv")
                        except Exception:
                            pass
                    st.rerun()

            html_table = display_df.to_html(escape=False, index=False)
            st.markdown(f'<div style="overflow-x: auto; overflow-y: auto; font-size: 12px;">{html_table}</div>', unsafe_allow_html=True)
        else:
            st.error("데이터를 수집하지 못했습니다. URL을 다시 확인해주세요.")

    # --- 반복 실행 타이머 ---
    if st.session_state.is_running:
        cycle_seconds = st.session_state.cycle_time * 60
        time_since_last = time.time() - st.session_state.last_crawl_time
        remaining_seconds = int(cycle_seconds - time_since_last)
        
        if remaining_seconds > 0:
            st.divider()
            countdown_placeholder = st.empty()
            while remaining_seconds > 0:
                minutes, seconds = divmod(remaining_seconds, 60)
                countdown_placeholder.info(f"⏳ 자동 수집 활성화 됨: 다음 수집까지 {minutes}분 {seconds}초 남았습니다... \n정지하려면 '데이터 취합 정지' 버튼을 누르세요.")
                time.sleep(1)
                remaining_seconds -= 1
            
            st.rerun() # 타이머 종료 후 다음 수집 트리거
        else:
            st.rerun()


if __name__ == "__main__":
    main()