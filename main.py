import requests
from bs4 import BeautifulSoup
import os
import json
import urllib3
import time
from google import genai

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 환경 변수
LINE_TOKEN = os.environ.get('LINE_TOKEN')
LINE_USER_ID = os.environ.get('LINE_USER_ID')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

def summarize_post(title, content, lang, retries=2):
    if not GEMINI_API_KEY:
        return f"[{title}]"
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # 백엔드 개발자 맞춤형 프롬프트로 강화
    prompt = f"""
    당신은 15년차 시니어 백엔드 아키텍트이자 AI 엔지니어입니다. 
    다음 기술 콘텐츠를 분석하여 '실무 적용 가능성' 중심으로 요약하세요.
    
    [분석 가이드라인]
    1. 제목: 한국어로 번역 (대괄호 포함)
    2. 핵심 요약 (3줄 이내): 
       - 이 기술/도구가 '어떤 백엔드 문제를 해결'하는가?
       - Graphify처럼 '비용(토큰) 절감'이나 '성능(Virtual Threads 등)'에 이득이 있는가?
       - 구체적인 '하네스(Harness)'나 '패턴'이 언급되었는가?
    3. 실무 키워드: 관련 기술 스택(예: Java, MCP, RAG, Prompt Caching 등)을 별도로 표시.

    [원본 데이터]
    제목: {title}
    언어: {lang}
    본문: {content[:3000]} 
    """
    
    for attempt in range(retries):
        try:
            # 모델명은 현재 사용 가능한 최신 버전으로 유지
            response = client.models.generate_content(
                model='gemini-3-flash', 
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            time.sleep(10)
            if attempt == retries - 1: return None

def send_line_message(text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": text}]}
    res = requests.post(url, headers=headers, json=payload)
    return res.status_code == 200

# --- 백엔드 + AI 하네스 특화 피드 ---
FEEDS = {
    # --- 해외: 찐 AI 코어 & AI 백엔드 엔지니어링 ---
    "Hugging Face Blog": {"url": "https://huggingface.co/blog/feed.xml", "lang": "en"}, 
    "Google AI Research": {"url": "http://googleresearch.blogspot.com/atom.xml", "lang": "en"},
    "Netflix TechBlog": {"url": "https://netflixtechblog.com/feed", "lang": "en"}, 
    
    # 1. AI 아키텍처 & 하네스 (가장 중요)
    "Anthropic News (MCP/Context)": {"url": "https://www.anthropic.com/news/rss", "lang": "en"},
    "LangChain Blog (Agentic Patterns)": {"url": "https://blog.langchain.dev/rss/", "lang": "en"},
    "LlamaIndex (RAG & Data Harness)": {"url": "https://www.llamaindex.ai/blog/rss.xml", "lang": "en"},
    "OpenAI Engineering": {"url": "https://openai.com/blog/rss.xml", "lang": "en"}, 
    
    # 2. 백엔드 실무 & 성능 (Spring/Java/Infrastructure)
    "Spring Blog (Spring AI/Virtual Threads)": {"url": "https://spring.io/blog.atom", "lang": "en"},
    "Cloudflare Blog (AI at Edge/Inference)": {"url": "https://blog.cloudflare.com/rss/", "lang": "en"},
    "Netflix TechBlog (Scale & AI)": {"url": "https://netflixtechblog.com/feed", "lang": "en"},
    
    # 3. AI 관측성 & 토큰 최적화
    "Langfuse Blog (LLM Observability)": {"url": "https://langfuse.com/rss.xml", "lang": "en"},
    "Helicone (Token/Cost Optimization)": {"url": "https://www.helicone.ai/blog/rss.xml", "lang": "en"},

    # 4. 국내 정제된 정보 (큐레이션)
    "GeekNews (핵심 요약)": {"url": "https://news.hada.io/rss", "lang": "ko"},
    "요즘IT (개발/기획 트렌드)": {"url": "https://yozm.wishket.com/magazine/feed/", "lang": "ko"}
}

# (기존 파싱 및 실행 로직 동일...)
try:
    with open('last_posts.json', 'r', encoding='utf-8') as f:
        last_posts = json.load(f)
except:
    last_posts = {}

new_posts_found = False

for blog_name, info in FEEDS.items():
    try:
        response = requests.get(info["url"], timeout=15, verify=False)
        soup = BeautifulSoup(response.content, 'xml')
        latest_item = soup.find('item') or soup.find('entry')
        
        if not latest_item: continue
        
        title = latest_item.title.text.strip()
        link = (latest_item.link.text.strip() if latest_item.link.text else latest_item.link.get('href'))
        
        if link != last_posts.get(blog_name):
            # 내용 추출
            content_tag = latest_item.find(['content:encoded', 'description', 'summary', 'content'])
            text_content = BeautifulSoup(content_tag.text, "html.parser").get_text()[:2500]
            
            summary = summarize_post(title, text_content, info["lang"])
            if summary:
                if send_line_message(f"🚀 [AI Backend Skill]\n\n{summary}\n\n🔗 {link}"):
                    last_posts[blog_name] = link
                    new_posts_found = True
            time.sleep(5)
    except Exception as e:
        print(f"Error {blog_name}: {e}")

if new_posts_found:
    with open('last_posts.json', 'w', encoding='utf-8') as f:
        json.dump(last_posts, f, ensure_ascii=False, indent=2)
