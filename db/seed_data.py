"""Dữ liệu mẫu ChợBay. Ảnh sản phẩm là ảnh chụp thật (Open Food Facts, Wikimedia Commons) — nguồn từng ảnh ở slide “Nguồn ảnh” và README.
Khách hàng, địa chỉ chi tiết và đội phương tiện là dữ liệu giả lập phục vụ demo."""

CATEGORIES = [
    (1, "Rau củ & trái cây tươi", "rau-cu-trai-cay"),
    (2, "Thịt, cá, trứng & hải sản", "thit-ca-trung"),
    (3, "Hàng đông lạnh", "dong-lanh"),
    (4, "Sữa & chế phẩm sữa", "sua"),
    (5, "Đồ uống", "do-uong"),
    (6, "Mì, gạo & đồ khô", "mi-gao-do-kho"),
    (7, "Gia vị", "gia-vi"),
    (8, "Bánh mì & bánh kẹo", "banh-keo"),
]

# (id, kind, cat, name, brand, price, unit, weight_kg, temp, fragile, liquid, odor, stock, rating, image, extra, keywords, description)
PRODUCTS = [
    (1, "PackagedFood", 6, "Mì Kim Chi Acecook gói 75g", "Acecook", 4500, "gói", 0.08, "AMBIENT", 0, 0, 0, 420, 4.6, "P01.jpg",
     {"barcode": "8934563796150", "expiry_days": 180}, "mi goi mi tom mi an lien kim chi cay han quoc", "Mì ăn liền vị kim chi cay nhẹ."),
    (2, "PackagedFood", 6, "Mì không chiên Mikochi vị sườn heo", "Acecook", 7000, "gói", 0.08, "AMBIENT", 0, 0, 0, 260, 4.5, "P02.jpg",
     {"barcode": "8934563167165", "expiry_days": 180}, "mi goi mi an lien mi tom suon heo khong chien", "Sợi mì không chiên, ít dầu."),
    (3, "PackagedFood", 6, "Bún bò Huế ăn liền Vifon 65g", "Vifon", 5500, "gói", 0.065, "AMBIENT", 0, 0, 0, 310, 4.4, "P03.jpg",
     {"barcode": "8935311140713", "expiry_days": 180}, "bun bo hue an lien goi cay", "Bún ăn liền hương vị bò Huế."),
    (4, "PackagedFood", 6, "Bánh phở khô Phở Story 500g", "Chin-Su", 32000, "gói", 0.5, "AMBIENT", 0, 0, 0, 120, 4.5, "P04.jpg",
     {"barcode": "8936136167992", "expiry_days": 365}, "banh pho kho pho bo nau pho", "Bánh phở khô sợi dẹt để nấu phở tại nhà."),
    (5, "PackagedFood", 6, "Gạo nếp Hoa Vàng Vinaseed túi 2kg", "Vinaseed", 78000, "túi", 2.0, "AMBIENT", 0, 0, 0, 80, 4.7, "P05.jpg",
     {"barcode": "8936089501492", "expiry_days": 365}, "gao nep hoa vang xoi banh chung", "Gạo nếp dẻo thơm, nấu xôi, gói bánh."),
    (6, "Beverage", 4, "Sữa tươi tiệt trùng Vinamilk 100% hộp 1L", "Vinamilk", 36000, "hộp", 1.05, "AMBIENT", 0, 1, 0, 200, 4.8, "P06.jpg",
     {"volume_ml": 1000, "barcode": "8934673576390"}, "sua tuoi sua bo vinamilk hop 1 lit khong duong", "Sữa tươi tiệt trùng nguyên chất."),
    (7, "Beverage", 4, "Thùng 48 hộp sữa tươi Vinamilk 180ml", "Vinamilk", 392000, "thùng", 9.6, "AMBIENT", 0, 1, 0, 45, 4.9, "P07.jpg",
     {"volume_ml": 8640, "barcode": "8934673573344"}, "sua tuoi thung sua hop nho vinamilk co duong", "Thùng 48 hộp 180ml — hàng nặng."),
    (8, "PackagedFood", 4, "Sữa chua dâu Vinamilk lốc 4 hộp", "Vinamilk", 26000, "lốc", 0.42, "CHILLED", 0, 0, 0, 150, 4.6, "P08.jpg",
     {"barcode": "8934673607827", "expiry_days": 30}, "sua chua yaourt dau vinamilk", "Sữa chua ăn vị dâu — bảo quản mát."),
    (9, "PackagedFood", 4, "Sữa đặc Ngôi Sao Phương Nam 380g", "Vinamilk", 25000, "hộp", 0.4, "AMBIENT", 0, 0, 0, 180, 4.7, "P09.jpg",
     {"barcode": "8934673218368", "expiry_days": 365}, "sua dac ngoi sao phuong nam lon pha che", "Sữa đặc pha cà phê sữa đá."),
    (10, "Beverage", 5, "Nước dừa Vietcoco hộp 330ml", "Vietcoco", 19000, "hộp", 0.36, "AMBIENT", 0, 1, 0, 140, 4.4, "P10.jpg",
     {"volume_ml": 330, "barcode": "8936079561833"}, "nuoc dua sua dua do uong", "Thức uống từ dừa Bến Tre."),
    (11, "PackagedFood", 5, "Cà phê G7 3in1 bịch 22 gói", "Trung Nguyên", 69000, "bịch", 0.4, "AMBIENT", 0, 0, 0, 95, 4.6, "P11.jpg",
     {"barcode": "8935024143360", "expiry_days": 365}, "ca phe sua hoa tan g7 3 in 1 trung nguyen", "Cà phê hòa tan 3 trong 1."),
    (12, "PackagedFood", 7, "Tương ớt Chin-su chai 250g", "Chin-Su", 15000, "chai", 0.28, "AMBIENT", 0, 1, 0, 230, 4.6, "P12.jpg",
     {"barcode": "8936017363505", "expiry_days": 365}, "tuong ot chinsu chin su sot ot cay", "Tương ớt cay nồng."),
    (13, "PackagedFood", 8, "Bánh mì tươi Kinh Đô bơ sữa 55g", "Kinh Đô", 8000, "cái", 0.055, "AMBIENT", 0, 0, 0, 90, 4.3, "P13.jpg",
     {"barcode": "8934680042567", "expiry_days": 7}, "banh mi tuoi bo sua kinh do an sang", "Bánh mì mềm ăn sáng."),
    (14, "FrozenFood", 3, "Kem que sầu riêng hộp 4 que", "Bích Hà", 45000, "hộp", 0.3, "FROZEN", 0, 0, 1, 60, 4.5, "P14.jpg",
     {"storage_temp_c": -18}, "kem que sau rieng kem lanh", "Kem que vị sầu riêng — đông lạnh, mùi mạnh."),
    (15, "FrozenFood", 3, "Cá basa phi lê đông lạnh 1kg", "Mekong Seafood", 89000, "túi", 1.0, "FROZEN", 0, 0, 0, 70, 4.4, "P15.jpg",
     {"storage_temp_c": -18}, "ca basa phi le ca tra dong lanh", "Phi lê cá basa cấp đông IQF."),
    (16, "FreshFood", 1, "Thanh long ruột trắng 1kg", "Nông trại Bình Thuận", 32000, "kg", 1.0, "AMBIENT", 0, 0, 0, 110, 4.6, "P16.jpg",
     {"origin": "Bình Thuận", "shelf_life_hours": 120}, "thanh long trai cay hoa qua dragon fruit", "Thanh long tươi hái trong ngày."),
    (17, "FreshFood", 1, "Sầu riêng Ri6 nguyên trái (~2,6kg)", "Vườn Cái Mơn", 245000, "trái", 2.6, "AMBIENT", 0, 0, 1, 25, 4.8, "P17.jpg",
     {"origin": "Cái Mơn, Bến Tre", "shelf_life_hours": 72}, "sau rieng ri6 trai cay durian", "Sầu riêng Ri6 cơm vàng — mùi rất mạnh."),
    (18, "FreshFood", 1, "Rau muống 500g", "HTX Củ Chi", 12000, "bó", 0.5, "CHILLED", 0, 0, 0, 150, 4.3, "P18.jpg",
     {"origin": "Củ Chi, TP.HCM", "shelf_life_hours": 36}, "rau muong rau xanh rau an", "Rau muống sạch, giữ mát."),
    (19, "FreshFood", 2, "Trứng gà vỉ 10 quả", "Trang trại Đồng Nai", 33000, "vỉ", 0.65, "AMBIENT", 1, 0, 0, 200, 4.6, "P19.jpg",
     {"origin": "Đồng Nai", "shelf_life_hours": 336}, "trung ga trung tuoi vi 10", "Trứng gà tươi — hàng dễ vỡ."),
    (20, "FreshFood", 2, "Tôm sú tươi 500g", "Cà Mau Seafood", 165000, "khay", 0.55, "CHILLED", 0, 0, 0, 40, 4.7, "P20.jpg",
     {"origin": "Cà Mau", "shelf_life_hours": 24}, "tom su tom tuoi hai san", "Tôm sú tươi — giữ lạnh 0–4 °C."),
    (21, "FreshFood", 2, "Thịt ba chỉ heo 500g", "Trang trại Đồng Nai", 78000, "khay", 0.5, "CHILLED", 0, 0, 0, 60, 4.5, "P21.jpg",
     {"origin": "Đồng Nai", "shelf_life_hours": 48}, "thit ba chi thit heo ba roi", "Thịt ba chỉ tươi — giữ lạnh."),
    (22, "FreshFood", 1, "Xoài cát Hòa Lộc 1kg", "Vườn Cái Bè", 75000, "kg", 1.0, "AMBIENT", 0, 0, 0, 85, 4.7, "P22.jpg",
     {"origin": "Cái Bè, Tiền Giang", "shelf_life_hours": 96}, "xoai cat hoa loc trai cay mango", "Xoài cát Hòa Lộc chín cây."),
]

