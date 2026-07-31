import argparse
import json
import math
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
IMPORTANCE_THRESHOLD = 7
HISTORY_DAYS = 7

FX_TICKERS = (
    ("USD/KRW", "KRW=X"),
    ("EUR/KRW", "EURKRW=X"),
    ("GBP/KRW", "GBPKRW=X"),
)

CATEGORY_ORDER = ("WORLD_ECONOMY", "GLOBAL_CORE", "KOREA_IMPACT")
CATEGORY_LABELS = {
    "WORLD_ECONOMY": "세계경제",
    "GLOBAL_CORE": "글로벌",
    "KOREA_IMPACT": "한국",
}

PRIMARY_SOURCE_DOMAINS = {
    "bankofengland.co.uk",
    "bea.gov",
    "bis.org",
    "bls.gov",
    "bok.or.kr",
    "bundesbank.de",
    "ecb.europa.eu",
    "ec.europa.eu",
    "europa.eu",
    "federalreserve.gov",
    "fsc.go.kr",
    "iea.org",
    "imf.org",
    "korea.kr",
    "kostat.go.kr",
    "moef.go.kr",
    "mofa.go.kr",
    "motie.go.kr",
    "nasa.gov",
    "nato.int",
    "noaa.gov",
    "oecd.org",
    "president.go.kr",
    "treasury.gov",
    "un.org",
    "who.int",
    "worldbank.org",
    "wto.org",
}

TRUSTED_MEDIA_DOMAINS = {
    "aljazeera.com",
    "apnews.com",
    "bbc.co.uk",
    "bbc.com",
    "bloomberg.com",
    "cnbc.com",
    "dw.com",
    "economist.com",
    "ft.com",
    "france24.com",
    "hankyung.com",
    "kbs.co.kr",
    "mbc.co.kr",
    "mk.co.kr",
    "nytimes.com",
    "reuters.com",
    "sbs.co.kr",
    "theguardian.com",
    "wsj.com",
    "yna.co.kr",
}


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def truncate(value, limit):
    value = clean_text(value)
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def fetch_exchange_rates(ticker_factory=None):
    if ticker_factory is None:
        import yfinance as yf

        ticker_factory = yf.Ticker

    rates = []
    for label, ticker in FX_TICKERS:
        value = None
        change_pct = None
        try:
            history = ticker_factory(ticker).history(
                period="5d",
                auto_adjust=False,
            )
            series = history["Close"]
            if hasattr(series, "dropna"):
                series = series.dropna()

            closes = []
            for raw_value in series:
                number = float(raw_value)
                if math.isfinite(number):
                    closes.append(number)

            if closes:
                value = closes[-1]
            if len(closes) >= 2 and closes[-2] != 0:
                change_pct = (closes[-1] / closes[-2] - 1) * 100
        except Exception as exc:
            print(f"{label} 환율 조회 실패: {exc}")

        rates.append(
            {
                "label": label,
                "ticker": ticker,
                "value": value,
                "change_pct": change_pct,
            }
        )
    return rates


def format_percent(value):
    if value is None:
        return "N/A"
    return f"{value:+.1f}%"


def format_fx_line(rates):
    parts = []
    for rate in rates:
        if rate["value"] is None:
            parts.append(f"{rate['label']} N/A")
            continue
        parts.append(
            f"{rate['label']} {rate['value']:,.1f}원 "
            f"({format_percent(rate['change_pct'])})"
        )
    return "💱 " + " · ".join(parts)


def history_path():
    return Path(os.environ.get("NEWS_HISTORY_PATH", "news_history.json"))


def load_news_history(path, now):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload.get("items", [])
    except (FileNotFoundError, json.JSONDecodeError, OSError, AttributeError):
        return []

    cutoff = now.date() - timedelta(days=HISTORY_DAYS)
    recent = []
    for item in items:
        try:
            item_date = datetime.fromisoformat(item["date"]).date()
        except (KeyError, TypeError, ValueError):
            continue
        if item_date >= cutoff and item.get("title"):
            recent.append(item)
    return recent[-30:]


