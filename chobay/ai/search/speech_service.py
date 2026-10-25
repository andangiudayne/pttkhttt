"""SpeechService — Speech-to-Text.

Nhận dạng giọng nói THẬT chạy ở SearchUI bằng Web Speech API của trình duyệt (Chrome/Edge, lang="vi-VN"):
khách bấm 🎤 → nói → trình duyệt trả bản phiên âm (transcript) + độ tin cậy → gửi lên với mode=VOICE.
Phía máy chủ, transcribe() chuẩn hóa bản phiên âm để QueryService hiểu được:
  "dưới 40.000 đồng" → "dưới 40000", "dưới 1,5 triệu" → "dưới 1500000", bỏ khoảng trắng thừa.
Nếu trình duyệt không hỗ trợ micro, khách vẫn gõ câu nói vào ô tìm kiếm (fallback, test TC08 dùng cách này)."""
import re

_THOUSANDS = re.compile(r"(?<=\d)[.,](?=\d{3}\b)")                 # 40.000 / 40,000 → 40000
_MILLION = re.compile(r"(\d+(?:[.,]\d+)?)\s*triệu", re.IGNORECASE)  # 1,5 triệu → 1500000
_CURRENCY = re.compile(r"(?<=\d)\s*(?:đồng|vnđ|vnd|đ)\b", re.IGNORECASE)


class SpeechService:
    MIN_CONFIDENCE = 0.3          # dưới ngưỡng → SearchController yêu cầu nói lại

    def transcribe(self, audio_input: str) -> str:
        """audio_input = bản phiên âm do Web Speech API trả về (hoặc câu khách gõ khi không có micro)."""
        t = " ".join(audio_input.split())
        t = _MILLION.sub(lambda m: str(round(float(m.group(1).replace(",", ".")) * 1_000_000)), t)
        while _THOUSANDS.search(t):
            t = _THOUSANDS.sub("", t)
        return _CURRENCY.sub("", t).strip()

    def is_confident(self, confidence: float | None) -> bool:
        return confidence is None or confidence >= self.MIN_CONFIDENCE