CUSTOMERS = [
    # id, first, last, email, phone, type, points
    (1, "Minh Anh", "Nguyễn", "minhanh@example.com", "0901000001", "VIP", 1250),
    (2, "Gia Bảo", "Trần", "giabao@example.com", "0901000002", "NEW", 0),
    (3, "Thu Hà", "Lê", "thuha@example.com", "0901000003", "REGULAR", 310),
    (4, "Quốc Huy", "Phạm", "quochuy@example.com", "0901000004", "REGULAR", 90),
    (5, "Thanh Tùng", "Võ", "thanhtung@example.com", "0901000005", "VIP", 2200),
    # khách có lịch sử mua hàng (db/seed_history.py sinh đơn đã giao trong 3 tuần gần đây)
    (6, "Bảo Ngọc", "Hoàng", "baongoc@example.com", "0901000006", "REGULAR", 420),
    (7, "Minh Quân", "Đặng", "minhquan@example.com", "0901000007", "VIP", 1880),
    (8, "Khánh Linh", "Bùi", "khanhlinh@example.com", "0901000008", "REGULAR", 260),
    (9, "Gia Huy", "Huỳnh", "giahuy@example.com", "0901000009", "REGULAR", 150),
    (10, "Thảo Vy", "Ngô", "thaovy@example.com", "0901000010", "REGULAR", 540),
    (11, "Đức Anh", "Trương", "ducanh@example.com", "0901000011", "REGULAR", 75),
    (12, "Mỹ Duyên", "Lý", "myduyen@example.com", "0901000012", "REGULAR", 330),
    (13, "Hoài Nam", "Phan", "hoainam@example.com", "0901000013", "VIP", 2600),
    (14, "Ngọc Hân", "Đỗ", "ngochan@example.com", "0901000014", "REGULAR", 210),
    (15, "Tiến Dũng", "Mai", "tiendung@example.com", "0901000015", "REGULAR", 95),
]

