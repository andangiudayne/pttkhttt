"""HomeController — trang chủ, danh mục, chi tiết sản phẩm (UC03, FR09)."""
from flask import Blueprint, render_template, request, abort
from chobay.model.delivery import spec
from chobay.model.enums import DeliveryMode
from .common import ctx

bp = Blueprint("home", __name__)


@bp.get("/")
def index():
    cat = request.args.get("cat", type=int)
    if cat not in {c.category_id for c in ctx().catalog_service.categories()}:
        cat = None                                              # danh mục lạ trên URL → hiện tất cả, không lỗi 500
    products = ctx().catalog_service.list_products(cat)
    fleet = [spec(m) for m in DeliveryMode]
    return render_template("index.html", products=products, active_cat=cat, fleet=fleet)


@bp.get("/product/<int:pid>")
def product_detail(pid):
    p = ctx().catalog_service.get_product(pid)
    if not p:
        abort(404)
    return render_template("product.html", p=p, fit=ctx().catalog_service.delivery_fit(p),
                           reviews=ctx().catalog_service.reviews(pid))
