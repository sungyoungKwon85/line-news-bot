import requests
from bs4 import BeautifulSoup
import os

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
    res = requests.post(url, headers=headers, json=payload)
    return res.status_code

rss_url = "https://toss.tech/rss.xml"
response = requests.get(rss_url)
soup = BeautifulSoup(response.content, 'xml')

latest_item = soup.find('item')
title = latest_item.title.text
link = latest_item.link.text

try:
    with open('last_post.txt', 'r') as f:
        last_link = f.read().strip()
except FileNotFoundError:
    last_link = ""

if link != last_link:
    message = f"📢 토스 기술 블로그 새 글!\n\n[{title}]\n{link}"
    status = send_line_message(message)
    
    # HTTP 200(성공)일 때만 파일을 업데이트하도록 로직 보강
    if status == 200:
        with open('last_post.txt', 'w') as f:
            f.write(link)
        print("라인 전송 성공 (200) 및 기록 업데이트 완료!")
    else:
        print(f"라인 전송 실패! 응답 코드: {status}. 기록을 업데이트하지 않습니다.")
else:
    print("새로운 글이 없습니다.")
