"""ImageService — bộ mã hóa ảnh f_θ(I) → vector đặc trưng (Assignment 06, mục 6.3).

f_θ(I) = [ √0.8 · CNN(I) ,  √0.2 · Color(I) ]       (mỗi khối đã chuẩn hóa L2)
  • CNN(I)  : MobileNet v1 tiền huấn luyện ImageNet (1024 chiều), trừ vector trung bình của catalog
  • Color(I): histogram HSV 12×3×3 trên vùng tiền cảnh tách bằng GrabCut (loại nền bàn/tay cầm)
⇒ cos(f(Iq), f(Ip)) = 0.8·cos_CNN + 0.2·cos_Color.
Nếu không có Keras/JAX, dịch vụ tự lùi về Color(I) (fallback)."""
from __future__ import annotations
import os
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[3]
WEIGHTS = ROOT / "models" / "mobilenet_1_0_224_tf_no_top.h5"
MEAN = ROOT / "models" / "catalog_mean.npy"
W_CNN, W_COLOR = 0.8, 0.2


class ImageService:
    def __init__(self):
        self._model = None
        self._mean = np.load(MEAN) if MEAN.exists() else None
        self.backend = "cnn+color"
        try:
            os.environ.setdefault("KERAS_BACKEND", "jax")
            import keras  # noqa: F401
            self._keras = keras
        except Exception:                               # thiếu thư viện → fallback màu sắc
            self._keras, self.backend = None, "color"

    # ---------- CNN ----------
    def _cnn(self, img: Image.Image) -> np.ndarray:
        if self._model is None:
            k = self._keras
            self._model = k.applications.MobileNet(input_shape=(224, 224, 3), include_top=False,
                                                   weights=None, pooling="avg")
            self._model.load_weights(str(WEIGHTS))
        x = np.asarray(ImageOps.fit(img, (224, 224), Image.BILINEAR), dtype=np.float32) / 127.5 - 1
        return self._model.predict(x[None], verbose=0)[0]

    # ---------- màu tiền cảnh ----------
    @staticmethod
    def _grabcut(img: Image.Image):
        """Tách tiền cảnh bằng GrabCut → (ảnh BGR 240px, mặt nạ 0/1)."""
        import cv2
        im = img.copy()
        im.thumbnail((240, 240))
        a = cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)
        h, w = a.shape[:2]
        mask = np.zeros((h, w), np.uint8)
        rect = (int(w * .08), int(h * .08), int(w * .84), int(h * .84))
        cv2.grabCut(a, mask, rect, np.zeros((1, 65)), np.zeros((1, 65)), 4, cv2.GC_INIT_WITH_RECT)
        fg = ((mask == 1) | (mask == 3)).astype(np.uint8)
        if fg.sum() < 0.05 * h * w:
            fg[:] = 1
        return a, fg

    @classmethod
    def _color(cls, img: Image.Image) -> np.ndarray:
        import cv2
        a, fg = cls._grabcut(img)
        hsv = cv2.cvtColor(a, cv2.COLOR_BGR2HSV)
        hist = np.sqrt(cv2.calcHist([hsv], [0, 1, 2], fg, [12, 3, 3], [0, 180, 0, 256, 0, 256]).ravel())
        return hist / (np.linalg.norm(hist) + 1e-9)

    def raw_cnn(self, image: Image.Image | str) -> np.ndarray:
        img = ImageOps.exif_transpose(Image.open(image) if isinstance(image, str) else image).convert("RGB")
        return self._cnn(img)

    def encode(self, image: Image.Image | str) -> list[float]:
        img = ImageOps.exif_transpose(Image.open(image) if isinstance(image, str) else image).convert("RGB")
        color = self._color(img)
        if self._keras is None:
            return color.round(5).tolist()
        z = self._cnn(img)
        if self._mean is not None:
            z = z - self._mean
        z = z / (np.linalg.norm(z) + 1e-9)
        return np.concatenate([np.sqrt(W_CNN) * z, np.sqrt(W_COLOR) * color]).round(5).tolist()

    @staticmethod
    def cosine(a: list[float], b: list[float]) -> float:
        a, b = np.asarray(a), np.asarray(b)
        if a.shape != b.shape:
            return 0.0
        d = np.linalg.norm(a) * np.linalg.norm(b)
        return float(a @ b / d) if d else 0.0