def save_news_history(path, old_items, news_items, now):
    combined = list(old_items)
    for item in news_items:
        combined.append(
            {
                "date": now.date().isoformat(),
                "title": item["title"],
                "url": item["source_url"],
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"items": combined[-30:]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_news_prompt(now, previous_titles):
    cutoff = now - timedelta(hours=24)
    previous = "\n".join(f"- {title}" for title in previous_titles)
    if not previous:
        previous = "- 없음"

    return f"""
현재 시각은 {now.isoformat()}이고, 한국 표준시(KST) 기준이다.
반드시 Google Search를 사용해 {cutoff.isoformat()} 이후 공개되거나 중대한
진전이 생긴 뉴스를 확인하라.

아래 세 분야에서 기준을 넘는 뉴스만 분야별 최대 1건 고른다.
1. WORLD_ECONOMY: 중앙은행, 물가, 고용, 무역, 에너지 등 세계 경제
2. GLOBAL_CORE: 국제정세, 정책, 기술/AI, 과학, 에너지/기후 중 파급력이 가장 큰 이슈
3. KOREA_IMPACT: 한국 경제생활에 직접 영향이 큰 국내외 뉴스

출처 규칙:
- 중앙은행, 통계기관, 정부, 국제기구 등 1차 출처를 우선한다.
- 보도는 Reuters, AP, BBC, Bloomberg, FT, 연합뉴스 등 주요 언론만 사용한다.
- 블로그, SNS, 사설, 전망성 기사, 연예, 스포츠, 단순 사건, 개별 종목 등락은 제외한다.
- 공식 1차 출처 또는 신뢰할 수 있는 주요 언론 1개 이상으로 확인한다.
- 각 SUMMARY, ITEM, EVENT 줄의 사실에 검색 citation이 직접 연결되게 작성한다.

중요도 점수:
- reach: 영향 범위 0~3
- persistence: 영향 지속성 0~2
- korea: 한국의 환율/금리/물가/고용/무역 영향 0~3
- corroboration: 공식 출처나 독립 언론 2곳이면 2, 주요 언론 1곳이면 1
- 합계 7점 미만은 출력하지 않는다.

반복 방지:
아래 최근 제목과 같은 사건은 제외하되, 새로운 정책 결정이나 수치 발표처럼
중대한 진전이 있으면 포함할 수 있다.
{previous}

오늘 KST 기준 예정된 고중요도 경제 일정도 최대 2개 찾는다.
일정은 중앙은행, 정부, 통계기관 등 공식 출처로만 확인한다.

한국어로 작성하고, 각 필드 안에는 | 문자를 쓰지 않는다.
마크다운과 설명 없이 아래 줄 형식만 출력한다.

SUMMARY|전체 흐름을 요약한 한 문장
ITEM|분야 코드|사건 발생 또는 중대한 진전 시각 ISO 8601|reach|persistence|korea|corroboration|제목|왜 중요한지와 한국 경제생활 영향을 합친 한 문장
EVENT|KST 기준 YYYY-MM-DD|HH:MM 또는 미정|일정 이름

기준을 넘는 ITEM이나 EVENT가 없으면 해당 줄은 생략한다.
""".strip()


def get_field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def utf8_byte_offset_to_char_index(text, byte_offset):
    encoded = text.encode("utf-8")
    bounded = max(0, min(int(byte_offset), len(encoded)))
    return len(encoded[:bounded].decode("utf-8", errors="ignore"))


def extract_grounded_text(interaction):
    pieces = []
    citations = []
    offset = 0

    def add_text_block(block):
        nonlocal offset
        text = get_field(block, "text")
        if not text:
            return
        if pieces:
            pieces.append("\n")
            offset += 1
        block_start = offset
        pieces.append(text)
        offset += len(text)

        for annotation in get_field(block, "annotations", []) or []:
            if get_field(annotation, "type") != "url_citation":
                continue
            url = get_field(annotation, "url")
            start = get_field(annotation, "start_index")
            end = get_field(annotation, "end_index")
            if not url or start is None or end is None:
                continue
            citations.append(
                {
                    "url": url,
                    "title": clean_text(get_field(annotation, "title", "")),
                    "start": block_start
                    + utf8_byte_offset_to_char_index(text, start),
                    "end": block_start
                    + utf8_byte_offset_to_char_index(text, end),
                }
            )

    for step in get_field(interaction, "steps", []) or []:
        if get_field(step, "type") != "model_output":
            continue
        for block in get_field(step, "content", []) or []:
            if get_field(block, "type") == "text":
                add_text_block(block)

    if not pieces:
        for output in get_field(interaction, "outputs", []) or []:
            if get_field(output, "type") == "text":
                add_text_block(output)

    if not pieces:
        return str(get_field(interaction, "output_text", "") or "").strip(), []
    return "".join(pieces), citations


def citations_for_span(citations, start, end):
    selected = []
    seen = set()
    for citation in citations:
        if citation["end"] <= start or citation["start"] >= end:
            continue
        if citation["url"] in seen:
            continue
        seen.add(citation["url"])
        selected.append(citation)
    return selected


def parse_iso_datetime(value):
    value = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timezone is required")
    return parsed.astimezone(KST)


def parse_grounded_response(interaction):
    text, citations = extract_grounded_text(interaction)
    summary = {"text": "", "citations": []}
    news = []
    events = []

    for match in re.finditer(r"[^\r\n]+", text):
        raw_line = match.group(0)
        line = raw_line.strip()
        if not line:
            continue
        start = match.start() + len(raw_line) - len(raw_line.lstrip())
        end = start + len(line)
        line_citations = citations_for_span(citations, start, end)

        if line.startswith("SUMMARY|"):
            summary = {
                "text": clean_text(line.split("|", 1)[1]),
                "citations": line_citations,
            }
            continue

        if line.startswith("ITEM|"):
            parts = line.split("|", 8)
            if len(parts) != 9:
                continue
            try:
                news.append(
                    {
                        "category": parts[1],
                        "occurred_at": parse_iso_datetime(parts[2]),
                        "reach": int(parts[3]),
                        "persistence": int(parts[4]),
                        "korea": int(parts[5]),
                        "reported_corroboration": int(parts[6]),
                        "title": clean_text(parts[7]),
                        "impact": clean_text(parts[8]),
                        "citations": line_citations,
                    }
                )
            except (TypeError, ValueError):
                continue
            continue

        if line.startswith("EVENT|"):
            parts = line.split("|", 3)
            if len(parts) != 4:
                continue
            try:
                event_date = datetime.fromisoformat(parts[1]).date()
            except ValueError:
                continue
            events.append(
                {
                    "date": event_date,
                    "time": clean_text(parts[2]),
                    "title": clean_text(parts[3]),
                    "citations": line_citations,
                }
            )

    return summary, news, events


def matches_domain(host, allowed_domain):
    return host == allowed_domain or host.endswith("." + allowed_domain)


def source_kind(url):
    try:
        parsed = urlparse(url)
    except ValueError:
        return None, None, None
    if parsed.scheme != "https" or not parsed.hostname or len(url) > 1000:
        return None, None, None

    host = parsed.hostname.lower().rstrip(".")
    for domain in PRIMARY_SOURCE_DOMAINS:
        if matches_domain(host, domain):
            return "primary", host, domain
    for domain in TRUSTED_MEDIA_DOMAINS:
        if matches_domain(host, domain):
            publisher = "bbc" if domain in {"bbc.com", "bbc.co.uk"} else domain
            return "media", host, publisher
    return None, host, None


def normalize_title(title):
    return re.sub(r"[^0-9a-z가-힣]+", "", clean_text(title).lower())


def titles_are_similar(left, right):
    left = normalize_title(left)
    right = normalize_title(right)
    return bool(left and right and left == right)


def is_history_repeat(item, history):
    for previous in history:
        if item["source_url"] == previous.get("url"):
            return True
        if titles_are_similar(item["title"], previous.get("title", "")):
            return True
    return False


def verified_sources(citations):
    verified = []
    seen_publishers = set()
    for citation in citations:
        kind, host, publisher = source_kind(citation["url"])
        if not kind or publisher in seen_publishers:
            continue
        seen_publishers.add(publisher)
        verified.append(
            {
                **citation,
                "kind": kind,
                "host": host,
                "publisher": publisher,
            }
        )
    return verified


def validate_and_select_news(raw_news, now, history):
    cutoff = now - timedelta(hours=24)
    candidates = []

    for item in raw_news:
        if item["category"] not in CATEGORY_ORDER:
            continue
        if not (0 <= item["reach"] <= 3):
            continue
        if not (0 <= item["persistence"] <= 2):
            continue
        if not (0 <= item["korea"] <= 3):
            continue
        if not (0 <= item["reported_corroboration"] <= 2):
            continue
        if not (cutoff <= item["occurred_at"] <= now + timedelta(minutes=15)):
            continue
        if not item["title"] or not item["impact"]:
            continue

        sources = verified_sources(item["citations"])
        if not sources:
            continue
        has_primary = any(source["kind"] == "primary" for source in sources)
        media_publishers = {
            source["publisher"]
            for source in sources
            if source["kind"] == "media"
        }
        if not has_primary and not media_publishers:
            continue

        source_corroboration = (
            2 if has_primary or len(media_publishers) >= 2 else 1
        )
        corroboration = min(
            item["reported_corroboration"],
            source_corroboration,
        )
        importance = (
            item["reach"]
            + item["persistence"]
            + item["korea"]
            + corroboration
        )
        if importance < IMPORTANCE_THRESHOLD:
            continue
        if item["category"] == "KOREA_IMPACT" and item["korea"] < 2:
            continue

        candidate = {
            **item,
            "title": truncate(item["title"], 58),
            "impact": truncate(item["impact"], 100),
            "importance": importance,
            "source_url": sources[0]["url"],
            "source_host": sources[0]["host"].removeprefix("www."),
            "sources": sources,
        }
        if is_history_repeat(candidate, history):
            continue
        candidates.append(candidate)

    selected = []
    used_urls = set()
    for category in CATEGORY_ORDER:
        category_items = [
            item for item in candidates if item["category"] == category
        ]
        category_items.sort(
            key=lambda item: (item["importance"], item["occurred_at"]),
            reverse=True,
        )
        for item in category_items:
            if item["source_url"] in used_urls:
                continue
            if any(
                titles_are_similar(item["title"], chosen["title"])
                for chosen in selected
            ):
                continue
            selected.append(item)
            used_urls.add(item["source_url"])
            break
    return selected


def validate_events(raw_events, now):
    selected = []
    seen_titles = set()
    for event in raw_events:
        if event["date"] != now.astimezone(KST).date():
            continue
        if event["time"] != "미정" and not re.fullmatch(
            r"(?:[01]\d|2[0-3]):[0-5]\d",
            event["time"],
        ):
            continue
        sources = verified_sources(event["citations"])
        official = next(
            (source for source in sources if source["kind"] == "primary"),
            None,
        )
        title_key = normalize_title(event["title"])
        if not official or not title_key or title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        selected.append(
            {
                "time": event["time"],
                "title": truncate(event["title"], 55),
                "source_url": official["url"],
                "source_host": official["host"].removeprefix("www."),
            }
        )
        if len(selected) == 2:
            break
    return selected


def validate_summary(raw_summary, news):
    if not raw_summary["text"] or not news:
        return ""
    sources = verified_sources(raw_summary["citations"])
    selected_urls = {
        source["url"]
        for item in news
        for source in item["sources"]
    }
    if not sources or any(
        source["url"] not in selected_urls for source in sources
    ):
        return ""
    return truncate(raw_summary["text"], 78)


def fetch_grounded_news(client, now, previous_titles):
    prompt = build_news_prompt(now, previous_titles)
    interaction = client.interactions.create(
        model=os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        input=prompt,
        tools=[{"type": "google_search"}],
        store=False,
    )
    parsed = parse_grounded_response(interaction)
    if not parsed[0]["text"]:
        raise RuntimeError("Gemini 뉴스 응답 형식을 확인할 수 없습니다.")
    return parsed


def create_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다.")

    from google import genai

    return genai.Client(api_key=api_key)


def build_briefing(
    now=None,
    ticker_factory=None,
    gemini_client=None,
    state_path=None,
):
    now = now or datetime.now(KST)
    state_path = state_path or history_path()
    history = load_news_history(state_path, now)
    rates = fetch_exchange_rates(ticker_factory)

    summary = ""
    news = []
    events = []
    news_error = None
    try:
        client = gemini_client or create_gemini_client()
        raw_summary, raw_news, raw_events = fetch_grounded_news(
            client,
            now,
            [item["title"] for item in history],
        )
        news = validate_and_select_news(raw_news, now, history)
        events = validate_events(raw_events, now)
        summary = validate_summary(raw_summary, news)
        print(
            f"뉴스 후보 {len(raw_news)}건 / 검증 통과 {len(news)}건, "
            f"일정 후보 {len(raw_events)}건 / 검증 통과 {len(events)}건"
        )
    except Exception as exc:
        news_error = str(exc)
        print(f"뉴스 조회 실패: {exc}")

    return {
        "now": now,
        "rates": rates,
        "summary": summary,
        "news": news,
        "events": events,
        "news_error": news_error,
        "history": history,
        "state_path": state_path,
    }


def render_text(briefing):
    now = briefing["now"]
    lines = [
        f"🌍 {now.month}/{now.day} 아침 브리핑",
        format_fx_line(briefing["rates"]),
    ]

    if briefing["news"]:
        if briefing["summary"]:
            lines.append(f"한줄: {briefing['summary']}")
        for index, item in enumerate(briefing["news"], start=1):
            label = CATEGORY_LABELS[item["category"]]
            lines.append(f"{index}. [{label}] {item['title']}")
            lines.append(f"   ↳ {item['impact']}")
    elif briefing["news_error"]:
        lines.append("📰 주요 뉴스를 불러오지 못했습니다.")
    else:
        lines.append("📰 오늘은 기준을 넘는 핵심 뉴스가 없습니다.")

    if briefing["events"]:
        event_text = " · ".join(
            f"{item['time']} {item['title']}" for item in briefing["events"]
        )
        lines.append(f"📅 오늘: {event_text}")
    else:
        lines.append("📅 오늘: 주요 경제 일정 없음")

    return "\n".join(lines)


def flex_text(text, **kwargs):
    component = {
        "type": "text",
        "text": text,
        "wrap": True,
    }
    component.update(kwargs)
    return component


def build_line_message(briefing):
    now = briefing["now"]
    contents = [
        flex_text(
            f"🌍 {now.month}/{now.day} 아침 브리핑",
            weight="bold",
            size="lg",
        ),
        flex_text(
            format_fx_line(briefing["rates"]),
            size="sm",
            color="#555555",
            margin="sm",
        ),
    ]

    if briefing["news"]:
        if briefing["summary"]:
            contents.append(
                flex_text(
                    f"한줄: {briefing['summary']}",
                    weight="bold",
                    size="sm",
                    margin="md",
                )
            )
        contents.append(
            {"type": "separator", "margin": "md", "color": "#DDDDDD"}
        )
        for index, item in enumerate(briefing["news"], start=1):
            label = CATEGORY_LABELS[item["category"]]
            contents.append(
                flex_text(
                    f"{index}. [{label}] {item['title']} ↗",
                    weight="bold",
                    size="sm",
                    color="#1769AA",
                    margin="md",
                    action={
                        "type": "uri",
                        "label": "원문 보기",
                        "uri": item["source_url"],
                    },
                )
            )
            contents.append(
                flex_text(
                    f"{item['impact']} · {item['source_host']}",
                    size="xs",
                    color="#555555",
                    margin="xs",
                )
            )
    else:
        status = (
            "📰 주요 뉴스를 불러오지 못했습니다."
            if briefing["news_error"]
            else "📰 오늘은 기준을 넘는 핵심 뉴스가 없습니다."
        )
        contents.append(flex_text(status, size="sm", margin="md"))

    if briefing["events"]:
        event_text = " · ".join(
            f"{item['time']} {item['title']}" for item in briefing["events"]
        )
        schedule = f"📅 오늘: {event_text}"
    else:
        schedule = "📅 오늘: 주요 경제 일정 없음"
    contents.append(flex_text(schedule, size="xs", margin="md"))

    return {
        "type": "flex",
        "altText": truncate(render_text(briefing), 1500),
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": contents,
            },
        },
    }


def send_line_message(message, token, user_id, post=None):
    if post is None:
        import requests

        post = requests.post

    response = post(
        LINE_PUSH_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        json={"to": user_id, "messages": [message]},
        timeout=20,
    )
    response.raise_for_status()


def main(argv=None):
    parser = argparse.ArgumentParser(description="LINE daily morning briefing")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print the briefing without sending it to LINE.",
    )
    args = parser.parse_args(argv)

    token = os.environ.get("LINE_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not args.dry_run and (not token or not user_id):
        raise RuntimeError("LINE_TOKEN and LINE_USER_ID must be set.")

    briefing = build_briefing()
    if args.dry_run:
        print(render_text(briefing))
        return

    send_line_message(build_line_message(briefing), token, user_id)
    if briefing["news"]:
        save_news_history(
            briefing["state_path"],
            briefing["history"],
            briefing["news"],
            briefing["now"],
        )
    print("아침 브리핑 전송 완료!")


if __name__ == "__main__":
    main()
