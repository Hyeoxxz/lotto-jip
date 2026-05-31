#!/usr/bin/env python3
"""
나장현서 로또집 — 자동 데이터 업데이트 스크립트
GitHub Actions가 매주 토요일 오후 9시(KST) 자동 실행
"""
import requests, json, re, sys, time
from datetime import date

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.dhlottery.co.kr/",
    "Accept": "application/json, text/plain, */*",
}

def fetch_round(n, retries=3):
    url = f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={n}"
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            d = r.json()
            if d.get("returnValue") == "success":
                return {
                    "round":   d["drwNo"],
                    "date":    d["drwNoDate"],
                    "numbers": [d[f"drwtNo{i}"] for i in range(1, 7)],
                    "bonus":   d["bnusNo"],
                }
        except Exception as e:
            print(f"  시도 {attempt+1}/{retries} 실패: {e}")
            time.sleep(2)
    return None

def calc_latest_round():
    start = date(2002, 12, 7)
    today = date.today()
    return (today - start).days // 7 + 1

# ── App.jsx 읽기 ──────────────────────────────────────────────────────────────
try:
    with open("src/App.jsx", "r", encoding="utf-8") as f:
        content = f.read()
except FileNotFoundError:
    print("❌ src/App.jsx 파일을 찾을 수 없습니다.")
    sys.exit(1)

# ── 현재 파일의 마지막 회차 파악 ──────────────────────────────────────────────
rounds_in_file = [int(r) for r in re.findall(r'"round":(\d+)', content)]
if not rounds_in_file:
    print("❌ HISTORY에서 회차를 찾을 수 없습니다.")
    sys.exit(1)

last_in_file  = max(rounds_in_file)
latest_round  = calc_latest_round()

print(f"📋 파일 마지막 회차: {last_in_file}")
print(f"📅 오늘 기준 최신 회차: {latest_round}")

if last_in_file >= latest_round:
    print("✅ 이미 최신 데이터입니다. 업데이트 불필요.")
    sys.exit(0)

# ── 새 회차 수집 ──────────────────────────────────────────────────────────────
new_entries = []
for r in range(last_in_file + 1, latest_round + 1):
    print(f"  🔄 {r}회차 가져오는 중...", end=" ")
    data = fetch_round(r)
    if data:
        new_entries.append(data)
        print(f"✅ {data['numbers']} +{data['bonus']}")
    else:
        print(f"❌ 실패 (아직 미추첨이거나 네트워크 오류)")
    time.sleep(0.3)

if not new_entries:
    print("새 데이터 없음. 업데이트 스킵.")
    sys.exit(0)

# ── App.jsx HISTORY 배열에 삽입 ───────────────────────────────────────────────
# // HISTORY_END 마커 직전에 새 항목 추가
new_items_str = ""
for entry in new_entries:
    nums = json.dumps(entry["numbers"], separators=(',', ':'))
    new_items_str += f',{{"round":{entry["round"]},"date":"{entry["date"]}","numbers":{nums},"bonus":{entry["bonus"]}}}'

# HISTORY 배열 닫는 부분 직전에 삽입
# 패턴: 마지막 {...}]; 앞에 추가
content_new = re.sub(
    r'(\}\]\s*;\s*// HISTORY_END)',
    lambda m: new_items_str + "}];\n// HISTORY_END",
    content,
    count=1
)

# 패턴이 없으면 fallback: }]; 패턴 사용
if content_new == content:
    content_new = re.sub(
        r'(\}\];)',
        lambda m: new_items_str + "}];",
        content,
        count=1
    )

with open("src/App.jsx", "w", encoding="utf-8") as f:
    f.write(content_new)

print(f"\n🎰 {len(new_entries)}개 회차 추가 완료!")
print(f"   추가 회차: {[e['round'] for e in new_entries]}")
