import requests
from bs4 import BeautifulSoup
import os
import json
import urllib3
import time
from google import genai

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LINE_TOKEN = os.environ.get('LINE_TOKEN')
LINE_USER_ID = os.environ.get('LINE_USER_ID')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

def summarize_post(title, content, lang, retries=2):
    if not GEMINI_API_KEY:
        return f"[{title}]"
    
    if len(content) < 50:
        safe_content = "본문이 RSS에 제공되지 않았습니다. 원문 링크를 참고하세요."
    else:
        safe_content = content

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""
    다음 IT 기술 블로그 글을 읽고 메시지를 작성해.
    
    요구사항:
    1. 제목이 영어라면 한국어로 번역해서 첫 줄에 대괄호 `[]` 안에 적어. (한국어면 원문 그대로)
    2. 본문 내용을 파악하여 백엔드/아키텍처 관점에서 핵심만 2~3줄로 한글로 요약해. (각 줄은 `-` 로 시작)
    3. 인사말이나 수식어 없이 딱 제목과 요약만 출력해.
    
    [원본 데이터]
    제목: {title}
    언어: {lang}
    본문: {safe_content}
    """
    
    # 에러 시 재시도(Retry) 로직
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
                print("15초 대기 후 재시도합니다...")
                time.sleep(15) # 제한에 걸렸을 경우 15초간 충분히 휴식
            else:
                return None

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

FEEDS = {
    # --- 국내: AI 트렌드 & 대규모 B2C 백엔드 ---
    "GeekNews (AI/개발 트렌드)": {"url": "https://news.hada.io/rss", "lang": "ko"}, # 💡 주소 수정 완료!
    "네이버 D2 (AI & 데이터)": {"url": "https://d2.naver.com/d2.atom", "lang": "ko"}, # 국내 AI 기술력 탑티어
    "토스 테크": {"url": "https://toss.tech/rss.xml", "lang": "ko"},
    "우아한형제들(배민)": {"url": "https://techblog.woowahan.com/feed/", "lang": "ko"},
    "당근마켓": {"url": "https://medium.com/feed/daangn", "lang": "ko"},
    "라인(LINE) Engineering": {"url": "https://engineering.linecorp.com/ko/feed/", "lang": "ko"},

    # --- 해외: 찐 AI 코어 & AI 백엔드 엔지니어링 ---
    "OpenAI Engineering": {"url": "https://openai.com/blog/rss.xml", "lang": "en"}, # 챗GPT 본진의 기술 블로그
    "Hugging Face Blog": {"url": "https://huggingface.co/blog/feed.xml", "lang": "en"}, # 오픈소스 AI 모델의 성지
    "Google AI Research": {"url": "http://googleresearch.blogspot.com/atom.xml", "lang": "en"},
    "Meta Engineering": {"url": "https://engineering.fb.com/feed/", "lang": "en"}, # Llama 모델과 대규모 인프라
    "AWS Machine Learning": {"url": "https://aws.amazon.com/blogs/machine-learning/feed/", "lang": "en"}, # 실무 클라우드 AI 적용기
    "Netflix TechBlog": {"url": "https://netflixtechblog.com/feed", "lang": "en"}, # 추천 알고리즘 및 글로벌 트래픽 처리
    "Uber Engineering": {"url": "https://www.uber.com/en-KR/blog/engineering/rss/", "lang": "en"},
    "ByteByteGo (System Design)": {"url": "https://blog.bytebytego.com/feed", "lang": "en"} # 대규모 시스템 설계 꿀팁
}

try:
    with open('last_posts.json', 'r', encoding='utf-8') as f:
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
            # ⭐ 기본 대기 시간을 6초로 늘려 안정성 확보
            time.sleep(6)
            
            summary_message = summarize_post(title, text_content, lang)
            if summary_message is None:
                print(f"⚠️ [{blog_name}] 요약 실패! 라인 전송을 보류하고 내일 다시 시도합니다.")
                continue
            final_message = f"{summary_message}\n\n{link}"
            
            if send_line_message(final_message):
                last_posts[blog_name] = link
                new_posts_found = True
                
    except Exception as e:
        print(f"{blog_name} 파싱 에러: {e}")

if new_posts_found:
    with open('last_posts.json', 'w', encoding='utf-8') as f:
        json.dump(last_posts, f, ensure_ascii=False, indent=2)
    print("새 글 전송 및 기록 업데이트 완료!")
else:
    print("새로운 글이 없습니다.")
