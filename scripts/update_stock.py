#!/usr/bin/env python3
"""
나장현서 로또집 — 주식 뉴스 자동 수집 스크립트
GitHub Actions가 매일 오전 7:30(KST) 자동 실행
구글 뉴스 RSS로 한국 경제/주식 뉴스 수집 → public/stock_briefing.json 저장
"""
import requests, json, re, os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

HISTORY_PATH = "public/stock_history.json"
HISTORY_MAX = 500          # 누적 보관 최대 건수
RELATED_MIN_SCORE = 0.25   # 이 이상 유사할 때만 "관련 기사"로 인정
RELATED_TOP_K = 2          # 기사당 붙일 관련 과거 기사 개수

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

# ── RAG: 과거 기사 누적 + 유사 기사 검색 ──────────────────────────────────
def load_history():
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(history):
    os.makedirs("public", exist_ok=True)
    # 최근 HISTORY_MAX건만 유지 (파일이 무한히 커지지 않도록)
    trimmed = history[-HISTORY_MAX:]
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)

def attach_related_news(today_items, history):
    """오늘 기사 제목들을 과거 기사 제목들과 TF-IDF 코사인 유사도로 비교해
    각 오늘 기사에 가장 관련 있는 과거 기사를 붙인다."""
    if not history:
        for item in today_items:
            item["relatedNews"] = []
        return today_items

    past_titles = [h["title"] for h in history]
    today_titles = [item["title"] for item in today_items]

    # 형태소 분석기 없이도 한국어 뉴스 제목은 명사구 반복이 많아
    # 글자 단위 n-gram TF-IDF가 단어 단위보다 안정적으로 유사도를 잡아준다
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
    corpus = past_titles + today_titles
    tfidf = vectorizer.fit_transform(corpus)

    past_vecs = tfidf[:len(past_titles)]
    today_vecs = tfidf[len(past_titles):]

    sims = cosine_similarity(today_vecs, past_vecs)  # (오늘건수, 과거건수)

    for i, item in enumerate(today_items):
        scored = sorted(
            ((sims[i][j], j) for j in range(len(history))),
            key=lambda x: x[0],
            reverse=True,
        )
        related = []
        for score, j in scored[:RELATED_TOP_K]:
            if score < RELATED_MIN_SCORE:
                break
            h = history[j]
            related.append({
                "title": h["title"],
                "date": h.get("date", ""),
                "link": h.get("link", ""),
                "score": round(float(score), 3),
            })
        item["relatedNews"] = related

    return today_items

# ── JSON 저장 ─────────────────────────────────────────────────────────────
def build_trend_note(news_items):
    """관련 과거 기사가 붙은 항목들을 모아 '며칠째 이어지는 이슈' 문장을 생성.
    단순 집계(autoSummary)와 달리, 검색된 과거 맥락을 실제로 활용하는 부분."""
    recurring = [n for n in news_items if n.get("relatedNews")]
    if not recurring:
        return None

    # 가장 유사도 높은 항목을 대표 이슈로 선정
    top = max(recurring, key=lambda n: n["relatedNews"][0]["score"])
    related_dates = sorted({r["date"] for r in top["relatedNews"] if r.get("date")})
    span = f"{related_dates[0]}부터" if related_dates else "최근"

    return f"'{top['title']}' 이슈가 {span} 이어지고 있습니다 (관련 과거 기사 {len(top['relatedNews'])}건 확인)."

def save_briefing(news_items):
    os.makedirs("public", exist_ok=True)

    counts = {"호재": 0, "리스크": 0, "중립": 0}
    for n in news_items:
        counts[n.get("impact", "중립")] += 1

    auto_summary = (
        f"{TODAY} 주요 경제 뉴스 {len(news_items)}건. "
        f"호재 {counts['호재']} · 리스크 {counts['리스크']} · 중립 {counts['중립']}"
    )

    trend_note = build_trend_note(news_items)

    output = {
        "updatedAt": UPDATED_AT,
        "date": TODAY_SHORT,
        "autoSummary": auto_summary,
        "trendNote": trend_note,
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

    print("과거 기사 불러오는 중...")
    history = load_history()
    print(f"  누적 기사 {len(history)}건")

    print("관련 과거 기사 검색 중 (TF-IDF 코사인 유사도)...")
    news = attach_related_news(news, history)
    related_count = sum(1 for n in news if n["relatedNews"])
    print(f"  {related_count}/{len(news)}건에 관련 기사 연결")

    print("JSON 저장 중...")
    save_briefing(news)

    for item in news:
        item["date"] = TODAY_SHORT
    save_history(history + news)

    print("=== 완료 ===\n")
