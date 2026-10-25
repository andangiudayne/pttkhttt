from datetime import datetime
from typing import Optional
from chobay.dao.database import Database
from chobay.dao.interfaces import ShippingDAO, VehicleDAO
from chobay.model.delivery import Shipping, Hub, DeliveryVehicle, TrackingEvent, FLEET_CLASSES
from chobay.model.enums import DeliveryMode, ShippingStatus


class ShippingDAOImpl(ShippingDAO):
    def __init__(self, db: Database):
        self.db = db

    def create_shipping(self, s: Shipping) -> int:
        with self.db.connect() as con:
            cur = con.execute("""INSERT INTO shipping(order_id, mode, hub_id, vehicle_id, status, distance_km,
                                 eta_minutes, fee, ai_score, ai_confidence, ai_reason, approved_by)
                                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                              (s.order_id, s.mode.value, s.hub_id, s.vehicle_id, s.status.value, s.distance_km,
                               s.eta_minutes, s.fee, s.ai_score, s.ai_confidence, s.ai_reason, s.approved_by))
        s.shipping_id = cur.lastrowid
        return s.shipping_id

    def get_by_order(self, order_id: int) -> Optional[Shipping]:
        return self._get("order_id", order_id)

    def get_by_id(self, shipping_id: int) -> Optional[Shipping]:
        return self._get("shipping_id", shipping_id)

    def _get(self, col: str, value: int) -> Optional[Shipping]:
        with self.db.connect() as con:
            r = con.execute(f"SELECT * FROM shipping WHERE {col} = ?", (value,)).fetchone()
            if not r:
                return None
            ev = con.execute("SELECT * FROM tracking_event WHERE shipping_id = ? ORDER BY event_id",
                             (r["shipping_id"],)).fetchall()
        return Shipping(r["shipping_id"], r["order_id"], DeliveryMode(r["mode"]), r["hub_id"], r["distance_km"],
                        r["eta_minutes"], r["fee"], ShippingStatus(r["status"]), r["vehicle_id"], r["ai_score"] or 0,
                        r["ai_confidence"] or 0, r["ai_reason"] or "", r["approved_by"],
                        [TrackingEvent(datetime.fromisoformat(e["ts"]), ShippingStatus(e["status"]), e["latitude"],
                                       e["longitude"], e["note"] or "") for e in ev])

    def add_event(self, shipping_id: int, e: TrackingEvent) -> None:
        with self.db.connect() as con:
            con.execute("INSERT INTO tracking_event(shipping_id, ts, status, latitude, longitude, note) VALUES (?,?,?,?,?,?)",
                        (shipping_id, e.ts.isoformat(timespec="seconds"), e.status.value, e.latitude, e.longitude, e.note))

    def update_status(self, shipping_id: int, status: ShippingStatus, approved_by: str | None = None) -> None:
        with self.db.connect() as con:
            con.execute("""UPDATE shipping SET status = ?, approved_by = COALESCE(?, approved_by),
                           delivered_at = CASE WHEN ? = 'DELIVERED' THEN CURRENT_TIMESTAMP ELSE delivered_at END
                           WHERE shipping_id = ?""", (status.value, approved_by, status.value, shipping_id))

    def find_by_status(self, statuses: list[ShippingStatus]) -> list[Shipping]:
        marks = ",".join("?" * len(statuses))
        with self.db.connect() as con:
            ids = [r["shipping_id"] for r in con.execute(
                f"SELECT shipping_id FROM shipping WHERE status IN ({marks}) ORDER BY shipping_id DESC",
                [s.value for s in statuses]).fetchall()]
        return [self.get_by_id(i) for i in ids]


class VehicleDAOImpl(VehicleDAO):
    def __init__(self, db: Database):
        self.db = db

    def hubs(self) -> list[Hub]:
        with self.db.connect() as con:
            rows = con.execute("SELECT * FROM hub ORDER BY hub_id").fetchall()
        return [Hub(r["hub_id"], r["name"], r["hub_type"], r["latitude"], r["longitude"], r["transfer_min"]) for r in rows]

    def find_available(self, mode: DeliveryMode) -> list[DeliveryVehicle]:
        with self.db.connect() as con:
            rows = con.execute("SELECT * FROM vehicle WHERE mode = ? AND status = 'IDLE' ORDER BY battery_pct DESC",
                               (mode.value,)).fetchall()
        cls = FLEET_CLASSES[mode]
        return [cls(vehicle_id=r["vehicle_id"], code=r["code"], hub_id=r["hub_id"], status=r["status"],
                    battery_pct=r["battery_pct"]) for r in rows]

    def mark_busy(self, vehicle_id: int) -> None:
        with self.db.connect() as con:
            con.execute("UPDATE vehicle SET status = 'BUSY' WHERE vehicle_id = ?", (vehicle_id,))

    def mark_idle(self, vehicle_id: int) -> None:
        with self.db.connect() as con:
            con.execute("UPDATE vehicle SET status = 'IDLE' WHERE vehicle_id = ?", (vehicle_id,))

    def find_all(self) -> list[DeliveryVehicle]:
        """UC17 Xem đội phương tiện — mọi chiếc, kèm loại, hub, trạng thái, pin."""
        with self.db.connect() as con:
            rows = con.execute("SELECT * FROM vehicle ORDER BY hub_id, mode, code").fetchall()
        return [FLEET_CLASSES[DeliveryMode(r["mode"])](vehicle_id=r["vehicle_id"], code=r["code"], hub_id=r["hub_id"],
                                                        status=r["status"], battery_pct=r["battery_pct"]) for r in rows]
