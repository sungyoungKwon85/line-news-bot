import requests
from bs4 import BeautifulSoup
import os

# 1. 깃허브 시크릿에 등록한 라인 정보 가져오기
LINE_TOKEN = os.environ.get('LINE_TOKEN')
LINE_USER_ID = os.environ.get('LINE_USER_ID')

def send_line_message(text):
    # 라인 Messaging API 규격에 맞춰 메시지 전송
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
    print(f"라인 전송 응답 코드: {res.status_code}")

# 2. 토스 기술 블로그 RSS 가져오기
rss_url = "https://toss.tech/rss.xml"
response = requests.get(rss_url)
soup = BeautifulSoup(response.content, 'xml')

# 가장 최신 글 하나 추출
latest_item = soup.find('item')
title = latest_item.title.text
link = latest_item.link.text

# 3. 중복 전송 방지를 위해 이전 기록(last_post.txt) 읽기
try:
    with open('last_post.txt', 'r') as f:
        last_link = f.read().strip()
except FileNotFoundError:
    last_link = ""

# 4. 새로운 글이면 라인으로 보내고 기록 업데이트
if link != last_link:
    message = f"📢 토스 기술 블로그 새 글!\n\n[{title}]\n{link}"
    send_line_message(message)
    
    # 다음 실행 때 비교하기 위해 방금 보낸 글 링크를 파일에 덮어쓰기
    with open('last_post.txt', 'w') as f:
        f.write(link)
    print("새 글 전송 성공 및 기록 업데이트 완료!")
else:
    print("새로운 글이 없습니다.")
