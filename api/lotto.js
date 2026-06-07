
// api/lotto.js — Vercel Serverless Function
// 서버에서 동행복권 API 호출 (CORS 우회)
// 사용법: /api/lotto?round=1227

export default async function handler(req, res) {
  // CORS 헤더 설정
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET");

  const { round } = req.query;
  if (!round) {
    return res.status(400).json({ error: "round 파라미터가 필요합니다" });
  }

  try {
    const response = await fetch(
      `https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo=${round}`,
      {
        headers: {
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
          "Referer": "https://www.dhlottery.co.kr/",
        },
      }
    );

    const data = await response.json();

    if (data.returnValue !== "success") {
      return res.status(404).json({ error: "해당 회차 데이터 없음", round });
    }

    return res.status(200).json({
      round: data.drwNo,
      date: data.drwNoDate,
      numbers: [data.drwtNo1, data.drwtNo2, data.drwtNo3, data.drwtNo4, data.drwtNo5, data.drwtNo6],
      bonus: data.bnusNo,
    });
  } catch (e) {
    return res.status(500).json({ error: "API 호출 실패", message: e.message });
  }
}
