"""Make the text scanner's test pages (used in results-2026-11-22.md).

Writes five pages into this folder, plus truth.json with the correct text of
each. The story text is original, written for these tests. Windows fonts are
used: Arial, Georgia, Microsoft JhengHei (正黑體) and DFKai-SB (標楷體).

Usage (from the project folder):
    .venv\\Scripts\\python.exe evaluation\\text-pages\\make_test_pages.py
"""
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
FONTS = Path("C:/Windows/Fonts")
BACKGROUND = (120, 110, 100)


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def add_noise(image, count, strength, seed):
    pixels = image.load()
    random.seed(seed)
    for _ in range(count):
        x, y = random.randrange(image.width), random.randrange(image.height)
        change = random.randint(-strength, strength)
        pixels[x, y] = tuple(max(0, min(255, value + change)) for value in pixels[x, y])


def picture(draw, box, seed):
    """A simple storybook scene: sky, grass, sun and trees."""
    random.seed(seed)
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(170, 215, 240))
    draw.rectangle((x0, y0 + (y1 - y0) * 0.65, x1, y1), fill=(120, 190, 90))
    draw.ellipse((x1 - 170, y0 + 30, x1 - 70, y0 + 130), fill=(250, 210, 60))
    for i in range(5):
        tree_x = x0 + 60 + i * (x1 - x0 - 120) // 4
        draw.rectangle((tree_x - 8, y0 + (y1 - y0) * 0.45, tree_x + 8, y0 + (y1 - y0) * 0.7), fill=(110, 70, 40))
        draw.ellipse((tree_x - 45, y0 + (y1 - y0) * 0.25, tree_x + 45, y0 + (y1 - y0) * 0.52), fill=(60, 140, 60))


def write_lines(draw, lines, x, y, step, pick_font, ink=(40, 35, 30)):
    for line in lines:
        draw.text((x, y), line, fill=ink, font=pick_font(line))
        y += step


def leaflet_page():
    lines = [
        "Take one tablet twice a day after meals.",
        "Do not use after the expiry date.",
        "Keep out of reach of children.",
        "每日兩次，飯後服用一錠。",
        "請放在兒童拿不到的地方。",
    ]
    page = Image.new("RGB", (1200, 700), "white")
    write_lines(ImageDraw.Draw(page), lines, 60, 60, 110,
                lambda line: font("msjh.ttc", 48) if ord(line[0]) > 255 else font("arial.ttf", 44), ink="black")
    return page, "\n".join(lines)


def as_phone_photo(page):
    """Tilted, shadowed, slightly blurry, with sensor noise."""
    photo = Image.new("RGB", (1500, 1100), BACKGROUND)
    photo.paste(page.rotate(4, expand=True, fillcolor=BACKGROUND), (150, 160))
    shade = Image.new("L", photo.size, 0)
    ImageDraw.Draw(shade).polygon([(0, 0), (700, 0), (300, 1100), (0, 1100)], fill=70)
    photo = Image.composite(Image.new("RGB", photo.size, (0, 0, 0)), photo, shade.filter(ImageFilter.GaussianBlur(80)))
    photo = photo.filter(ImageFilter.GaussianBlur(1.2))
    add_noise(photo, 60000, 25, seed=1)
    return photo


def storybook_page(lines, font_name, size, top, step, seed, page_number=None):
    page = Image.new("RGB", (1240, 1700), (253, 248, 235))
    draw = ImageDraw.Draw(page)
    picture(draw, (80, 80, 1160, 760), seed)
    write_lines(draw, lines, 90, top, step, lambda line: font(font_name, size))
    if page_number:
        draw.text((600, 1610), page_number, fill=(90, 80, 70), font=font("georgia.ttf", 34))
    return page


def open_book_photo(lines):
    """Text printed over the picture, photographed in an open book."""
    page = Image.new("RGB", (1240, 1700), (253, 248, 235))
    draw = ImageDraw.Draw(page)
    picture(draw, (0, 0, 1240, 1700), 3)
    write_lines(draw, lines, 80, 1180, 95,
                lambda line: font("kaiu.ttf", 56) if ord(line[0]) > 255 else font("georgia.ttf", 48))
    book = Image.new("RGB", (1500, 1900), (70, 60, 55))
    book.paste(page, (200, 100))
    shade = Image.new("L", book.size, 0)
    ImageDraw.Draw(shade).rectangle((150, 0, 330, 1900), fill=150)  # the fold's shadow
    book = Image.composite(Image.new("RGB", book.size, (0, 0, 0)), book, shade.filter(ImageFilter.GaussianBlur(60)))
    book = book.rotate(-3, expand=True, fillcolor=(70, 60, 55)).filter(ImageFilter.GaussianBlur(1.0))
    add_noise(book, 80000, 20, seed=5)
    return book


def main():
    truth = {}
    leaflet, leaflet_text = leaflet_page()
    leaflet.save(HERE / "ocr-test-page.png")
    as_phone_photo(leaflet).save(HERE / "ocr-phone-photo.jpg", quality=80)
    truth["ocr-test-page.png"] = truth["ocr-phone-photo.jpg"] = leaflet_text

    english = [
        "Once upon a time, a little fox lived",
        "at the edge of a quiet green wood.",
        "Every morning she ran to the river",
        "to say hello to her friend the duck.",
        "\"Good morning, Duck!\" said the fox.",
        "\"Good morning, Fox!\" said the duck.",
    ]
    storybook_page(english, "georgia.ttf", 46, 840, 82, seed=1, page_number="4").save(HERE / "story-en.png")
    truth["story-en.png"] = "\n".join(english)

    chinese = [
        "從前從前，森林的邊上住著一隻小狐狸。",
        "每天早上，她都跑到河邊，",
        "跟她的好朋友小鴨子說早安。",
        "「小鴨子，早安！」小狐狸說。",
        "「小狐狸，早安！」小鴨子說。",
    ]
    storybook_page(chinese, "kaiu.ttf", 56, 850, 100, seed=2).save(HERE / "story-zh.png")
    truth["story-zh.png"] = "\n".join(chinese)

    mixed = [
        "The fox and the duck sat by the river.",
        "They watched the sun go down.",
        "小狐狸和小鴨子坐在河邊，",
        "一起看著太陽下山。",
    ]
    open_book_photo(mixed).save(HERE / "story-photo.jpg", quality=82)
    truth["story-photo.jpg"] = "\n".join(mixed)

    (HERE / "truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {len(truth)} pages and truth.json to {HERE}")


if __name__ == "__main__":
    main()
