"""Pixel-accurate renderer shared by preview, clipboard and file export."""
import math
import os
from pathlib import Path
import tempfile

import cv2
import numpy as np
from PIL import Image
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF


def to_array(image):
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    data = np.frombuffer(image.constBits(), np.uint8).reshape(image.height(), image.bytesPerLine())
    return data[:, :image.width() * 4].reshape(image.height(), image.width(), 4).copy()


def from_array(array):
    a = np.ascontiguousarray(array, dtype=np.uint8)
    return QImage(a.data, a.shape[1], a.shape[0], a.strides[0], QImage.Format.Format_RGBA8888).copy()


def draw_annotation(p, layer):
    if not layer.visible or not layer.points:
        return
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setOpacity(layer.opacity * (.32 if layer.tool == "highlight" else 1))
    color = QColor(layer.color)
    pen = QPen(color, layer.width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    points = [QPointF(x, y) for x, y in layer.points]
    rect = layer.bounds()
    if layer.tool in ("pen", "highlight"):
        if len(points) == 1:
            p.drawPoint(points[0])
        else:
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)
            p.drawPath(path)
    elif layer.tool in ("line", "arrow"):
        a, b = points[0], points[-1]
        p.drawLine(a, b)
        if layer.tool == "arrow":
            angle = math.atan2(b.y() - a.y(), b.x() - a.x())
            size = max(14, layer.width * 4)
            head = [b, QPointF(b.x() - size * math.cos(angle - .48), b.y() - size * math.sin(angle - .48)),
                    QPointF(b.x() - size * math.cos(angle + .48), b.y() - size * math.sin(angle + .48))]
            p.setBrush(color)
            p.drawPolygon(QPolygonF(head))
    elif layer.tool == "rect":
        p.drawRect(rect)
    elif layer.tool == "ellipse":
        p.drawEllipse(rect)
    elif layer.tool == "redact":
        p.setOpacity(1)
        p.fillRect(rect, Qt.GlobalColor.black)
    elif layer.tool == "text":
        font = QFont("Segoe UI")
        font.setPixelSize(layer.font_size)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, layer.text)
    elif layer.tool == "number":
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(rect)
        p.setPen(QColor("#101219") if color.lightnessF() > .6 else QColor("white"))
        font = QFont("Segoe UI")
        font.setPixelSize(layer.font_size)
        font.setBold(True)
        p.setFont(font)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(layer.number))
    p.restore()


def render(image, layers):
    result = image.convertToFormat(QImage.Format.Format_RGBA8888).copy()
    result.setDevicePixelRatio(1)
    for layer in layers:
        if not layer.visible:
            continue
        if layer.tool in ("blur", "pixel"):
            region = layer.bounds().toAlignedRect().intersected(result.rect())
            if region.isEmpty():
                continue
            source = to_array(result.copy(region))
            strength = max(1, min(80, int(layer.strength)))
            if layer.tool == "blur":
                # Region-local OpenCV kernel: work scales with the redacted area.
                filtered = cv2.GaussianBlur(source, (0, 0), sigmaX=strength, sigmaY=strength,
                                            borderType=cv2.BORDER_REPLICATE)
            else:
                small = cv2.resize(source, (max(1, region.width() // strength), max(1, region.height() // strength)),
                                   interpolation=cv2.INTER_AREA)
                filtered = cv2.resize(small, (region.width(), region.height()), interpolation=cv2.INTER_NEAREST)
            # Privacy tools always apply at full opacity.
            p = QPainter(result)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            p.drawImage(region.topLeft(), from_array(filtered))
            p.end()
        else:
            p = QPainter(result)
            draw_annotation(p, layer)
            p.end()
    return result


def save_image(image, target, fmt=None, quality=98, webp_lossless=True):
    target = Path(target)
    fmt = (fmt or target.suffix.lstrip(".")).upper()
    if fmt == "JPG":
        fmt = "JPEG"
    if fmt not in ("PNG", "JPEG", "WEBP"):
        raise ValueError("PNG, JPG veya WEBP biçimi seçin.")
    pil = Image.fromarray(to_array(image))
    if fmt == "JPEG":
        bg = Image.new("RGB", pil.size, "white")
        bg.paste(pil, mask=pil.getchannel("A"))
        pil = bg
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".snapforge-", suffix=".tmp", dir=target.parent)
    os.close(fd)
    try:
        quality = max(1, min(100, int(quality)))
        options = ({"quality": quality, "subsampling": 0} if fmt == "JPEG"
                   else {"lossless": bool(webp_lossless), "quality": quality} if fmt == "WEBP" else {})
        pil.save(temp, format=fmt, **options)
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