STAFF = [
    # id, full_name, role, username — mật khẩu demo chung "chobay123"
    (1, "Đỗ Minh Khang", "DISPATCHER", "dieuphoi"),
]

ADDRESSES = [
    # id, cust, label, street, ward, district, city, lat, lon, area, drop_zone, vertiport_km
    (1, 1, "Căn hộ", "Tòa S2, 15 Nguyễn Hữu Thọ", "Phước Kiển", "Nhà Bè", "TP.HCM", 10.7130, 106.7050, "URBAN_HIGHRISE", 1, 0.6),
    (2, 2, "Nhà phố", "42 Lê Thánh Tôn", "Bến Nghé", "Quận 1", "TP.HCM", 10.7769, 106.7009, "URBAN_STREET", 0, 2.4),
    (3, 3, "Nhà trên đảo", "Ấp Thạnh Hòa", "Xã Thạnh An", "Cần Giờ", "TP.HCM", 10.5260, 106.9750, "ISLAND", 0, 99),
    (4, 4, "Nhà ven sông", "Bến số 3, An Phú Đông", "An Phú Đông", "Quận 12", "TP.HCM", 10.8590, 106.7040, "RIVERSIDE", 1, 6.5),
    (5, 5, "Biệt thự", "Khu dân cư Chánh Nghĩa", "Chánh Nghĩa", "Thủ Dầu Một", "Bình Dương", 10.9800, 106.6500, "SUBURBAN", 1, 0.8),
    (6, 6, "Nhà phố", "118 Võ Văn Tần", "Võ Thị Sáu", "Quận 3", "TP.HCM", 10.7797, 106.6869, "URBAN_STREET", 0, 3.1),
    (7, 7, "Căn hộ", "Tòa B, Vinhomes Grand Park", "Long Thạnh Mỹ", "Thủ Đức", "TP.HCM", 10.8420, 106.8380, "URBAN_HIGHRISE", 1, 1.8),
    (8, 8, "Nhà ven sông", "25 Bình Quới", "Phường 28", "Bình Thạnh", "TP.HCM", 10.8150, 106.7300, "RIVERSIDE", 1, 4.0),
    (9, 9, "Căn hộ", "Sunrise City, 23 Nguyễn Hữu Thọ", "Tân Hưng", "Quận 7", "TP.HCM", 10.7395, 106.7010, "URBAN_HIGHRISE", 1, 0.9),
    (10, 10, "Nhà phố", "64 Phan Văn Trị", "Phường 10", "Gò Vấp", "TP.HCM", 10.8300, 106.6790, "URBAN_STREET", 0, 2.2),
    (11, 11, "Nhà trên đảo", "Ấp Thiềng Liềng", "Xã Thạnh An", "Cần Giờ", "TP.HCM", 10.5410, 106.9620, "ISLAND", 0, 99),
    (12, 12, "Nhà vườn", "Ấp 3, Hiệp Phước", "Hiệp Phước", "Nhà Bè", "TP.HCM", 10.6560, 106.7480, "SUBURBAN", 1, 2.5),
    (13, 13, "Căn hộ", "The Nassim, 23 Song Hành", "An Phú", "Thủ Đức", "TP.HCM", 10.8005, 106.7440, "URBAN_HIGHRISE", 1, 1.2),
    (14, 14, "Nhà phố", "Đường Lê Hồng Phong", "Phú Hòa", "Thủ Dầu Một", "Bình Dương", 10.9720, 106.6650, "SUBURBAN", 1, 1.0),
    (15, 15, "Nhà ven sông", "Bến Hiệp Thành", "Hiệp Thành", "Quận 12", "TP.HCM", 10.8780, 106.6980, "RIVERSIDE", 1, 5.5),
]

