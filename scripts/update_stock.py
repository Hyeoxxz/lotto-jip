#!/usr/bin/env python3
"""
나장현서 로또집 — 주식 뉴스 자동 수집 스크립트
GitHub Actions가 매일 오전 7:30(KST) 자동 실행
네이버 금융 뉴스를 수집해서 public/stock_briefing.json 저장
API 키 불필요 — 완전 무료
"""
import requests, json, re, os
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y년 %m월 %d일")
TODAY_SHORT = datetime.now(KST).strftime("%Y-%m-%d")
UPDATED_AT = datetime.now(KST).strftime("%Y-%m-%d %H:%M")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

TAG_RULES = [
    (["미국","美","연준","Fed","나스닥","다우","S&P","중국","中","일본","유럽"], "글로벌"),
    (["삼성","SK하이닉스","현대차","LG","카카오","네이버","기업","실적","수주","공시"], "기업"),
    (["한국은행","금리","기준금리","정부","규제","법안","정책"], "정책"),
    (["코스피","코스닥","증시","선물","외국인","매수","매도","시장"], "시장"),
    (["물가","CPI","PCE","GDP","경기","고용","수출","무역"], "경제"),
]

IMPACT_RULES = [
    (["상승","급등","호재","수주","흑자","성장","돌파","최고","강세","반등"], "호재"),
    (["하락","급락","악재","적자","위기","우려","리스크","둔화","약세","하향"], "리스크"),
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

def fetch_naver_news():
    news_items = []
    try:
        url = "https://finance.naver.com/news/mainnews.naver"
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.encoding = "euc-kr"
        text = r.text
        titles = re.findall(r'<dt[^>]*>\s*<a[^>]*title="([^"]+)"', text)
        if not titles:
            titles = re.findall(r'<dt[^>]*>\s*<a[^>]*>([^<]{10,})</a>', text)
        sources = re.findall(r'class="press"[^>]*>([^<]+)<', text)
        now_str = datetime.now(KST).strftime("%H:%M")
        for i, title in enumerate(titles[:12]):
            title = title.strip()
            if len(title) < 8:
                continue
            source = sources[i].strip() if i < len(sources) else "네이버금융"
            tag, impact = classify(title)
            news_items.append({"time": now_str, "title": title, "source": source, "tag": tag, "impact": impact})
        print(f"  네이버금융 {len(news_items)}건 수집")
    except Exception as e:
        print(f"  네이버금융 실패: {e}")

    if len(news_items) < 5:
        try:
            import xml.etree.ElementTree as ET
            rss_url = "https://www.yonhapnewstv.co.kr/category/news/economy/feed/"
            r = requests.get(rss_url, headers=HEADERS, timeout=10)
            root = ET.fromstring(r.content)
            now_str = datetime.now(KST).strftime("%H:%M")
            for item in root.findall(".//item")[:8]:
                title = item.findtext("title", "").strip()
                if len(title) < 8:
                    continue
                tag, impact = classify(title)
                news_items.append({"time": now_str, "title": title, "source": "연합뉴스TV", "tag": tag, "impact": impact})
            print(f"  연합뉴스 보조 수집 완료")
        except Exception as e:
            print(f"  연합뉴스 실패: {e}")

    return news_items[:10]

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

if __name__ == "__main__":
    print(f"\n=== 주식 뉴스 수집 ({TODAY}) ===")
    news = fetch_naver_news()
    save_briefing(news)
    print("=== 완료 ===\n")
