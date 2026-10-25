-- ChợBay — Physical data model (SQLite 3)
-- Sinh từ Data Model (4.2): kế thừa được chuyển thành quan hệ 1–0..1 (bảng con dùng chung khóa chính).
PRAGMA foreign_keys = ON;

-- ===== KHÁCH HÀNG =====
CREATE TABLE customer (
    customer_id     INTEGER PRIMARY KEY,
    first_name      TEXT    NOT NULL,
    last_name       TEXT    NOT NULL,
    email           TEXT    NOT NULL UNIQUE,
    phone           TEXT    NOT NULL,
    loyalty_points  INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE customer_vip (            -- Customer 1 — 0..1 CustomerVIP
    customer_id  INTEGER PRIMARY KEY REFERENCES customer(customer_id) ON DELETE CASCADE,
    vip_level    INTEGER NOT NULL DEFAULT 1,
    vip_discount REAL    NOT NULL DEFAULT 0.05
);
CREATE TABLE customer_new (            -- Customer 1 — 0..1 CustomerNew
    customer_id     INTEGER PRIMARY KEY REFERENCES customer(customer_id) ON DELETE CASCADE,
    welcome_voucher INTEGER NOT NULL DEFAULT 20000,
    voucher_used    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE account (                 -- Customer 1 — 1 Account
    account_id    INTEGER PRIMARY KEY,
    customer_id   INTEGER NOT NULL UNIQUE REFERENCES customer(customer_id) ON DELETE CASCADE,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'ACTIVE'
);
CREATE TABLE staff (                   -- nhân viên vận hành: điều phối viên, quản trị, kho, quản lý (tác nhân mục 2.1)
    staff_id      INTEGER PRIMARY KEY,
    full_name     TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK (role IN ('DISPATCHER')),
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'ACTIVE'
);
CREATE TABLE address (                 -- Customer 1 — 1..* Address
    address_id           INTEGER PRIMARY KEY,
    customer_id          INTEGER NOT NULL REFERENCES customer(customer_id) ON DELETE CASCADE,
    label                TEXT    NOT NULL,
    street               TEXT    NOT NULL,
    ward                 TEXT    NOT NULL,
    district             TEXT    NOT NULL,
    city                 TEXT    NOT NULL,
    latitude             REAL    NOT NULL,
    longitude            REAL    NOT NULL,
    area_type            TEXT    NOT NULL CHECK (area_type IN ('URBAN_HIGHRISE','URBAN_STREET','SUBURBAN','RIVERSIDE','ISLAND')),
    has_drop_zone        INTEGER NOT NULL DEFAULT 0,
    nearest_vertiport_km REAL    NOT NULL DEFAULT 99
);

-- ===== SẢN PHẨM =====
CREATE TABLE category (
    category_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE
);
CREATE TABLE product (                 -- Category 1 — 0..* Product
    product_id   INTEGER PRIMARY KEY,
    category_id  INTEGER NOT NULL REFERENCES category(category_id),
    kind         TEXT    NOT NULL CHECK (kind IN ('FreshFood','FrozenFood','PackagedFood','Beverage')),
    name         TEXT    NOT NULL,
    brand        TEXT    NOT NULL,
    price        INTEGER NOT NULL CHECK (price > 0),
    unit         TEXT    NOT NULL,
    weight_kg    REAL    NOT NULL CHECK (weight_kg > 0),
    temp_class   TEXT    NOT NULL CHECK (temp_class IN ('AMBIENT','CHILLED','FROZEN')),
    is_fragile   INTEGER NOT NULL DEFAULT 0,
    is_liquid    INTEGER NOT NULL DEFAULT 0,
    strong_odor  INTEGER NOT NULL DEFAULT 0,
    stock        INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    rating       REAL    NOT NULL DEFAULT 4.5,
    image_path   TEXT    NOT NULL,
    description  TEXT    NOT NULL DEFAULT ''
);
CREATE TABLE fresh_food (              -- Product 1 — 0..1 FreshFood
    product_id       INTEGER PRIMARY KEY REFERENCES product(product_id) ON DELETE CASCADE,
    origin           TEXT    NOT NULL,
    shelf_life_hours INTEGER NOT NULL
);
CREATE TABLE frozen_food (
    product_id     INTEGER PRIMARY KEY REFERENCES product(product_id) ON DELETE CASCADE,
    storage_temp_c INTEGER NOT NULL DEFAULT -18
);
CREATE TABLE packaged_food (
    product_id  INTEGER PRIMARY KEY REFERENCES product(product_id) ON DELETE CASCADE,
    barcode     TEXT,
    expiry_days INTEGER NOT NULL DEFAULT 180
);
CREATE TABLE beverage (
    product_id INTEGER PRIMARY KEY REFERENCES product(product_id) ON DELETE CASCADE,
    volume_ml  INTEGER NOT NULL,
    barcode    TEXT
);
CREATE TABLE product_embedding (       -- Vector index cho AI Search (1 — 0..1)
    product_id   INTEGER PRIMARY KEY REFERENCES product(product_id) ON DELETE CASCADE,
    image_vector TEXT NOT NULL,        -- JSON: vector 1132 chiều = MobileNet 1024 + màu HSV 108
    keywords     TEXT NOT NULL         -- từ khóa không dấu + đồng nghĩa
);

-- ===== GIỎ HÀNG (tạm thời) =====
CREATE TABLE cart (                    -- Customer 1 — 0..1 Cart
    cart_id     INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL UNIQUE REFERENCES customer(customer_id) ON DELETE CASCADE,
    updated_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE cart_item (               -- Cart 1 — 0..* CartItem ; Product 1 — 0..* CartItem
    cart_item_id INTEGER PRIMARY KEY,
    cart_id      INTEGER NOT NULL REFERENCES cart(cart_id) ON DELETE CASCADE,
    product_id   INTEGER NOT NULL REFERENCES product(product_id),
    quantity     INTEGER NOT NULL CHECK (quantity > 0),
    cart_price   INTEGER NOT NULL,
    UNIQUE (cart_id, product_id)
);

-- ===== ĐƠN HÀNG (giao dịch) =====
CREATE TABLE orders (                  -- Customer 1 — 0..* Order ; Address 1 — 0..* Order
    order_id     INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customer(customer_id),
    address_id   INTEGER NOT NULL REFERENCES address(address_id),
    order_date   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status       TEXT    NOT NULL,
    subtotal     INTEGER NOT NULL,
    shipping_fee INTEGER NOT NULL DEFAULT 0,
    discount     INTEGER NOT NULL DEFAULT 0,
    total        INTEGER NOT NULL,
    preference   TEXT    NOT NULL DEFAULT 'FAST'
);
CREATE TABLE order_item (              -- Order 1 — 1..* OrderItem
    order_item_id INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id    INTEGER NOT NULL REFERENCES product(product_id),
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    unit_price    INTEGER NOT NULL
);
CREATE TABLE payment (                 -- Order 1 — 0..1 Payment
    payment_id      INTEGER PRIMARY KEY,
    order_id        INTEGER NOT NULL UNIQUE REFERENCES orders(order_id) ON DELETE CASCADE,
    method          TEXT    NOT NULL CHECK (method IN ('CASH','CREDIT','EWALLET')),
    amount          INTEGER NOT NULL,
    status          TEXT    NOT NULL,
    transaction_ref TEXT,
    paid_at         TEXT
);
CREATE TABLE pay_cash   (payment_id INTEGER PRIMARY KEY REFERENCES payment(payment_id) ON DELETE CASCADE, cash_tendered INTEGER);
CREATE TABLE pay_credit (payment_id INTEGER PRIMARY KEY REFERENCES payment(payment_id) ON DELETE CASCADE, card_last4 TEXT NOT NULL);
CREATE TABLE pay_ewallet(payment_id INTEGER PRIMARY KEY REFERENCES payment(payment_id) ON DELETE CASCADE, wallet_provider TEXT NOT NULL);

-- ===== GIAO HÀNG ĐA PHƯƠNG THỨC =====
CREATE TABLE hub (
    hub_id    INTEGER PRIMARY KEY,
    name      TEXT NOT NULL,
    hub_type  TEXT NOT NULL CHECK (hub_type IN ('DARK_STORE','DRONE_PORT','VERTIPORT','SEA_DOCK','RIVER_DOCK')),
    latitude  REAL NOT NULL,
    longitude REAL NOT NULL,
    transfer_min INTEGER NOT NULL DEFAULT 0   -- thời gian chuyển hàng từ kho tối trung tâm tới hub
);
CREATE TABLE vehicle_type (            -- kế thừa DeliveryVehicle → bảng tham chiếu loại phương tiện
    mode           TEXT PRIMARY KEY,
    name_vi        TEXT    NOT NULL,
    max_payload_kg REAL    NOT NULL,
    max_range_km   REAL    NOT NULL,
    speed_kmh      REAL    NOT NULL,
    has_cooler     INTEGER NOT NULL,
    has_freezer    INTEGER NOT NULL,
    base_fee       INTEGER NOT NULL,
    fee_per_km     INTEGER NOT NULL,
    co2_g_per_km   INTEGER NOT NULL,
    max_wind_ms    REAL    NOT NULL,
    max_rain_mmh   REAL    NOT NULL,
    needs_approval INTEGER NOT NULL,
    allowed_areas  TEXT    NOT NULL
);
CREATE TABLE vehicle (                 -- VehicleType 1 — 0..* Vehicle ; Hub 1 — 0..* Vehicle
    vehicle_id  INTEGER PRIMARY KEY,
    mode        TEXT    NOT NULL REFERENCES vehicle_type(mode),
    hub_id      INTEGER NOT NULL REFERENCES hub(hub_id),
    code        TEXT    NOT NULL UNIQUE,
    status      TEXT    NOT NULL DEFAULT 'IDLE',
    battery_pct INTEGER NOT NULL DEFAULT 100
);
CREATE TABLE shipping (                -- Order 1 — 0..1 Shipping ; Vehicle 0..1 — 0..* Shipping
    shipping_id   INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL UNIQUE REFERENCES orders(order_id) ON DELETE CASCADE,
    mode          TEXT    NOT NULL REFERENCES vehicle_type(mode),
    hub_id        INTEGER NOT NULL REFERENCES hub(hub_id),
    vehicle_id    INTEGER REFERENCES vehicle(vehicle_id),
    status        TEXT    NOT NULL,
    distance_km   REAL    NOT NULL,
    eta_minutes   INTEGER NOT NULL,
    fee           INTEGER NOT NULL,
    ai_score      REAL,
    ai_confidence REAL,
    ai_reason     TEXT,
    approved_by   TEXT REFERENCES staff(username),   -- điều phối viên duyệt chuyến (UC15, BR-H1)
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delivered_at  TEXT
);
CREATE TABLE tracking_event (          -- Shipping 1 — 1..* TrackingEvent
    event_id    INTEGER PRIMARY KEY,
    shipping_id INTEGER NOT NULL REFERENCES shipping(shipping_id) ON DELETE CASCADE,
    ts          TEXT    NOT NULL,
    status      TEXT    NOT NULL,
    latitude    REAL,
    longitude   REAL,
    note        TEXT
);

-- ===== DỮ LIỆU CHO AI =====
CREATE TABLE search_log (              -- lịch sử tìm kiếm (Data requirement của AI Search)
    log_id         INTEGER PRIMARY KEY,
    customer_id    INTEGER REFERENCES customer(customer_id),
    mode           TEXT NOT NULL CHECK (mode IN ('TEXT','VOICE','IMAGE')),
    query          TEXT,
    top_product_id INTEGER REFERENCES product(product_id),
    ts             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE review (                  -- Customer 1 — 0..* Review — 1 Product
    review_id   INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customer(customer_id),
    product_id  INTEGER NOT NULL REFERENCES product(product_id),
    rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment     TEXT,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_product_category ON product(category_id);
CREATE INDEX idx_orders_customer  ON orders(customer_id);
CREATE INDEX idx_shipping_status  ON shipping(status);
