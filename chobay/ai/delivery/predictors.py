"""Mô hình học máy: dự đoán thời gian di chuyển (ETA) và xác suất giao thất bại (risk)."""
from __future__ import annotations
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import mean_absolute_error, roc_auc_score
from sklearn.model_selection import train_test_split
from chobay.model.enums import DeliveryMode
from . import simulator


class EtaPredictor:
    """ETA_travel = f_θ(mode, distance, rain, wind, traffic, rush_hour) — Gradient Boosting."""

    def __init__(self):
        self.model = GradientBoostingRegressor(n_estimators=250, max_depth=3, learning_rate=0.08, random_state=1)
        self.mae: float | None = None

    def fit(self, X, y):
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=3)
        self.model.fit(Xtr, ytr)
        self.mae = float(mean_absolute_error(yte, self.model.predict(Xte)))
        return self

    def predict(self, mode: DeliveryMode, dist, rain, wind, traffic, hour) -> float:
        return float(self.model.predict([simulator.features(mode, dist, rain, wind, traffic, hour)])[0])


class RiskPredictor:
    """P(thất bại | mode, thời tiết, quãng đường, pin, dễ vỡ) — Logistic Regression."""

    def __init__(self):
        self.model = LogisticRegression(max_iter=2000)
        self.auc: float | None = None

    def fit(self, X, y):
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=3, stratify=y)
        self.model.fit(Xtr, ytr)
        self.auc = float(roc_auc_score(yte, self.model.predict_proba(Xte)[:, 1]))
        return self

    def predict(self, mode, dist, rain, wind, battery, fragile) -> float:
        x = simulator.risk_features(mode, dist, rain, wind, battery, fragile)
        return float(self.model.predict_proba([x])[0, 1])


def train_default(seed: int = 7):
    X_eta, y_eta, X_risk, y_risk = simulator.simulate(seed=seed)
    return EtaPredictor().fit(X_eta, y_eta), RiskPredictor().fit(X_risk, y_risk)
