"""Builds shared/icons/tray.ico and shared/icons/tray-disabled.ico.

Run once from the repository root: python scripts/build-icons.py
Needs Pillow and the Segoe UI Bold font that ships with Windows.
"""
import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT = pathlib.Path(r"C:\Windows\Fonts\segoeuib.ttf")
SIZES = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (256, 256)]
ENABLED = "#2563EB"
DISABLED = "#9CA3AF"


def render(background):
    size = 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, size - 8, size - 8), radius=48, fill=background)
    font = ImageFont.truetype(str(FONT), 190)
    # ARABIC LETTER AIN, isolated form, which needs no text shaping.
    draw.text((size / 2, size / 2), "\u0639", font=font, fill="white", anchor="mm")
    return image


def main():
    out = ROOT / "shared" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    render(ENABLED).save(out / "tray.ico", sizes=SIZES)
    render(DISABLED).save(out / "tray-disabled.ico", sizes=SIZES)
    print(f"wrote {out / 'tray.ico'} and {out / 'tray-disabled.ico'}")


if __name__ == "__main__":
    main()
