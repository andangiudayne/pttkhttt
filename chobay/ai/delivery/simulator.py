"""Bộ mô phỏng lịch sử giao hàng (dữ liệu huấn luyện GIẢ LẬP cho prototype).
Khi triển khai thật, dữ liệu lấy từ bảng shipping + tracking_event."""
import numpy as np
from chobay.model.enums import DeliveryMode
from chobay.model.delivery import spec

MODES = list(DeliveryMode)
HANDLING = {DeliveryMode.DRONE: 4, DeliveryMode.ROBOT: 3, DeliveryMode.AUTO_CAR: 6, DeliveryMode.FLYING_CAR: 14,
            DeliveryMode.SUBMARINE: 18, DeliveryMode.AUTO_BOAT: 7, DeliveryMode.EBIKE: 5, DeliveryMode.LOCKER: 35}
TRAFFIC_SENS = {DeliveryMode.DRONE: 0.0, DeliveryMode.ROBOT: 0.35, DeliveryMode.AUTO_CAR: 1.1, DeliveryMode.FLYING_CAR: 0.0,
                DeliveryMode.SUBMARINE: 0.0, DeliveryMode.AUTO_BOAT: 0.1, DeliveryMode.EBIKE: 0.7, DeliveryMode.LOCKER: 0.0}


def features(mode: DeliveryMode, dist, rain, wind, traffic, hour):
    onehot = [1.0 if m == mode else 0.0 for m in MODES]
    rush = 1.0 if hour in (7, 8, 17, 18, 19) else 0.0
    return onehot + [dist, rain, wind, traffic, rush]


def true_travel_minutes(rng, mode, dist, rain, wind, traffic, hour):
    s = spec(mode)
    if mode == DeliveryMode.LOCKER:
        base = 0.0
    else:
        base = dist / s.speed_kmh * 60
    rush = 1.0 if hour in (7, 8, 17, 18, 19) else 0.0
    t = base * (1 + TRAFFIC_SENS[mode] * (traffic + 0.4 * rush)) + HANDLING[mode]
    if mode in (DeliveryMode.DRONE, DeliveryMode.FLYING_CAR):
        t += 0.6 * wind                       # bay ngược gió
    if mode in (DeliveryMode.EBIKE, DeliveryMode.ROBOT, DeliveryMode.AUTO_CAR):
        t *= 1 + 0.02 * rain                  # mưa làm chậm đường bộ
    return float(t * rng.lognormal(0, 0.08))


def true_fail_prob(mode, dist, rain, wind, battery, fragile):
    s = spec(mode)
    z = -4.2 + 2.6 * (wind / max(s.max_wind_ms, 1)) ** 2 + 2.0 * (rain / max(s.max_rain_mmh, 1)) ** 2 \
        + 1.8 * (dist / max(s.max_range_km, 0.5)) ** 3 + 1.2 * (1 - battery / 100) + 0.6 * fragile * (mode == DeliveryMode.DRONE)
    return 1 / (1 + np.exp(-z))


def simulate(n=6000, seed=7):
    rng = np.random.default_rng(seed)
    X_eta, y_eta, X_risk, y_risk = [], [], [], []
    for _ in range(n):
        mode = MODES[rng.integers(len(MODES))]
        s = spec(mode)
        dist = float(rng.uniform(0.3, max(s.max_range_km, 1.0)))
        rain = float(rng.choice([0, 0, 0, 1, 3, 8, 20]))
        wind = float(rng.uniform(0, 14))
        traffic = float(rng.uniform(0, 1))
        hour = int(rng.integers(6, 22))
        battery = float(rng.uniform(40, 100))
        fragile = int(rng.random() < 0.2)
        X_eta.append(features(mode, dist, rain, wind, traffic, hour))
        y_eta.append(true_travel_minutes(rng, mode, dist, rain, wind, traffic, hour))
        X_risk.append(risk_features(mode, dist, rain, wind, battery, fragile))
        y_risk.append(int(rng.random() < true_fail_prob(mode, dist, rain, wind, battery, fragile)))
    return np.array(X_eta), np.array(y_eta), np.array(X_risk), np.array(y_risk)


def risk_features(mode, dist, rain, wind, battery, fragile):
    s = spec(mode)
    onehot = [1.0 if m == mode else 0.0 for m in MODES]
    return onehot + [(wind / max(s.max_wind_ms, 1)) ** 2, (rain / max(s.max_rain_mmh, 1)) ** 2,
                     (dist / max(s.max_range_km, 0.5)) ** 3, 1 - battery / 100, fragile * (mode == DeliveryMode.DRONE)]
