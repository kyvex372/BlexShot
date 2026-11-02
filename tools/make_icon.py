"""Package the supplied BlexShot logo as PNG and multi-resolution ICO."""
from pathlib import Path
from PIL import Image
root = Path(__file__).resolve().parent.parent / "resources"
with Image.open(root / "brand-logo.png") as source:
    image = source.convert("RGBA")
    # Ignore barely visible export speckles when measuring padding; retain the
    # actual logo pixels and alpha, without stretching a landscape asset.
    bounds = image.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if not bounds:
        raise ValueError("Logo is fully transparent.")
    left, top, right, bottom = bounds
    image = image.crop((max(0,left-8), max(0,top-8), min(image.width,right+8), min(image.height,bottom+8)))
    side = max(image.size) + 40
    square = Image.new("RGBA", (side,side), (0,0,0,0))
    square.paste(image, ((side-image.width)//2, (side-image.height)//2))
    image = square
    image.save(root / "app.png")
    image.save(root / "app.ico", sizes=[(16,16),(20,20),(24,24),(32,32),(40,40),(48,48),(64,64),(128,128),(256,256)])
