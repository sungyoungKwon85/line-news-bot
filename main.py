import requests
from bs4 import BeautifulSoup
import os
import json
import urllib3
from google import genai

# SSL 인증서 경고 무시 (넷플릭스 등 크롤링 에러 방지용)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LINE_TOKEN = os.environ.get('LINE_TOKEN')
LINE_USER_ID = os.environ.get('LINE_USER_ID')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

def translate_text(text):
    if not GEMINI_API_KEY:
        return text
    try:
        # 구글의 새로운 최신 SDK 규격 적용
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"다음 IT 기술 블로그의 제목을 한국어로 자연스럽게 번역해줘. 부연 설명 없이 번역된 문장만 출력해:\n\n{text}"
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"번역 에러: {e}")
        return text

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
        # verify=False 를 추가하여 SSL 에러 우회
        response = requests.get(rss_url, timeout=10, verify=False)
        soup = BeautifulSoup(response.content, 'xml')
        
        latest_item = soup.find('item') or soup.find('entry')
        if not latest_item: continue
        
        title = latest_item.title.text.strip()
        
        link_tag = latest_item.link
        if link_tag:
            link = link_tag.text.strip() if link_tag.text.strip() else link_tag.get('href', '')
        else: continue
            
        last_link = last_posts.get(blog_name, "")
        
        if link and link != last_link:
            display_title = title
            
            if lang == "en":
                translated_title = translate_text(title)
                display_title = f"{translated_title}\n(원문: {title})"
            
            message = f"📢 {blog_name} 기술 블로그 새 글!\n\n[{display_title}]\n{link}"
            
            if send_line_message(message):
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
