import requests
from bs4 import BeautifulSoup
import os
import json
import urllib3
import time
from google import genai

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LINE_TOKEN = os.environ.get('JS_LINE_TOKEN')
LINE_USER_ID = os.environ.get('JS_USER_ID')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

def summarize_post(title, content, lang, retries=2):
    if not GEMINI_API_KEY:
        return f"[{title}]"
    
    if len(content) < 50:
        safe_content = "본문이 RSS에 제공되지 않았습니다. 원문 링크를 참고하세요."
    else:
        safe_content = content

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # 박사과정 연구자를 위한 맞춤형 요약 프롬프트
    prompt = f"""
    다음은 언어학, 인지과학, 제2언어 습득(SLA) 관련 최신 학술 기사 및 논문입니다. 박사과정 연구자가 동향을 빠르게 파악할 수 있도록 메시지를 작성해.
    
    요구사항:
    1. 제목이 영어라면 한국어로 번역해서 첫 줄에 대괄호 `[]` 안에 적어. (한국어면 원문 그대로)
    2. 본문 내용을 파악하여 '연구 주제(대상)'와 '핵심 결과' 위주로 2~3줄로 한글로 요약해. (각 줄은 `-` 로 시작)
    3. 인사말이나 불필요한 수식어 없이 딱 제목과 요약만 출력해.
    
    [원본 데이터]
    제목: {title}
    언어: {lang}
    본문: {safe_content}
    """
    
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            print(f"요약 에러 ({title}) - 시도 {attempt+1}/{retries}: {e}")
            if attempt < retries - 1:
                time.sleep(15) 
            else:
                return f"[{title}]\n- (API 호출 제한으로 요약 불가)"

def send_line_message(text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_TOKEN}"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}]
    }
    res = requests.post(url, headers=headers, json=payload)
    
    if res.status_code != 200:
        print(f"🚨 라인 전송 실패! 코드: {res.status_code}")
        return False
    return True

# 와이프분의 전공(언어학, 인지과학, 제2언어 습득)에 맞춘 글로벌 최상급 소스
FEEDS = {
    # --- 국제 학술지 (Open Access) ---
    "MDPI Languages (국제 언어학 저널)": {"url": "https://www.mdpi.com/rss/journal/languages", "lang": "en"},
    "Frontiers in Language Sciences": {"url": "https://www.frontiersin.org/journals/psychology/section/language-sciences/rss", "lang": "en"},
    
    # --- 최신 연구 및 과학 뉴스 ---
    "ScienceDaily (언어습득 연구)": {"url": "https://www.sciencedaily.com/rss/mind_brain/language_acquisition.xml", "lang": "en"},
    "ScienceDaily (인지심리학)": {"url": "https://www.sciencedaily.com/rss/mind_brain/cognitive_psychology.xml", "lang": "en"},
    
    # --- 저명한 언어학 블로그 ---
    "Language Log (펜실베니아대)": {"url": "https://languagelog.ldc.upenn.edu/nll/?feed=rss2", "lang": "en"},
    "All Things Linguistic": {"url": "https://allthingslinguistic.com/rss", "lang": "en"}
}

try:
    with open('last_posts_js.json', 'r', encoding='utf-8') as f:
        last_posts = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    last_posts = {}

new_posts_found = False

for blog_name, info in FEEDS.items():
    rss_url = info["url"]
    lang = info["lang"]
    try:
        response = requests.get(rss_url, timeout=10, verify=False)
        soup = BeautifulSoup(response.content, 'xml')
        
        latest_item = soup.find('item') or soup.find('entry')
        if not latest_item: continue
        
        title = latest_item.title.text.strip()
        
        link_tag = latest_item.link
        if link_tag:
            link = link_tag.text.strip() if link_tag.text.strip() else link_tag.get('href', '')
        else: continue
            
        content_tag = latest_item.find('content:encoded') or latest_item.find('encoded') or latest_item.find('description') or latest_item.find('summary') or latest_item.find('content')
        raw_content = content_tag.text if content_tag else ""
        
        text_content = BeautifulSoup(raw_content, "html.parser").get_text(separator=" ", strip=True)[:2000]

        last_link = last_posts.get(blog_name, "")
        
        if link and link != last_link:
            time.sleep(6) # 구글 API 제한 방지
            
            summary_message = summarize_post(title, text_content, lang)
            
            # 출처를 명확히 하기 위해 맨 밑에 저널/블로그 이름을 붙여줍니다.
            final_message = f"{summary_message}\n\n출처: {blog_name}\n{link}"
            
            if send_line_message(final_message):
                last_posts[blog_name] = link
                new_posts_found = True
                
    except Exception as e:
        print(f"{blog_name} 파싱 에러: {e}")

if new_posts_found:
    with open('last_posts_js.json', 'w', encoding='utf-8') as f:
        json.dump(last_posts, f, ensure_ascii=False, indent=2)
    print("새 글 전송 및 기록 업데이트 완료!")
else:
    print("새로운 글이 없습니다.")
