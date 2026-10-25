"""IWeatherService — điểm tích hợp với Dịch vụ thời tiết (tác nhân phụ, sơ đồ ngữ cảnh 1.7 và component 4.4).

Hai cài đặt:
  • OpenMeteoWeatherService — mặc định khi chạy web: tự lấy thời tiết hiện tại và dự báo theo giờ từ Open-Meteo
    (api.open-meteo.com, miễn phí, không cần khóa API) theo TỌA ĐỘ ĐỊA CHỈ GIAO; lưu đệm 15 phút mỗi ô lưới 0,1°;
    mất mạng → dùng số liệu gần nhất, nếu chưa có thì số liệu dự phòng (mưa 0, gió 3) và thử lại sau 5 phút.
    Điều phối viên vẫn có thể GHI ĐÈ THỦ CÔNG (sự cố, diễn tập bão) rồi bấm “Về tự động”.
  • WeatherStub — trạm giả lập trong bộ nhớ: dùng cho kiểm thử, sinh dữ liệu mẫu và khi đặt CHOBAY_WEATHER=stub.
Thời tiết không lưu CSDL: AI đọc lại mỗi lần đề xuất cách giao (BR-D06)."""
from __future__ import annotations
import json
import time
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from chobay.ai.delivery.rules import Weather

HCM_CENTER = (10.7769, 106.7009)          # Quận 1 — trạm mặc định khi không có địa chỉ cụ thể
VN_TZ = timezone(timedelta(hours=7))      # giờ Việt Nam cố định (UTC+7), không phụ thuộc múi giờ của máy chạy


def vn_time(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, VN_TZ).replace(tzinfo=None)


def traffic_for(hour: int) -> float:
    """Chỉ số giao thông theo giờ (giờ cao điểm TP.HCM 7–9h, 16–19h)."""
    if hour in (7, 8, 16, 17, 18, 19):
        return 0.85
    return 0.35 if hour >= 22 or hour < 6 else 0.55


@dataclass
class HourForecast:
    time: datetime
    rain_mmh: float
    rain_prob: int
    wind_ms: float


class IWeatherService(ABC):
    @abstractmethod
    def current(self, lat: float | None = None, lon: float | None = None) -> Weather: ...

    def forecast(self, lat: float | None = None, lon: float | None = None, hours: int = 6) -> list[HourForecast]:
        return []

    @abstractmethod
    def info(self, lat: float | None = None, lon: float | None = None) -> dict:
        """mode: AUTO | MANUAL · source · updated_at · error — để trang Thời tiết hiển thị nguồn số liệu."""

    @abstractmethod
    def update(self, rain_mmh: float, wind_ms: float) -> Weather:
        """Ghi đè thủ công (điều phối viên)."""

    def clear_override(self) -> None:
        """Bỏ ghi đè, quay lại số liệu tự động (stub: không làm gì)."""


def _clamp(rain_mmh: float, wind_ms: float) -> tuple[float, float]:
    """Giới hạn giá trị hợp lý: mưa 0–100 mm/h, gió 0–40 m/s."""
    return min(max(rain_mmh, 0.0), 100.0), min(max(wind_ms, 0.0), 40.0)


class WeatherStub(IWeatherService):
    def __init__(self, rain_mmh: float = 0.0, wind_ms: float = 3.0, traffic_index: float = 0.6, hour: int = 10):
        self._w = Weather(rain_mmh=rain_mmh, wind_ms=wind_ms, traffic_index=traffic_index, hour=hour)

    def current(self, lat: float | None = None, lon: float | None = None) -> Weather:
        return self._w

    def info(self, lat=None, lon=None) -> dict:
        return {"mode": "MANUAL", "source": "Trạm giả lập (WeatherStub)", "updated_at": None, "error": None}

    def update(self, rain_mmh: float, wind_ms: float) -> Weather:
        rain, wind = _clamp(rain_mmh, wind_ms)
        self._w = Weather(rain_mmh=rain, wind_ms=wind, traffic_index=self._w.traffic_index, hour=self._w.hour)
        return self._w