HUBS = [
    # id, name, type, lat, lon, transfer_min
    (1, "Kho tối ChợBay Quận 7", "DARK_STORE", 10.7340, 106.7220, 0),
    (2, "Drone port Thủ Đức", "DRONE_PORT", 10.8500, 106.7720, 25),
    (3, "Vertiport Tân Bình", "VERTIPORT", 10.8000, 106.6600, 25),
    (4, "Cảng tàu ngầm Cần Giờ", "SEA_DOCK", 10.4110, 106.9550, 70),
    (5, "Bến xuồng Thanh Đa", "RIVER_DOCK", 10.8150, 106.7180, 20),
]

# id, mode, hub, code, status, battery
VEHICLES = [
    (1, "DRONE", 1, "DR-07", "IDLE", 92), (2, "DRONE", 2, "DR-12", "IDLE", 88),
    (3, "ROBOT", 1, "RB-03", "IDLE", 100), (4, "ROBOT", 2, "RB-09", "IDLE", 76),
    (5, "AUTO_CAR", 1, "AV-01", "IDLE", 81), (6, "AUTO_CAR", 2, "AV-02", "IDLE", 95),
    (7, "FLYING_CAR", 3, "FC-01", "IDLE", 97),
    (8, "SUBMARINE", 4, "SB-01", "IDLE", 90),
    (9, "AUTO_BOAT", 5, "BT-02", "IDLE", 85),
    (10, "EBIKE", 1, "EB-21", "IDLE", 100), (11, "EBIKE", 2, "EB-34", "IDLE", 100),
    (12, "LOCKER", 1, "LK-Q7-05", "IDLE", 100),
]
