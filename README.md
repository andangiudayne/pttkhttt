# ChợBay — prototype tiểu luận PTTK HTTT (Lớp 04)

Tạp hóa online với **AI Search đa phương thức** (chữ, giọng nói, hình ảnh) và **AI điều phối giao hàng** 8 phương thức
(drone, robot vỉa hè, xe tự lái, ô tô bay, tàu ngầm, xuồng tự hành, xe máy điện, tủ khóa).

## Yêu cầu môi trường

- Python **3.11 trở lên** (đã chạy trên 3.13); thư viện chính: Flask 3.1, scikit-learn 1.9, Keras 3 + JAX (CPU), OpenCV, NumPy, Pillow, pytest — xem `requirements.txt`.
- Không cần GPU. Lần chạy đầu Keras nạp MobileNet từ `models/mobilenet_1_0_224_tf_no_top.h5` (có sẵn trong thư mục).

## Chạy thử

```bash
pip install -r requirements.txt
export KERAS_BACKEND=jax          # Windows PowerShell: $env:KERAS_BACKEND="jax"
python -m db.init_db              # tạo 28 bảng, nạp dữ liệu mẫu (22 sản phẩm, 15 khách, 120 đơn đã giao…), lập vector ảnh
python run.py                     # mở http://127.0.0.1:5000
python demo_ai.py                 # số liệu chương 3: 16 truy vấn sản phẩm + 2 truy vấn đơn hàng, 7 kịch bản giao (chạy trên bản sao CSDL)
pytest -q                         # 37 ca kiểm thử (TC01–TC37), không cần mạng
```

Chạy lại `python -m db.init_db` trước mỗi buổi demo để CSDL về đúng dữ liệu mẫu (phương tiện đều rảnh, tồn kho như ban đầu).

## Dữ liệu mẫu có sẵn

`python -m db.init_db` tự sinh đầy đủ dữ liệu, không cần nhập tay (random cố định nên lần nào cũng ra cùng một bộ):

| Dữ liệu | Số lượng | Nguồn |
|---|---|---|
| Danh mục / sản phẩm | 8 / 22 (ảnh thật, tồn kho, khối lượng, bảo quản) | `db/seed_data.py` |
| Khách hàng / địa chỉ | 15 / 15 (4 VIP, 1 khách mới; phố, chung cư, ven sông, ngoại thành, đảo) | `db/seed_data.py` |
| Điều phối viên · hub · phương tiện | 1 · 5 · 12 xe thuộc 8 loại | `db/seed_data.py` |
| Đơn hàng đã giao (3 tuần gần nhất) | 120 đơn · 285 dòng hàng · 120 thanh toán (tiền mặt, thẻ, ví) · 120 chuyến giao · 480 sự kiện hành trình | `db/seed_history.py` |
| Đánh giá sản phẩm | 125 (chỉ từ khách đã mua món đó) | `db/seed_history.py` |
| Lịch sử tìm kiếm `search_log` | 160 lượt (chữ, giọng nói, ảnh) | `db/seed_history.py` |

Đơn lịch sử được tạo bằng chính các lớp nghiệp vụ (CartService → OrderService.checkout → DeliveryDispatcher → duyệt UC15 → giao),
nên quyết định AI, phí, ETA, lý do chọn đều là kết quả thật; sau đó chỉ lùi mốc thời gian về quá khứ.
Khách `giabao` không có đơn cũ để còn voucher chào mừng khi demo.
Bản CSV của từng bảng (mở bằng Excel) nằm ở `docs/data/` — tạo lại bằng `python -m db.export_csv`.

## Thời tiết tự động (UC20, FR28)

