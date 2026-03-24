import requests
from bs4 import BeautifulSoup
import os
import json

LINE_TOKEN = os.environ.get('LINE_TOKEN')
LINE_USER_ID = os.environ.get('LINE_USER_ID')

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
    requests.post(url, headers=headers, json=payload)

# 백엔드, Java/Spring, 대용량 아키텍처 관련 고품질 기술 블로그 10선
FEEDS = {
    "토스": "https://toss.tech/rss.xml",
    "우아한형제들(배민)": "https://techblog.woowahan.com/feed/",
    "라인(LINE)": "https://engineering.linecorp.com/ko/feed/",
    "당근마켓": "https://medium.com/feed/daangn",
    "카카오페이": "https://tech.kakaopay.com/rss.xml",
    "컬리(Kurly)": "https://helloworld.kurly.com/feed",
    "왓챠(Watcha)": "https://medium.com/feed/watcha",
    "야놀자": "https://medium.com/feed/yanolja",
    "쏘카(Socar)": "https://tech.socarcorp.kr/feed",
    "데브시스터즈": "https://tech.devsisters.com/rss.xml"
}

# 각 블로그별 마지막 글 링크를 기억할 JSON 파일 읽기
try:
    with open('last_posts.json', 'r', encoding='utf-8') as f:
        last_posts = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    last_posts = {}

new_posts_found = False

for blog_name, rss_url in FEEDS.items():
    try:
        response = requests.get(rss_url, timeout=10)
        soup = BeautifulSoup(response.content, 'xml')
        
        # 블로그마다 RSS 표준이 다르므로 item 또는 entry 태그를 찾음
        latest_item = soup.find('item') or soup.find('entry')
        if not latest_item:
            continue
        
        title = latest_item.title.text.strip()
        
        # 링크 추출 방식 예외 처리
        link_tag = latest_item.link
        if link_tag:
            link = link_tag.text.strip() if link_tag.text.strip() else link_tag.get('href', '')
        else:
            continue
            
        last_link = last_posts.get(blog_name, "")
        
        # 새로운 글이 올라왔다면?
        if link and link != last_link:
            message = f"📢 {blog_name} 기술 블로그 새 글!\n\n[{title}]\n{link}"
            send_line_message(message)
            last_posts[blog_name] = link
            new_posts_found = True
            
    except Exception as e:
        print(f"{blog_name} 파싱 에러: {e}")

# 변경사항이 있으면 JSON 파일에 덮어쓰기
if new_posts_found:
    with open('last_posts.json', 'w', encoding='utf-8') as f:
        json.dump(last_posts, f, ensure_ascii=False, indent=2)
    print("새 글 전송 및 기록 업데이트 완료!")
else:
    print("새로운 글이 없습니다.")
