# 🏠 나장현서 로또집

실제 동행복권 데이터 기반 통계 로또 번호 추천 앱

## 기능
- ✅ 실제 동행복권 1026~1225회차 데이터 (200회차)
- ✅ 최근 20회 트렌드 가중치 60% + 전체 빈도 40%
- ✅ 연속번호 · 미출현 간격 · 구간 분포 패턴 분석
- ✅ 생성된 번호 통계 분석 카드 (합계, 홀짝, 고저, 구간 분포)
- ✅ 매주 일요일 0시(KST) 자동 회차 +1
- ✅ GitHub Actions 매주 토요일 오후 9시(KST) 자동 데이터 업데이트
- ✅ 디스코드 공유용 미리보기

---

## 🚀 배포 방법 (10분 완성)

### 1단계 — GitHub 레포 만들기
1. https://github.com/new 접속
2. Repository name: `lotto-jip`
3. Public 선택 → **Create repository**

### 2단계 — 파일 업로드
```
lotto-jip/
├── src/
│   ├── App.jsx       ← 메인 앱 (이 파일)
│   └── index.js
├── public/
│   └── index.html
├── .github/
│   └── workflows/
│       └── update-lotto.yml   ← 자동 업데이트
├── scripts/
│   └── update_lotto.py        ← 업데이트 스크립트
└── package.json
```

GitHub 웹에서 드래그앤드롭으로 업로드하거나:
```bash
git init
git add .
git commit -m "🎰 나장현서 로또집 첫 배포"
git branch -M main
git remote add origin https://github.com/[내아이디]/lotto-jip.git
git push -u origin main
```

### 3단계 — Vercel 배포
1. https://vercel.com 접속 → GitHub 로그인
2. **New Project** → `lotto-jip` 레포 선택
3. Framework: **Create React App** → **Deploy**
4. 완료! URL이 자동 생성됨 → 디스코드에 공유

### 4단계 — GitHub Actions 권한 설정
1. GitHub 레포 → **Settings** → **Actions** → **General**
2. **Workflow permissions** → `Read and write permissions` 선택 → Save

---

## 🔄 자동 업데이트 동작 방식
```
매주 토요일 오후 8:35 추첨
       ↓
매주 토요일 오후 9:00 GitHub Actions 실행
       ↓
동행복권 API에서 최신 회차 데이터 수집
       ↓
src/App.jsx HISTORY 배열 자동 업데이트
       ↓
Vercel 자동 재배포 (약 1~2분)
       ↓
앱에 최신 데이터 반영 완료 ✅
```

---

## 📝 수동 업데이트 (필요 시)
GitHub 레포 → **Actions** 탭 → **로또 데이터 자동 업데이트** → **Run workflow**
