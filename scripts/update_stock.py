#!/usr/bin/env python3
"""
나장현서 로또집 — 주식 뉴스 자동 수집 스크립트
GitHub Actions가 매일 오전 7:30(KST) 자동 실행
구글 뉴스 RSS로 한국 경제/주식 뉴스 수집 → public/stock_briefing.json 저장
"""
import requests, json, re, os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y년 %m월 %d일")
TODAY_SHORT = datetime.now(KST).strftime("%Y-%m-%d")
UPDATED_AT = datetime.now(KST).strftime("%Y-%m-%d %H:%M")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# ── 태그/임팩트 자동 분류 ──────────────────────────────────────────────────
TAG_RULES = [
    (["미국", "美", "연준", "Fed", "나스닥", "다우", "S&P", "중국", "中", "일본", "유럽", "달러", "환율"], "글로벌"),
    (["삼성", "SK하이닉스", "현대차", "LG", "카카오", "네이버", "기업", "실적", "수주", "공시", "상장"], "기업"),
    (["한국은행", "금리", "기준금리", "정부", "규제", "법안", "정책", "예산", "세금"], "정책"),
    (["코스피", "코스닥", "증시", "선물", "외국인", "매수", "매도", "시장", "주가", "주식"], "시장"),
    (["물가", "CPI", "PCE", "GDP", "경기", "고용", "수출", "무역", "경제"], "경제"),
]

IMPACT_RULES = [
    (["상승", "급등", "호재", "수주", "흑자", "성장", "돌파", "최고", "강세", "반등", "상향", "증가", "개선"], "호재"),
    (["하락", "급락", "악재", "적자", "위기", "우려", "리스크", "둔화", "약세", "하향", "감소", "부진"], "리스크"),
]

def classify(title):
    tag = "시장"
    for keywords, t in TAG_RULES:
        if any(k in title for k in keywords):
            tag = t
            break
    impact = "중립"
    for keywords, i in IMPACT_RULES:
        if any(k in title for k in keywords):
            impact = i
            break
    return tag, impact

def clean_title(title):
    """HTML 엔티티 제거 및 정리"""
    title = re.sub(r'<[^>]+>', '', title)
    title = title.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
    title = re.sub(r'\s+', ' ', title).strip()
    return title

# ── 구글 뉴스 RSS 수집 ────────────────────────────────────────────────────
RSS_QUERIES = [
    ("코스피 코스닥 주식", "https://news.google.com/rss/search?q=%EC%BD%94%EC%8A%A4%ED%94%BC+%EC%BD%94%EC%8A%A4%EB%8B%A5+%EC%A3%BC%EC%8B%9D&hl=ko&gl=KR&ceid=KR:ko"),
    ("한국 경제 금리 환율", "https://news.google.com/rss/search?q=%ED%95%9C%EA%B5%AD+%EA%B2%BD%EC%A0%9C+%EA%B8%88%EB%A6%AC&hl=ko&gl=KR&ceid=KR:ko"),
    ("삼성전자 SK하이닉스 현대차", "https://news.google.com/rss/search?q=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90+SK%ED%95%98%EC%9D%B4%EB%8B%89%EC%8A%A4&hl=ko&gl=KR&ceid=KR:ko"),
]

def fetch_google_news():
    news_items = []
    seen_titles = set()
    now_str = datetime.now(KST).strftime("%H:%M")

    for query_name, url in RSS_QUERIES:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                print(f"  {query_name}: {r.status_code} 실패")
                continue

            root = ET.fromstring(r.content)
            items = root.findall(".//item")
            count = 0

            for item in items[:6]:
                raw_title = item.findtext("title", "").strip()
                title = clean_title(raw_title)
                link = item.findtext("link", "").strip()

                # 출처 추출 (구글 뉴스 형식: "제목 - 언론사")
                source = "구글뉴스"
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    title = parts[0].strip()
                    source = parts[1].strip()

                if len(title) < 8 or title in seen_titles:
                    continue

                seen_titles.add(title)
                tag, impact = classify(title)
                news_items.append({
                    "time": now_str,
                    "title": title,
                    "source": source,
                    "tag": tag,
                    "impact": impact,
                    "link": link,
                })
                count += 1
                if count >= 4:
                    break

            print(f"  {query_name}: {count}건 수집")
        except Exception as e:
            print(f"  {query_name} 실패: {e}")

    # 최대 10건
    result = news_items[:10]
    print(f"  총 {len(result)}건 수집 완료")
    return result

# ── JSON 저장 ─────────────────────────────────────────────────────────────
def save_briefing(news_items):
    os.makedirs("public", exist_ok=True)

    counts = {"호재": 0, "리스크": 0, "중립": 0}
    for n in news_items:
        counts[n.get("impact", "중립")] += 1

    auto_summary = (
        f"{TODAY} 주요 경제 뉴스 {len(news_items)}건. "
        f"호재 {counts['호재']} · 리스크 {counts['리스크']} · 중립 {counts['중립']}"
    )

    output = {
        "updatedAt": UPDATED_AT,
        "date": TODAY_SHORT,
        "autoSummary": auto_summary,
        "news": news_items,
        "aiSummary": None,
    }

    with open("public/stock_briefing.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  저장 완료 ({TODAY_SHORT}, {len(news_items)}건)")

# ── 메인 ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n=== 주식 뉴스 수집 ({TODAY}) ===")
    print("뉴스 수집 중 (구글 뉴스 RSS)...")
    news = fetch_google_news()
    print("JSON 저장 중...")
    save_briefing(news)
    print("=== 완료 ===\n")