class OpenMeteoWeatherService(IWeatherService):
    URL = "https://api.open-meteo.com/v1/forecast"
    TTL_S = 15 * 60                 # làm mới mỗi 15 phút (Open-Meteo cập nhật số liệu hiện tại theo chu kỳ 15 phút)
    RETRY_S = 5 * 60                # lỗi mạng → 5 phút sau mới thử lại, web không bị chậm
    TIMEOUT_S = 3
    FALLBACK = Weather(rain_mmh=0.0, wind_ms=3.0)

    def __init__(self, fetch=None, clock=time.time):
        self._fetch = fetch or self._http_get          # tiêm hàm giả khi kiểm thử
        self._clock = clock
        self._cache: dict[tuple[float, float], tuple[float, dict]] = {}
        self._retry_at: dict[tuple[float, float], float] = {}
        self._error: str | None = None
        self._override: Weather | None = None

    # ---------- gọi API ----------
    def _http_get(self, lat: float, lon: float) -> dict:
        q = urllib.parse.urlencode({
            "latitude": lat, "longitude": lon, "timezone": "Asia/Ho_Chi_Minh", "wind_speed_unit": "ms",
            "current": "precipitation,wind_speed_10m", "forecast_hours": 12,
            "hourly": "precipitation,precipitation_probability,wind_speed_10m"})
        with urllib.request.urlopen(f"{self.URL}?{q}", timeout=self.TIMEOUT_S) as r:
            return json.loads(r.read().decode("utf-8"))

    @staticmethod
    def _key(lat, lon) -> tuple[float, float]:
        lat, lon = (lat, lon) if lat is not None and lon is not None else HCM_CENTER
        return round(lat, 1), round(lon, 1)

    def _data(self, lat, lon) -> tuple[dict | None, float | None]:
        key, now = self._key(lat, lon), self._clock()
        hit = self._cache.get(key)
        if hit and now - hit[0] < self.TTL_S:
            return hit[1], hit[0]
        if now < self._retry_at.get(key, 0):
            return (hit[1], hit[0]) if hit else (None, None)
        try:
            data = self._fetch(*key)
            data["current"]["wind_speed_10m"]                         # kiểm tra đúng định dạng
            self._cache[key] = (now, data)
            self._error = None
            return data, now
        except Exception as exc:                                       # mất mạng, hết thời gian chờ, sai định dạng
            self._retry_at[key] = now + self.RETRY_S
            self._error = f"Không kết nối được dịch vụ dự báo ({type(exc).__name__})"
            return (hit[1], hit[0]) if hit else (None, None)

    # ---------- IWeatherService ----------
    def current(self, lat: float | None = None, lon: float | None = None) -> Weather:
        hour = vn_time(self._clock()).hour
        if self._override is not None:
            return Weather(self._override.rain_mmh, self._override.wind_ms, traffic_for(hour), hour)
        data, _ = self._data(lat, lon)
        if data is None:
            return Weather(self.FALLBACK.rain_mmh, self.FALLBACK.wind_ms, traffic_for(hour), hour)
        cur = data["current"]
        per_hour = 3600 / max(int(cur.get("interval") or 3600), 1)    # precipitation = tổng mm trong khoảng interval
        rain, wind = _clamp(float(cur.get("precipitation") or 0) * per_hour, float(cur.get("wind_speed_10m") or 0))
        return Weather(round(rain, 1), round(wind, 1), traffic_for(hour), hour)

    def forecast(self, lat: float | None = None, lon: float | None = None, hours: int = 6) -> list[HourForecast]:
        data, _ = self._data(lat, lon)
        if not data or "hourly" not in data:
            return []
        h, now = data["hourly"], vn_time(self._clock()).replace(minute=0, second=0, microsecond=0)
        out = []
        for i, t in enumerate(h.get("time", [])):
            ts = datetime.fromisoformat(t)
            if ts >= now and len(out) < hours:
                prob = h.get("precipitation_probability") or [0] * len(h["time"])
                out.append(HourForecast(ts, float(h["precipitation"][i] or 0), int(prob[i] or 0), float(h["wind_speed_10m"][i] or 0)))
        return out

    def info(self, lat: float | None = None, lon: float | None = None) -> dict:
        if self._override is not None:
            return {"mode": "MANUAL", "source": "Điều phối viên ghi đè", "updated_at": None, "error": None}
        data, at = self._data(lat, lon)
        return {"mode": "AUTO", "source": "Open-Meteo" if data else "Số liệu dự phòng",
                "updated_at": vn_time(at) if at else None, "error": self._error}

    def update(self, rain_mmh: float, wind_ms: float) -> Weather:
        rain, wind = _clamp(rain_mmh, wind_ms)
        self._override = Weather(rain_mmh=rain, wind_ms=wind)
        return self.current()

    def clear_override(self) -> None:
        self._override = None

    def refresh(self) -> None:
        """Bấm “Làm mới”: bỏ bộ đệm để lần đọc sau gọi API ngay."""
        self._cache.clear()
        self._retry_at.clear()
