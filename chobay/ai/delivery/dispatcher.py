"""AI Delivery Dispatcher — chọn phương thức giao phù hợp NHẤT với sản phẩm trong đơn.

Pipeline:  Luật cứng (lọc)  →  ML dự đoán ETA & rủi ro  →  Chấm điểm đa tiêu chí  →  Giải thích  →  Người duyệt
AI Design = Prediction + Fallback + Human Control.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from chobay.dao.interfaces import VehicleDAO
from chobay.model.delivery import DeliveryVehicle, Hub
from chobay.model.enums import DeliveryMode, DeliveryPreference, TempClass
from .rules import ConstraintChecker, DeliveryRequest, RuleViolation, haversine_km, route_km
from .predictors import EtaPredictor, RiskPredictor

PICK_PACK_MIN = 10
WEIGHTS = {   # (thời gian, chi phí, rủi ro, phát thải, độ tươi)
    DeliveryPreference.FAST:  (0.55, 0.15, 0.20, 0.05, 0.05),
    DeliveryPreference.CHEAP: (0.15, 0.55, 0.20, 0.05, 0.05),
    DeliveryPreference.GREEN: (0.15, 0.15, 0.20, 0.45, 0.05),
}
FRESH_TOLERANCE = {TempClass.AMBIENT: 240, TempClass.CHILLED: 90, TempClass.FROZEN: 60}  # phút chấp nhận được


@dataclass
class ModeOption:
    mode: DeliveryMode
    name_vi: str
    vehicle: DeliveryVehicle | None
    hub: Hub | None
    distance_km: float = 0
    eta_min: int = 0
    fee: int = 0
    risk: float = 0
    co2_g: int = 0
    score: float = 9.99
    feasible: bool = True
    violations: list[RuleViolation] = field(default_factory=list)


@dataclass
class DispatchDecision:
    chosen: ModeOption | None
    options: list[ModeOption]
    confidence: float
    needs_human: bool
    reason: str
    fallback_used: bool = False


class DeliveryDispatcher:
    def __init__(self, vehicle_dao: VehicleDAO, eta: EtaPredictor, risk: RiskPredictor,
                 checker: ConstraintChecker | None = None):
        self.vehicle_dao, self.eta, self.risk = vehicle_dao, eta, risk
        self.checker = checker or ConstraintChecker()

    # ---------- 1. ứng viên ----------
    def _candidate(self, mode: DeliveryMode, req: DeliveryRequest) -> ModeOption:
        hubs = {h.hub_id: h for h in self.vehicle_dao.hubs()}
        vehicles = self.vehicle_dao.find_available(mode)
        from chobay.model.delivery import spec
        if not vehicles:
            s = spec(mode)
            return ModeOption(mode, s.name_vi, None, None, feasible=False,
                              violations=[RuleViolation("BR-D12", "Không còn phương tiện rảnh")])
        a = req.address
        best = min(vehicles, key=lambda v: haversine_km(hubs[v.hub_id].latitude, hubs[v.hub_id].longitude,
                                                         a.latitude, a.longitude))
        hub = hubs[best.hub_id]
        dist = route_km(mode, haversine_km(hub.latitude, hub.longitude, a.latitude, a.longitude))
        return ModeOption(mode, best.name_vi, best, hub, distance_km=dist)

    # ---------- 2+3. dự đoán & chấm điểm ----------
    def decide(self, req: DeliveryRequest, pref: DeliveryPreference = DeliveryPreference.FAST) -> DispatchDecision:
        try:
            return self._decide_ai(req, pref)
        except Exception as exc:                                 # AI lỗi/timeout → luật dự phòng
            return self._fallback(req, f"AI không khả dụng ({type(exc).__name__}) — dùng luật dự phòng")

    def _decide_ai(self, req: DeliveryRequest, pref: DeliveryPreference) -> DispatchDecision:
        w = req.weather
        opts = [self._candidate(m, req) for m in DeliveryMode]
        for o in opts:
            if o.vehicle is None:
                continue
            travel = self.eta.predict(o.mode, o.distance_km, w.rain_mmh, w.wind_ms, w.traffic_index, w.hour)
            o.eta_min = int(round(PICK_PACK_MIN + o.hub.transfer_min + travel))
            o.violations = self.checker.check(o.vehicle, req, o.distance_km, travel)
            o.feasible = not o.violations
            o.fee = o.vehicle.fee(o.distance_km)
            o.co2_g = int(o.vehicle.co2_g_per_km * o.distance_km)
            o.risk = self.risk.predict(o.mode, o.distance_km, w.rain_mmh, w.wind_ms,
                                       o.vehicle.battery_pct, int(req.fragile))
        feas = [o for o in opts if o.feasible]
        if not feas:
            return self._fallback(req, "Không phương thức nào thỏa luật — chuyển điều phối viên", opts)
        wt, wc, wr, we, wq = WEIGHTS[pref]
        tol = FRESH_TOLERANCE[req.coldest]
        for o in feas:
            fresh_pen = max(0.0, (o.eta_min - tol) / tol)
            locker_pen = 0.15 if o.mode == DeliveryMode.LOCKER else 0.0   # khách phải tự đi lấy
            o.score = round(wt * o.eta_min / 120 + wc * o.fee / 200_000 + wr * o.risk * 5
                            + we * o.co2_g / 1500 + wq * fresh_pen + locker_pen, 4)
        feas.sort(key=lambda o: o.score)
        best = feas[0]
        margin = (feas[1].score - best.score) if len(feas) > 1 else 0.5
        confidence = round(min(0.99, (0.55 + 1.6 * margin) * (1 - best.risk)), 2)
        needs_human = best.vehicle.needs_approval or confidence < 0.6
        reason = self._explain(best, feas, opts, pref)
        opts.sort(key=lambda o: (not o.feasible, o.score))
        return DispatchDecision(best, opts, confidence, needs_human, reason)

    def _explain(self, best, feas, opts, pref) -> str:
        excluded = [f"{o.mode.value}: {o.violations[0].code}" for o in opts if not o.feasible and o.violations]
        runner = f"; phương án 2 là {feas[1].mode.value} (điểm {feas[1].score})" if len(feas) > 1 else ""
        fee = f"{best.fee:,}".replace(",", ".")                   # 21000 → 21.000
        return (f"Chọn {best.mode.value} ({best.name_vi}) — ETA {best.eta_min}′, phí {fee}đ, rủi ro "
                f"{best.risk:.0%}, ưu tiên {pref.value}{runner}. Loại: {', '.join(excluded) or 'không'}.")

    # ---------- 4. dự phòng (fallback) ----------
    def _fallback(self, req: DeliveryRequest, why: str, opts=None) -> DispatchDecision:
        order = [DeliveryMode.SUBMARINE] if req.address.area_type.value == "ISLAND" else \
                [DeliveryMode.EBIKE, DeliveryMode.AUTO_CAR]
        for m in order:
            o = self._candidate(m, req)
            if o.vehicle and not self.checker.check(o.vehicle, req, o.distance_km, None):
                o.eta_min = int(PICK_PACK_MIN + o.hub.transfer_min + o.distance_km / o.vehicle.speed_kmh * 60 * 1.3 + 10)
                o.fee = o.vehicle.fee(o.distance_km)
                return DispatchDecision(o, opts or [o], 0.5, True, f"{why}: chọn {m.value}", fallback_used=True)
        return DispatchDecision(None, opts or [], 0.0, True, why, fallback_used=True)
