"""Kiểm thử không gọi mạng: web dùng WeatherStub (trạm giả lập) thay cho Open-Meteo."""
import os

os.environ["CHOBAY_WEATHER"] = "stub"
