import requests
from bs4 import BeautifulSoup
import os
import json
import urllib3
import time
from google import genai

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 환경 변수 확인
LINE_TOKEN = os.environ.get('LINE_TOKEN')
LINE_USER_ID = os.environ.get('LINE_USER_ID')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

def summarize_post(title, content, lang, retries=2):
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY 가 설정되지 않았습니다.")
        return f"[{title}]"
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    당신은 15년차 시니어 백엔드 아키텍트입니다. 
    다음 기술 콘텐츠를 '실무 적용' 관점에서 요약하세요.
    1. 제목: 한글 번역 (대괄호 포함)
    2. 핵심 요약: 백엔드/AI 하네스 관점에서 3줄 이내 요약 (- 사용)
    3. 실무 키워드: 관련 스택 표시
    제목: {title} / 언어: {lang} / 본문: {content[:3000]}
    """
    
    for attempt in range(retries):
        try:
            # 모델명을 명확히 지정 (Gemini 3 Flash 사용)
            response = client.models.generate_content(
                model='gemini-3-flash', 
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            print(f"   - Gemini API 에러 (시도 {attempt+1}): {e}")
            time.sleep(5)
    return None

def send_line_message(text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": text}]}
    res = requests.post(url, headers=headers, json=payload)
    return res.status_code == 200

FEEDS = {
    "Anthropic News (MCP)": {"url": "https://www.anthropic.com/news/rss", "lang": "en"},
    "LangChain Blog": {"url": "https://blog.langchain.dev/rss/", "lang": "en"},
    "Spring Blog": {"url": "https://spring.io/blog.atom", "lang": "en"},
    "Cloudflare (AI/Edge)": {"url": "https://blog.cloudflare.com/rss/", "lang": "en"},
    "Langfuse (LLM Obs)": {"url": "https://langfuse.com/rss.xml", "lang": "en"},
    "Helicone (Cost)": {"url": "https://www.helicone.ai/blog/rss.xml", "lang": "en"},
    "Hugging Face Blog": {"url": "https://huggingface.co/blog/feed.xml", "lang": "en"}, 
    "Google AI Research": {"url": "http://googleresearch.blogspot.com/atom.xml", "lang": "en"},
    "OpenAI Engineering": {"url": "https://openai.com/blog/rss.xml", "lang": "en"}, 
    "GeekNews": {"url": "https://news.hada.io/rss", "lang": "ko"},
    "요즘IT (개발/기획 트렌드)": {"url": "https://yozm.wishket.com/magazine/feed/", "lang": "ko"}
}

# 상태 관리 로드
try:
    with open('last_posts.json', 'r', encoding='utf-8') as f:
        last_posts = json.load(f)
except:
    last_posts = {}
    print("ℹ️ 기존 기록이 없어 새로 생성합니다.")

new_posts_found = False

for blog_name, info in FEEDS.items():
    print(f"🔍 확인 중: {blog_name}...")
    try:
        response = requests.get(info["url"], timeout=20, verify=False)
        soup = BeautifulSoup(response.content, 'xml')
        
        # RSS(item) vs Atom(entry) 모두 대응
        entry = soup.find('item') or soup.find('entry')
        if not entry:
            print(f"   - 게시글을 찾을 수 없습니다.")
            continue
        
        title = entry.title.text.strip()
        
        # 링크 추출 방식 강화 (href 속성 우선 확인)
        link_tag = entry.find('link')
        if link_tag:
            link = link_tag.get('href') or link_tag.text.strip()
        else:
            print(f"   - 링크 태그가 없습니다.")
            continue

        # 중복 체크
        if link == last_posts.get(blog_name):
            print(f"   - 새로운 글 없음 (최근 글: {title[:20]}...)")
            continue

        print(f"   - ✨ 새 글 발견! 요약 중: {title}")
        
        # 본문 추출 로직 강화
        content_tag = entry.find(['content:encoded', 'content', 'description', 'summary'])
        text_content = BeautifulSoup(content_tag.text, "html.parser").get_text() if content_tag else "본문 없음"
        
        summary = summarize_post(title, text_content, info["lang"])
        if summary:
            if send_line_message(f"🚀 [AI Backend Skill]\n\n{summary}\n\n🔗 {link}"):
                last_posts[blog_name] = link
                new_posts_found = True
                print(f"   - ✅ 라인 전송 완료")
            else:
                print(f"   - 🚨 라인 전송 실패")
        
        time.sleep(2) # API Rate limit 방지
        
    except Exception as e:
        print(f"   - ❌ 에러 발생: {e}")

if new_posts_found:
    with open('last_posts.json', 'w', encoding='utf-8') as f:
        json.dump(last_posts, f, ensure_ascii=False, indent=2)
    print("\n🎉 모든 작업 완료!")
else:
    print("\n😴 업데이트된 내용이 없습니다.")
