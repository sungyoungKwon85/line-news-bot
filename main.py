import requests
from bs4 import BeautifulSoup
import os
import json
import urllib3
from google import genai

# SSL 인증서 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LINE_TOKEN = os.environ.get('LINE_TOKEN')
LINE_USER_ID = os.environ.get('LINE_USER_ID')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

def summarize_post(title, content, lang):
    if not GEMINI_API_KEY:
        return f"[{title}]"
    
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # 백엔드 동료에게 쿨하게 핵심만 공유하는 느낌의 프롬프트
        prompt = f"""
        다음 IT 기술 블로그 글을 읽고 메시지를 작성해줘.
        
        요구사항:
        1. 제목이 영어라면 한국어로 번역해서 첫 줄에 대괄호 `[]` 안에 적어. (한국어면 원문 그대로)
        2. 본문 내용을 파악하여 백엔드/아키텍처 관점에서 핵심만 2~3줄로 한글로 요약해. (각 줄은 `-` 로 시작)
        3. "블로그 새 글!" 같은 불필요한 수식어나 인사말은 절대 넣지 말고 딱 제목과 요약만 출력해.
        
        [원본 데이터]
        제목: {title}
        언어: {lang}
        본문: {content}
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"요약 에러: {e}")
        return f"[{title}]\n(요약 중 오류가 발생했습니다)"

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
        print(f"🚨 에러 상세 내용: {res.text}")
        return False
    return True

FEEDS = {
    # --- 국내 10개 ---
    "토스": {"url": "https://toss.tech/rss.xml", "lang": "ko"},
    "우아한형제들(배민)": {"url": "https://techblog.woowahan.com/feed/", "lang": "ko"},
    "카카오 테크": {"url": "https://tech.kakao.com/feed/", "lang": "ko"},
    "라인(LINE)": {"url": "https://engineering.linecorp.com/ko/feed/", "lang": "ko"},
    "당근마켓": {"url": "https://medium.com/feed/daangn", "lang": "ko"},
    "카카오페이": {"url": "https://tech.kakaopay.com/rss.xml", "lang": "ko"},
    "컬리(Kurly)": {"url": "https://helloworld.kurly.com/feed", "lang": "ko"},
    "왓챠(Watcha)": {"url": "https://medium.com/feed/watcha", "lang": "ko"},
    "야놀자": {"url": "https://medium.com/feed/yanolja", "lang": "ko"},
    "쏘카(Socar)": {"url": "https://tech.socarcorp.kr/feed", "lang": "ko"},

    # --- 해외 10개 ---
    "Spotify Engineering": {"url": "https://engineering.atspotify.com/feed/", "lang": "en"},
    "Netflix TechBlog": {"url": "https://netflixtechblog.com/feed", "lang": "en"},
    "Uber Engineering": {"url": "https://www.uber.com/en-KR/blog/engineering/rss/", "lang": "en"},
    "Airbnb Engineering": {"url": "https://medium.com/feed/airbnb-engineering", "lang": "en"},
    "Meta Engineering": {"url": "https://engineering.fb.com/feed/", "lang": "en"},
    "Cloudflare": {"url": "https://blog.cloudflare.com/rss/", "lang": "en"},
    "Pinterest Engineering": {"url": "https://medium.com/feed/@Pinterest_Engineering", "lang": "en"},
    "Slack Engineering": {"url": "https://slack.engineering/feed/", "lang": "en"},
    "Dropbox Tech": {"url": "https://dropbox.tech/feed", "lang": "en"},
    "ByteByteGo (System Design)": {"url": "https://blog.bytebytego.com/feed", "lang": "en"}
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
        
        # 1. 제목 추출
        title = latest_item.title.text.strip()
        
        # 2. 링크 추출
        link_tag = latest_item.link
        if link_tag:
            link = link_tag.text.strip() if link_tag.text.strip() else link_tag.get('href', '')
        else: continue
            
        # 3. 본문 추출 (RSS 포맷마다 태그가 달라서 순차적으로 탐색)
        content_tag = latest_item.find('content:encoded') or latest_item.find('encoded') or latest_item.find('description') or latest_item.find('summary') or latest_item.find('content')
        raw_content = content_tag.text if content_tag else ""
        
        # HTML 태그 제거 및 텍스트 2000자로 제한 (토큰 절약 및 속도 향상)
        text_content = BeautifulSoup(raw_content, "html.parser").get_text(separator=" ", strip=True)[:2000]

        last_link = last_posts.get(blog_name, "")
        
        if link and link != last_link:
            # LLM을 통해 제목 번역 및 2~3줄 요약 생성
            summary_message = summarize_post(title, text_content, lang)
            
            # 최종 전송 메시지 조합 (불필요한 타이틀 제외)
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
