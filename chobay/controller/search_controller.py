"""SearchController — nhận text / voice / image từ giao diện, gọi tầng AI, trả kết quả xếp hạng.
Các luồng thay thế khớp biểu đồ hoạt động 3.4: từ khóa không hợp lệ, không nhận dạng được giọng nói,
tệp ảnh lỗi, không có sản phẩm phù hợp. Câu hỏi về đơn hàng (“đơn hàng số 3”, “đơn gần nhất đâu”) → Search Order.
Mỗi lần tìm được ghi vào search_log QUA SearchService — Controller (tầng trình bày) không gọi DAO."""
import base64
import io
from flask import Blueprint, render_template, request
from PIL import Image, ImageOps, UnidentifiedImageError
from .common import ctx, current_customer

bp = Blueprint("search", __name__)
MAX_LEN = 100


def _read_image(file_storage):
    """Kiểm tra tệp ảnh (luồng thay thế 'Ảnh hợp lệ? — không')."""
    try:
        img = Image.open(file_storage.stream)
        img.load()
        return img
    except (UnidentifiedImageError, OSError):
        return None


def _data_uri(img, size=360) -> str:
    """Ảnh thu nhỏ nhúng thẳng vào trang (data URI) để khách thấy ảnh mình vừa tải — KHÔNG lưu xuống đĩa (riêng tư)."""
    im = ImageOps.exif_transpose(img).convert("RGB")
    im.thumbnail((size, size))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _confidence():
    """Độ tin cậy Web Speech API gửi kèm (0–1); không có/không hợp lệ → None (khách gõ tay)."""
    try:
        return float(request.values["conf"])
    except (KeyError, ValueError):
        return None


def validate_keyword(query) -> bool:
    """Từ khóa hợp lệ khi còn ít nhất một từ có nghĩa sau chuẩn hóa, có bộ lọc giá, hoặc là câu hỏi về đơn hàng."""
    return bool(query.tokens) or query.max_price is not None or query.intent == "ORDER"


@bp.route("/search", methods=["GET", "POST"])
def search():
    c = ctx()
    cust = current_customer()
    mode = request.values.get("mode", "TEXT")
    text = request.values.get("q", "").strip()
    query, error, label, upload = None, None, text, None
    if len(text) > MAX_LEN:
        error = f"Từ khóa quá dài (tối đa {MAX_LEN} ký tự)."
    elif mode == "VOICE" and text:
        transcript = c.speech_service.transcribe(text)          # bản phiên âm từ Web Speech API (🎤) → chuẩn hóa
        label = transcript
        query = c.query_service.voice_query(transcript)
        if not c.speech_service.is_confident(_confidence()):
            query, error = None, "Nghe chưa rõ — bạn nói lại gần micro hơn, hoặc sửa văn bản rồi bấm Tìm."
        elif not validate_keyword(query):
            query, error = None, "Không nhận dạng được tên sản phẩm trong câu nói — hãy nói lại hoặc sửa văn bản."
    elif mode == "IMAGE" and "image" in request.files and request.files["image"].filename:
        f = request.files["image"]
        img = _read_image(f)
        if img is None:
            error = "Tệp tải lên không phải ảnh hợp lệ — hãy chọn ảnh JPG hoặc PNG."
        else:
            emb = c.image_service.encode(img)
            upload = {"name": f.filename, "src": _data_uri(img)}
            query = c.query_service.multimodal_query(text, emb) if text else c.query_service.image_query(emb)
            label = f.filename if not text else f"{text} + {f.filename}"
    elif text:
        query = c.query_service.text_query(text)
        if not validate_keyword(query):
            query, error = None, "Từ khóa không hợp lệ — hãy nhập tên sản phẩm, ví dụ “sữa chua dâu”."
    results, orders = [], None
    if query and query.intent == "ORDER":                          # Search Order (A06) → UC09 Xem đơn
        if cust is None:                                           # đơn hàng là dữ liệu riêng → phải đăng nhập (NFR03)
            orders, error = None, "Vui lòng đăng nhập để tìm đơn hàng của bạn."
        else:
            orders = c.search_service.find_orders(query, cust.customer_id)
            c.search_service.log_search(cust.customer_id, query, label, None)
    elif query:
        cands = c.search_service.retrieve(query)                   # Retrieval
        results = c.ranking_service.rank(query, cands, cust.default_address() if cust else None)  # Ranking
        c.search_service.log_search(cust.customer_id if cust else None, query, label,
                                    results[0].product.product_id if results else None)
    recent = c.search_service.recent(cust.customer_id) if cust else []
    return render_template("search.html", results=results, orders=orders, query=query, mode=mode, q=text,
                           error=error, recent=recent, upload=upload)
