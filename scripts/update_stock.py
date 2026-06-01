#!/usr/bin/env python3
"""
나장현서 로또집 — 주식 브리핑 자동 업데이트 스크립트
GitHub Actions가 매일 오전 7:30(KST) 자동 실행
1. 네이버 금융 RSS에서 오늘 뉴스 수집
2. Claude API로 AI 요약 생성
3. public/stock_briefing.json 저장
"""
import requests, json, re, os, sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y년 %m월 %d일")
TODAY_SHORT = datetime.now(KST).strftime("%Y-%m-%d")
UPDATED_AT = datetime.now(KST).strftime("%Y-%m-%d %H:%M")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── 1. 네이버 금융 뉴스 RSS 수집 ──────────────────────────────────────────────
RSS_FEEDS = [
    ("https://finance.naver.com/news/news_list.naver?mode=LSS2D&section_id=101&section_id2=258", "증권"),
    ("https://finance.naver.com/news/news_list.naver?mode=LSS2D&section_id=101&section_id2=259", "시장"),
    ("https://finance.naver.com/news/news_list.naver?mode=LSS2D&section_id=101&section_id2=261", "경제"),
]

NAVER_RSS_URLS = [
    "https://finance.naver.com/news/news_list.naver?mode=MAINNEWS&section_id=101",
]

def fetch_naver_news():
    """네이버 금융 메인 뉴스 크롤링 (RSS 대체)"""
    news_items = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }
    try:
        # 네이버 금융 뉴스 페이지에서 헤드라인 파싱
        url = "https://finance.naver.com/news/mainnews.naver"
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = "euc-kr"
        text = r.text

        # 뉴스 제목 파싱 (dl dt 형태)
        titles = re.findall(r'<dt[^>]*>\s*<a[^>]*>([^<]+)</a>', text)
        sources = re.findall(r'<dd class="article_source"[^>]*>([^<]+)</dd>', text)

        for i, title in enumerate(titles[:10]):
            title = title.strip()
            if len(title) < 10:
                continue
            source = sources[i].strip() if i < len(sources) else "네이버금융"
            news_items.append({
                "title": title,
                "source": source,
            })
    except Exception as e:
        print(f"  뉴스 수집 실패: {e}")

    # 수집 실패시 기본 뉴스 (워크플로우가 멈추지 않게)
    if not news_items:
        news_items = [
            {"title": f"{TODAY} 국내 증시 개장 예정", "source": "자동생성"},
            {"title": "코스피·코스닥 장전 동향 분석", "source": "자동생성"},
        ]

    print(f"  뉴스 {len(news_items)}건 수집 완료")
    return news_items


# ── 2. Claude API로 AI 요약 생성 ─────────────────────────────────────────────
def generate_briefing(news_items):
    if not ANTHROPIC_API_KEY:
        print("  ANTHROPIC_API_KEY 없음 — 스킵")
        return None

    news_text = "\n".join([f"- {n['title']} ({n['source']})" for n in news_items])

    prompt = f"""오늘({TODAY}) 한국 주식시장 아침 브리핑을 작성해주세요.

오늘 수집된 뉴스:
{news_text}

위 뉴스를 바탕으로 아래 JSON 형식으로만 응답해주세요. 마크다운 코드블록(```) 없이 순수 JSON만:
{{
  "summary": "오늘 시장 핵심 흐름 2-3문장",
  "kospi": {{"outlook": "상승/보합/하락", "reason": "한 줄 이유"}},
  "kosdaq": {{"outlook": "상승/보합/하락", "reason": "한 줄 이유"}},
  "keyStocks": [
    {{"name": "종목명", "code": "종목코드", "signal": "매수관심/중립/주의", "reason": "한 줄 이유"}}
  ],
  "keywords": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5"],
  "riskFactors": "오늘 주목할 리스크 한 줄"
}}
keyStocks는 3개. 뉴스 내용 기반으로 작성."""

    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "system": "당신은 한국 주식시장 전문 애널리스트입니다. 수집된 뉴스를 바탕으로 정확하고 실용적인 아침 브리핑을 작성합니다. JSON만 반환하세요.",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        data = res.json()
        raw = data["content"][0]["text"]
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(cleaned)
        print("  AI 요약 생성 완료")
        return parsed
    except Exception as e:
        print(f"  Claude API 실패: {e}")
        return None


# ── 3. JSON 파일 저장 ─────────────────────────────────────────────────────────
def save_briefing(news_items, ai_summary):
    os.makedirs("public", exist_ok=True)

    output = {
        "updatedAt": UPDATED_AT,
        "date": TODAY_SHORT,
        "news": [
            {
                "time": datetime.now(KST).strftime("%H:%M"),
                "title": n["title"],
                "source": n["source"],
                "tag": "시장",
                "impact": "중립",
            }
            for n in news_items
        ],
        "aiSummary": ai_summary,
    }

    with open("public/stock_briefing.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  public/stock_briefing.json 저장 완료")
    print(f"  날짜: {TODAY_SHORT}, 뉴스: {len(news_items)}건, AI요약: {'있음' if ai_summary else '없음'}")


# ── 메인 ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n=== 주식 브리핑 업데이트 시작 ({TODAY}) ===")
    print("1. 뉴스 수집 중...")
    news = fetch_naver_news()
    print("2. AI 요약 생성 중...")
    summary = generate_briefing(news)
    print("3. JSON 저장 중...")
    save_briefing(news, summary)
    print("=== 완료 ===\n")