Khi chạy web, `OpenMeteoWeatherService` tự lấy thời tiết từ [Open-Meteo](https://open-meteo.com) (miễn phí, không cần khóa API)
**theo tọa độ địa chỉ giao của từng đơn**, lưu đệm 15 phút; AI dùng số liệu này ở mỗi lần đề xuất cách giao (luật BR-D06).
Không ai phải nhập tay. Máy không có mạng: trang Thời tiết báo “Không kết nối được dịch vụ dự báo” và hệ thống dùng số liệu dự phòng.
Muốn chạy hoàn toàn không mạng (như khi kiểm thử): đặt biến môi trường `CHOBAY_WEATHER=stub` trước `python run.py`.

## Tài khoản mẫu (UC01 Đăng nhập)

Mật khẩu của mọi tài khoản: `chobay123` (lưu dạng băm PBKDF2-SHA256).

| Tên đăng nhập | Vai trò | Địa chỉ giao |
|---|---|---|
| `minhanh` | Khách VIP · có lịch sử đơn | Chung cư · Nhà Bè (drone giao được) |
| `giabao` | Khách mới (voucher 20.000đ) | Nhà phố · Quận 1 |
| `thuha` | Khách hàng | Xã đảo Thạnh An · Cần Giờ (tàu ngầm, cần duyệt) |
| `quochuy` | Khách hàng | Ven sông · Quận 12 |
| `thanhtung` | Khách VIP | Ngoại thành · Thủ Dầu Một |
| `baongoc`, `minhquan`, `khanhlinh`, `giahuy`, `thaovy`, `ducanh`, `myduyen`, `hoainam`, `ngochan`, `tiendung` | Khách có lịch sử mua | Quận 3, Thủ Đức, Bình Thạnh, Quận 7, Gò Vấp, đảo Thạnh An, Nhà Bè, Thủ Đức, Thủ Dầu Một, Quận 12 |
| `dieuphoi` | Điều phối viên | — vào **Kênh điều phối** `/dispatch` |

Khi demo nên mở hai cửa sổ trình duyệt (một cửa sổ ẩn danh): một cho khách, một cho điều phối viên.

## Luồng chính trên web

- **Khách**: tìm bằng chữ / 🎤 giọng nói / 📷 ảnh → giỏ hàng → **thanh toán kiểu sàn TMĐT**: địa chỉ nhận hàng, danh sách sản phẩm,
  phương thức vận chuyển (AI chọn sẵn kèm lý do, khung giờ nhận hàng, phí; khách bấm “Đổi cách giao” để chọn cách hợp lệ khác),
  ưu đãi tự áp dụng (VIP / voucher khách mới), thanh toán khi nhận hàng · thẻ · ví điện tử → trang **Đặt hàng thành công**.
  **Đơn mua** `/orders`: mọi đơn của khách theo tab (Chờ xác nhận, Đang giao, Đã giao), “Mua lại” (UC04.1: thêm **cả đơn** vào giỏ, số lượng theo tồn kho, món hết hàng được báo lại; `POST /order/{id}/reorder`, `OrderService.reorder()`), “Xem chi tiết”.
  Trang sản phẩm có **Đánh giá sản phẩm**: điểm trung bình, phân bố sao, nhận xét mới nhất của người đã mua.
- **Điều phối viên** — **Kênh điều phối** (giao diện riêng, giống kênh người bán của sàn TMĐT):
  - *Quản lý chuyến giao* `/dispatch`: ô tổng quan (chờ duyệt, chờ xuất phát, đã giao, phương tiện rảnh), tab lọc theo trạng thái,
    ô tìm mã đơn / tên khách, phân trang 15 chuyến/trang, nút **Duyệt chuyến** (UC15, BR-H1) và **Cho xuất phát** ngay trên từng dòng;
  - *Chi tiết chuyến* `/dispatch/<mã đơn>`: quyết định của AI (phương thức, điểm, độ tin cậy, lý do), bản đồ và hành trình, khách, hàng trong đơn;
  - *Đội phương tiện* `/dispatch/fleet`: 12 xe theo hub, rảnh / đang chạy, pin (UC17);
  - *Thời tiết (UC20)* `/dispatch/weather`: **tự động theo dự báo Open-Meteo** (mưa, gió hiện tại + dự báo 6 giờ tới, drone / ô tô bay bay được không);
    chỉ khi diễn tập bão hay có sự cố mới bấm *Ghi đè thủ công*, xong bấm *Về tự động* (BR-D06).
- Truy vấn mẫu: `sua chua dau` · `sữa tươi dưới 40k` · nói `tìm giúp mình kem sầu riêng nha` · ảnh trong `tests/query_images/` ·
  `đơn hàng gần nhất` hoặc nói `đơn hàng gần nhất của mình đâu rồi` (cần đăng nhập).

## Cấu trúc

| Thư mục | Nội dung |
|---|---|
| `chobay/model` | 35 lớp + 8 enum (Customer, Staff, Product, Review, Cart, Order, Shipping, 8 lớp DeliveryVehicle…) |
| `chobay/dao`, `chobay/dao/impl` | 8 interface DAO và 8 lớp cài đặt SQLite (StaffDAO cho tài khoản nhân viên, SearchLogDAO cho lịch sử tìm kiếm) |
| `chobay/service` | Catalog, Customer, Auth (đăng nhập), Cart, Order (checkout trong 1 giao dịch), Payment, Shipping, Weather (IWeatherService · OpenMeteoWeatherService tự động · WeatherStub cho kiểm thử) |
| `chobay/ai/search` | QueryService, SpeechService, ImageService (MobileNet), SearchService (sản phẩm + đơn hàng + search_log), RankingService |
| `chobay/ai/delivery` | DeliveryDispatcher, ConstraintChecker (BR-D01…D11), EtaPredictor, RiskPredictor |
| `chobay/controller`, `chobay/view` | 6 Blueprint Flask (Home, Account, Search, Cart, Order, Dispatch) + 17 template Jinja2 — controller chỉ gọi service/AI, không gọi DAO (TC15) |
| `db` | schema.sql (28 bảng), seed_data.py (danh mục), seed_history.py (đơn, đánh giá, tìm kiếm), init_db.py, export_csv.py |
| `tests` | test_chobay.py (TC01–TC37), conftest.py (tắt gọi mạng), ảnh truy vấn thử |
| `docs/data` | Dữ liệu mẫu dạng CSV, mỗi bảng một tệp |
| `docs/diagrams` | Toàn bộ biểu đồ trong slide (PNG + SVG) để vẽ lại bằng Visual Paradigm nếu cần |

## Lệnh thường dùng

| Lệnh | Việc |
|---|---|
| `python -m db.init_db` | Tạo lại 28 bảng + dữ liệu mẫu (kể cả 120 đơn lịch sử) + vector ảnh (~30 giây) |
| `python -m db.export_csv` | Xuất dữ liệu ra `docs/data/*.csv` |
| `python run.py` | Chạy web tại http://127.0.0.1:5000 |
| `python demo_ai.py` | In số liệu đánh giá AI, ghi `docs/demo_results.json` |
| `pytest -q` | 37 ca kiểm thử |

## Hạn chế của prototype

- Chưa có trang đăng ký tài khoản (tài khoản mẫu tạo sẵn); chưa chống CSRF; khóa phiên mặc định `chobay-dev` — triển khai thật đặt biến môi trường `CHOBAY_SECRET`.
- Giọng nói dùng Web Speech API của trình duyệt (Chrome/Edge, cần mạng; Firefox chưa hỗ trợ → gõ câu nói và chọn “Giọng nói”).
- Cổng thanh toán, đội phương tiện là stub. Thời tiết lấy thật từ Open-Meteo (cần Internet); mất mạng thì dùng số liệu gần nhất, chưa có thì mưa 0, gió 3 và tự thử lại sau 5 phút.
- Mô hình ETA/rủi ro học từ 6.000 chuyến mô phỏng; mỗi sản phẩm có 1 ảnh tham chiếu (tìm bằng ảnh đúng 4/6 ở top-1).
- Fallback chỉ bắt lỗi ngoại lệ của mô hình, chưa có giới hạn thời gian (timeout) cho lời gọi AI.

## Ghi chú

- ChợBay là doanh nghiệp giả định. Khách hàng, địa chỉ, đơn lịch sử, đánh giá và lịch sử tìm kiếm là dữ liệu giả lập; thông số phương tiện là giả định thiết kế; dữ liệu huấn luyện ETA/rủi ro là 6.000 chuyến mô phỏng.
- Cổng thanh toán là stub. Thẻ thử: `4242 4242 4242 4242` (thành công), `4000 0000 0000 0002` (ngân hàng từ chối), hạn `12/30`, CVV `123`.
  Số thẻ được kiểm tra bằng thuật toán Luhn, hạn dùng và CVV; CSDL chỉ lưu 4 số cuối (NFR03).
- Ảnh sản phẩm: Open Food Facts (CC BY-SA 3.0) và Wikimedia Commons — nguồn từng ảnh ở slide cuối; trang sản phẩm ghi nguồn dưới ảnh.
- Dữ liệu thời tiết: [Open-Meteo.com](https://open-meteo.com) (CC BY 4.0) — trang Thời tiết của Kênh điều phối ghi nguồn.


## Ghi chú hành vi (khớp phân tích thiết kế)
- **Mua lại (UC04.1)**: sơ đồ tuần tự `docs/diagrams/4_seq_reorder.png`; kiểm thử TC36.
- **“+ Giỏ”** gửi nền (JSON) nên giữ nguyên kết quả tìm kiếm, số trên “Giỏ” tự tăng; giỏ có nút **Xóa** từng món; kiểm thử TC37.
- Dữ liệu lạ trên URL/form không gây lỗi 500: danh mục không tồn tại → hiện tất cả; trang Thời tiết chỉ nhận mưa 0–100 mm/h, gió 0–40 m/s (sai → báo lỗi, không đổi thời tiết).
