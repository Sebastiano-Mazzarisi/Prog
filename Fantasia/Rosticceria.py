# Nome.py: Rosticceria.py
# Data e ora ultima modifica: 02/09/2026 10:19
# Descrizione: Estrae e pubblica i menu e le foto delle rosticcerie Fantasia, Cibarìa e Pane&Co da Facebook e web.
# File di input: cookies.txt
# File di output: status.json, index.html, immagini jpg
# Parametri: --once, --show, --no-git

import io
import json
import os
import re
import subprocess
import sys
import time
import argparse
import datetime
import html
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional

import requests
from PIL import Image, ImageDraw, ImageFont

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Manca Playwright. Installa con: pip install playwright")
    print("Poi esegui: playwright install chromium")
    sys.exit(1)


FACEBOOK_PAGES = [
    {
        "name": "Fantasia",
        "url": "https://www.facebook.com/RosticceriaFantasia",
        "output_image": "Rosticceria_Fantasia.jpg",
    },
    {
        "name": "Cibarìa",
        "url": "https://www.facebook.com/cibaria.asporto",
        "output_image": "Rosticceria_Cibaria.jpg",
    },
]
PANECO_PAGE = {
    "name": "Pane&Co",
    "url": "https://www.paneeco.it/menu",
}
COOKIE_FILE = "cookies.txt"
PUBLISH_DIR = os.path.join("output", "rosticceria_ios")
RUN_START = datetime.time(9, 0)
RUN_END = datetime.time(12, 0)
RUN_INTERVAL_MINUTES = 1
ITALIAN_MONTHS = {
    "gennaio": 1,
    "gen": 1,
    "febbraio": 2,
    "feb": 2,
    "marzo": 3,
    "mar": 3,
    "aprile": 4,
    "apr": 4,
    "maggio": 5,
    "mag": 5,
    "giugno": 6,
    "giu": 6,
    "luglio": 7,
    "lug": 7,
    "agosto": 8,
    "ago": 8,
    "settembre": 9,
    "set": 9,
    "ottobre": 10,
    "ott": 10,
    "novembre": 11,
    "nov": 11,
    "dicembre": 12,
    "dic": 12,
}
# Cookie che compaiono solo dopo un login Facebook riuscito. Se mancano,
# stiamo navigando come visitatori anonimi e Facebook mostra molte meno
# informazioni (spesso senza data/ora del post).
FACEBOOK_LOGIN_COOKIE_NAMES = {"c_user", "xs"}


def script_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def load_facebook_cookies(cookie_path: str) -> List[Dict]:
    if not os.path.exists(cookie_path):
        return []

    cookies = []
    with open(cookie_path, "r", encoding="utf-8") as cookie_file:
        for line in cookie_file:
            if not line.strip() or line.startswith("#"):
                continue

            parts = line.rstrip("\n").split("\t")
            if len(parts) != 7:
                continue

            domain, _include_subdomains, path, secure, expires, name, value = parts
            if "facebook.com" not in domain:
                continue

            try:
                expires_value = int(float(expires))
            except ValueError:
                expires_value = -1

            cookies.append(
                {
                    "domain": domain,
                    "path": path or "/",
                    "secure": secure.upper() == "TRUE",
                    "expires": expires_value,
                    "name": name,
                    "value": value,
                    "httpOnly": False,
                    "sameSite": "Lax",
                }
            )

    return cookies


def clean_post_text(text: str) -> str:
    lines = []
    blocked = {
        "Mi piace",
        "Commenta",
        "Condividi",
        "Invia",
        "Tutti",
        "Piu pertinenti",
        "Più pertinenti",
    }

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line in blocked:
            continue
        if (
            line.startswith("Foto di ")
            or line.startswith("Rosticceria Fantasia")
            or line.startswith("Cibaria")
        ):
            continue
        lines.append(line)

    return "\n".join(lines).strip()


def menu_date_line_from_text(text: str) -> str:
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not re.search(r"\bmenu\b|\bmenù\b", line, re.IGNORECASE):
            continue
        if infer_date_from_text(line):
            return line

    return ""


def best_text_from_post(post) -> str:
    try:
        full_text = clean_post_text(post.inner_text(timeout=3000))
        menu_date_line = menu_date_line_from_text(full_text)
        if menu_date_line:
            return menu_date_line
    except Exception:
        full_text = ""

    message_selectors = [
        'div[data-ad-preview="message"] span[dir="auto"]',
        'div[data-ad-preview="message"] div[dir="auto"]',
        'div[data-ad-comet-preview="message"] span[dir="auto"]',
        'div[data-ad-comet-preview="message"] div[dir="auto"]',
    ]

    for selector in message_selectors:
        try:
            text_parts = []
            for element in post.locator(selector).all():
                if element.is_visible(timeout=1000):
                    text_parts.append(element.inner_text(timeout=3000))
            text = clean_post_text("\n".join(text_parts))
            if text:
                menu_date_line = menu_date_line_from_text(text)
                if menu_date_line:
                    return menu_date_line
                return text
        except Exception:
            pass

    try:
        text_parts = []
        seen = set()
        for element in post.locator('div[dir="auto"], span[dir="auto"]').all():
            if not element.is_visible(timeout=500):
                continue
            text = element.inner_text(timeout=1000).strip()
            if text and text not in seen:
                seen.add(text)
                text_parts.append(text)
        text = clean_post_text("\n".join(text_parts))
        if text:
            menu_date_line = menu_date_line_from_text(text)
            if menu_date_line:
                return menu_date_line
            return text
    except Exception:
        pass

    return full_text


def best_published_time_from_post(post) -> str:
    selectors = [
        "time",
        "abbr",
        'a[aria-label]',
        'span[aria-label]',
        'a[href*="/posts/"]',
        'a[href*="story_fbid"]',
        'a[href*="/permalink/"]',
        'a[role="link"]',
        'span',
    ]

    candidates = []
    for selector in selectors:
        try:
            for element in post.locator(selector).all():
                for attribute in ("title", "aria-label", "datetime", "href"):
                    value = element.get_attribute(attribute)
                    if value:
                        candidates.append(value.strip())

                try:
                    text = element.inner_text(timeout=1000).strip()
                except Exception:
                    text = ""
                if text:
                    candidates.append(text)
        except Exception:
            pass

    try:
        text = post.inner_text(timeout=3000)
        candidates.extend(line.strip() for line in text.splitlines()[:10] if line.strip())
    except Exception:
        pass

    seen = set()
    for value in candidates:
        compact = re.sub(r"\s+", " ", value).strip()
        if not compact or compact in seen:
            continue
        seen.add(compact)
        if looks_like_facebook_time(compact):
            return compact

    return ""


def rome_now() -> datetime.datetime:
    return datetime.datetime.now(ZoneInfo("Europe/Rome"))


def normalize_facebook_time(value: str) -> str:
    value = value.strip()
    if not value:
        return ""

    lower_value = value.lower()
    now = rome_now()

    match = re.search(r"\d{4}-\d{2}-\d{2}(?:[t ][0-9:.+-]+)?", lower_value)
    if match:
        raw_iso = match.group(0)
        try:
            published = datetime.datetime.fromisoformat(raw_iso.replace("z", "+00:00"))
            if published.tzinfo:
                published = published.astimezone(ZoneInfo("Europe/Rome"))
            return published.strftime("%d/%m/%Y %H:%M")
        except ValueError:
            pass

    if lower_value.startswith(("oggi", "today")):
        match = re.search(r"(\d{1,2})[:.](\d{2})", lower_value)
        if match:
            published = now.replace(hour=int(match.group(1)), minute=int(match.group(2)), second=0, microsecond=0)
            return published.strftime("%d/%m/%Y %H:%M")
        return now.strftime("%d/%m/%Y circa")

    match = re.search(r"(\d+)\s*(min|m|minuti)", lower_value)
    if match:
        minutes = int(match.group(1))
        return (now - datetime.timedelta(minutes=minutes)).strftime("%d/%m/%Y %H:%M circa")

    match = re.search(r"(\d+)\s*(h|ore?|ora|hours?)", lower_value)
    if match:
        hours = int(match.group(1))
        return (now - datetime.timedelta(hours=hours)).strftime("%d/%m/%Y %H:%M circa")

    match = re.search(r"(\d+)\s*(g|gg|giorno|giorni|d|days?)", lower_value)
    if match:
        days = int(match.group(1))
        return (now - datetime.timedelta(days=days)).strftime("%d/%m/%Y circa")

    match = re.search(r"(\d+)\s*(sett|settiman[ae]|settimane|w|weeks?)", lower_value)
    if match:
        weeks = int(match.group(1))
        return (now - datetime.timedelta(weeks=weeks)).strftime("%d/%m/%Y circa")

    if lower_value.startswith(("ieri", "yesterday")):
        published = now - datetime.timedelta(days=1)
        match = re.search(r"(\d{1,2})[:.](\d{2})", lower_value)
        if match:
            published = published.replace(hour=int(match.group(1)), minute=int(match.group(2)), second=0, microsecond=0)
        return published.strftime("%d/%m/%Y %H:%M")

    inferred = infer_date_from_text(value)
    if inferred:
        return inferred

    return value


def looks_like_facebook_time(value: str) -> bool:
    value = value.strip().lower()
    if not value:
        return False

    month_words = list(ITALIAN_MONTHS.keys()) + [
        "january",
        "jan",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "aug",
        "september",
        "sep",
        "sept",
        "october",
        "oct",
        "november",
        "december",
        "dec",
    ]
    relative_words = [
        "min",
        "minuti",
        "h",
        "ore",
        "ora",
        "ieri",
        "oggi",
        "yesterday",
        "today",
        "g",
        "gg",
        "giorno",
        "giorni",
        "d",
        "day",
        "days",
        "sett",
        "settimana",
        "settimane",
        "w",
        "week",
        "weeks",
    ]
    has_digit = any(char.isdigit() for char in value)
    # Confronto a parole intere per evitare falsi positivi con abbreviazioni
    # corte come "g" o "h" (es. non deve scattare su testi generici).
    words_in_value = set(re.findall(r"[a-zàèéìòù]+", value))

    return has_digit and (
        any(month in value for month in month_words)
        or bool(words_in_value & set(relative_words))
        or bool(re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", value))
        or bool(re.search(r"\b\d{4}-\d{2}-\d{2}\b", value))
        or ":" in value
    )


def image_score(image) -> int:
    try:
        box = image.bounding_box(timeout=1000)
    except Exception:
        box = None

    if not box:
        return 0

    width = int(box.get("width", 0))
    height = int(box.get("height", 0))
    if width < 180 or height < 120:
        return 0

    src = image.get_attribute("src") or ""
    if not src.startswith("http"):
        return 0
    if "emoji.php" in src or "static.xx.fbcdn.net" in src:
        return 0

    return width * height


def find_first_post_image(page) -> Optional[Dict[str, str]]:
    post_selectors = [
        'div[role="article"]',
        "div[aria-posinset]",
    ]

    for selector in post_selectors:
        posts = page.locator(selector).all()
        for post in posts[:20]:
            try:
                images = post.locator("img").all()
            except Exception:
                continue

            best_image = None
            best_score = 0
            for image in images:
                score = image_score(image)
                if score > best_score:
                    best_image = image
                    best_score = score

            if best_image and best_score:
                image_url = best_image.get_attribute("src")
                if image_url:
                    post_text = best_text_from_post(post)
                    try:
                        full_post_text = clean_post_text(post.inner_text(timeout=3000))
                    except Exception:
                        full_post_text = post_text
                    date_in_post_text = infer_date_from_text(post_text) or infer_date_from_text(full_post_text)
                    published_at_raw = date_in_post_text or best_published_time_from_post(post)
                    try:
                        photo_url = best_image.evaluate(
                            "image => { const link = image.closest('a[href]'); return link ? link.href : ''; }"
                        )
                    except Exception:
                        photo_url = ""
                    return {
                        "image_url": image_url,
                        "photo_url": photo_url,
                        "text": post_text,
                        "published_at": date_in_post_text or normalize_facebook_time(published_at_raw),
                        "published_at_raw": published_at_raw,
                    }

    return None


def find_largest_visible_image_url(page) -> str:
    best_url = ""
    best_score = 0

    for image in page.locator("img").all():
        score = image_score(image)
        if score > best_score:
            src = image.get_attribute("src") or ""
            if src.startswith("http"):
                best_url = src
                best_score = score

    return best_url


def cookies_look_authenticated(cookies: List[Dict]) -> bool:
    names = {cookie.get("name", "") for cookie in cookies}
    return bool(names & FACEBOOK_LOGIN_COOKIE_NAMES)


def extract_first_facebook_image(facebook_url: str) -> Dict[str, str]:
    cookie_path = os.path.join(script_dir(), COOKIE_FILE)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                viewport={"width": 1366, "height": 2400},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
            )

            cookies = load_facebook_cookies(cookie_path)
            if cookies:
                context.add_cookies(cookies)
            if not cookies_look_authenticated(cookies):
                print(
                    f"ATTENZIONE: {cookie_path} non contiene un login Facebook valido "
                    "(mancano i cookie 'c_user'/'xs'). Verrà usata una sessione anonima: "
                    "Facebook mostra molte meno informazioni (spesso senza data/ora del post). "
                    "Rigenera il file con extract_cookies.py facendo il login quando richiesto."
                )

            page = context.new_page()
            page.goto(facebook_url, wait_until="domcontentloaded", timeout=60000)

            try:
                page.get_by_role("button", name="Consenti tutti i cookie").click(timeout=3000)
            except PlaywrightTimeoutError:
                pass
            except Exception:
                pass

            page.wait_for_timeout(5000)
            for _ in range(4):
                post = find_first_post_image(page)
                if post:
                    photo_url = post.get("photo_url", "")
                    if photo_url:
                        try:
                            photo_page = context.new_page()
                            photo_page.goto(photo_url, wait_until="domcontentloaded", timeout=60000)
                            photo_page.wait_for_timeout(4000)
                            larger_image_url = find_largest_visible_image_url(photo_page)
                            photo_page.close()
                            if larger_image_url:
                                post["image_url"] = larger_image_url
                        except Exception:
                            pass
                    return post
                page.mouse.wheel(0, 900)
                page.wait_for_timeout(2000)

            raise RuntimeError(f"Non ho trovato nessuna immagine grande nella pagina Facebook: {facebook_url}")
        finally:
            browser.close()


def extract_paneeco_menu() -> Dict:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": 1366, "height": 2200},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
            )
            page.goto(PANECO_PAGE["url"], wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)

            data = page.evaluate(
                """() => {
                    const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim();
                    const date = normalize(document.querySelector('.menu-header__title')?.textContent);
                    const categories = Array.from(document.querySelectorAll('.menu-category')).map((section) => {
                        const title = normalize(section.querySelector('.menu-category__title')?.textContent);
                        const description = normalize(section.querySelector('.menu-category__description')?.textContent);
                        const items = Array.from(section.querySelectorAll('.menu-item')).map((item) => ({
                            name: normalize(item.querySelector('.menu-item__name')?.textContent),
                            price: normalize(item.querySelector('.menu-item__price')?.textContent),
                            description: normalize(item.querySelector('.menu-item__description')?.textContent)
                        })).filter((item) => item.name);
                        return { title, description, items };
                    }).filter((category) => category.title);
                    return { date, categories };
                }"""
            )
        finally:
            browser.close()

    wanted_titles = {
        "primi piatti del giorno",
        "secondi piatti del giorno",
    }
    categories = [
        category
        for category in data.get("categories", [])
        if category.get("title", "").strip().lower() in wanted_titles
    ]

    if not categories:
        raise RuntimeError("Non ho trovato Primi del giorno e Secondi del giorno su Pane&Co.")

    published_at = normalize_paneeco_date(data.get("date", ""))
    menu_text = paneeco_text(data.get("date", ""), categories)
    image_bytes = render_paneeco_image(data.get("date", ""), categories)

    return {
        "name": PANECO_PAGE["name"],
        "image_bytes": image_bytes,
        "text": menu_text,
        "published_at": published_at,
        "published_at_raw": data.get("date", ""),
    }


def normalize_paneeco_date(value: str) -> str:
    value = value.strip()
    if not value:
        return ""

    match = re.search(r"(\d{1,2})\s+([A-Za-zÀ-ÿ]+)", value, re.IGNORECASE)
    if not match:
        return value

    month = ITALIAN_MONTHS.get(match.group(2).lower())
    if not month:
        return value

    year = rome_now().year
    return f"{int(match.group(1)):02d}/{month:02d}/{year}"


def paneeco_text(date_label: str, categories: List[Dict]) -> str:
    lines = []
    if date_label:
        lines.append(f"Menu {date_label}")
        lines.append("")

    for category in categories:
        lines.append(category["title"].upper())
        for item in category.get("items", []):
            price = f" - {item['price']}" if item.get("price") else ""
            lines.append(f"- {item['name']}{price}")
            if item.get("description"):
                lines.append(f"  {item['description']}")
        lines.append("")

    return "\n".join(lines).strip()


def load_font(size: int, bold: bool = False):
    candidates = []
    if os.name == "nt":
        candidates.extend(
            [
                os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arialbd.ttf" if bold else "arial.ttf"),
                os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "segoeuib.ttf" if bold else "segoeui.ttf"),
            ]
        )
    candidates.extend(
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
    )

    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)

    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> List[str]:
    words = text.split()
    if not words:
        return []

    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def render_paneeco_image(date_label: str, categories: List[Dict]) -> bytes:
    width = 1080
    margin = 54
    yellow = (255, 214, 65)
    cream = (255, 252, 243)
    ink = (16, 16, 16)
    muted = (92, 92, 92)
    border = (229, 229, 229)

    title_font = load_font(48, bold=True)
    date_font = load_font(30)
    section_font = load_font(30, bold=True)
    item_font = load_font(28, bold=True)
    desc_font = load_font(23)
    price_font = load_font(27, bold=True)

    probe = Image.new("RGB", (width, 200), cream)
    draw = ImageDraw.Draw(probe)

    row_data = []
    height = margin
    height += 66
    if date_label:
        height += 45
    height += 28

    for category in categories:
        section_height = 74
        if category.get("description"):
            section_height += 34
        height += section_height
        for item in category.get("items", []):
            item_lines = wrap_text(draw, item["name"], item_font, width - (margin * 2) - 170)
            desc_lines = wrap_text(draw, item.get("description", ""), desc_font, width - (margin * 2) - 30)
            row_height = 38 * max(1, len(item_lines)) + 28 * len(desc_lines) + 30
            row_data.append((item, item_lines, desc_lines, row_height))
            height += row_height
        height += 28

    image = Image.new("RGB", (width, height + margin), cream)
    draw = ImageDraw.Draw(image)

    y = margin
    draw.text((margin, y), "Pane&Co", fill=ink, font=title_font)
    y += 64
    if date_label:
        draw.text((margin, y), f"Menu del giorno: {date_label}", fill=muted, font=date_font)
        y += 48
    y += 12

    row_index = 0
    for category in categories:
        section_top = y
        section_height = 74 + (34 if category.get("description") else 0)
        draw.rounded_rectangle((margin, section_top, width - margin, section_top + section_height), radius=18, fill=yellow)
        draw.text((margin + 28, section_top + 20), category["title"].upper(), fill=ink, font=section_font)
        if category.get("description"):
            draw.text((margin + 28, section_top + 57), category["description"], fill=ink, font=desc_font)
        y += section_height

        for item in category.get("items", []):
            item, item_lines, desc_lines, row_height = row_data[row_index]
            row_index += 1
            draw.rectangle((margin, y, width - margin, y + row_height), fill=(255, 255, 255))
            draw.line((margin, y, width - margin, y), fill=border, width=2)

            text_y = y + 18
            for line in item_lines:
                draw.text((margin + 28, text_y), line, fill=ink, font=item_font)
                text_y += 38

            if item.get("price"):
                price_bbox = draw.textbbox((0, 0), item["price"], font=price_font)
                draw.text((width - margin - 28 - (price_bbox[2] - price_bbox[0]), y + 20), item["price"], fill=ink, font=price_font)

            for line in desc_lines:
                draw.text((margin + 28, text_y), line, fill=muted, font=desc_font)
                text_y += 28

            y += row_height

        y += 28

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=92)
    return output.getvalue()


def download_image(image_url: str) -> bytes:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(image_url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.content


def save_image(image_bytes: bytes, filename: str) -> str:
    image_path = os.path.join(script_dir(), filename)
    with open(image_path, "wb") as image_file:
        image_file.write(image_bytes)
    return image_path


def publish_dir() -> str:
    path = os.path.join(script_dir(), PUBLISH_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def safe_file_name(name: str) -> str:
    replacements = {
        "ì": "i",
        "Ì": "I",
        "à": "a",
        "è": "e",
        "é": "e",
        "ò": "o",
        "ù": "u",
    }
    for source, target in replacements.items():
        name = name.replace(source, target)
    return "".join(char if char.isalnum() else "_" for char in name).strip("_")


def parse_status_date(value: str) -> Optional[datetime.date]:
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", value or "")
    if not match:
        return None

    try:
        return datetime.date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    except ValueError:
        return None


def infer_date_from_text(text: str) -> str:
    text = text or ""

    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", text)
    if match:
        year = int(match.group(3))
        if year < 100:
            year += 2000

        try:
            return datetime.date(year, int(match.group(2)), int(match.group(1))).strftime("%d/%m/%Y")
        except ValueError:
            pass

    # Fallback: date scritte per esteso in italiano, es. "1 Settembre 2026"
    # o "1 settembre" (anno sottinteso = anno corrente).
    month_pattern = "|".join(ITALIAN_MONTHS.keys())
    match = re.search(
        rf"(\d{{1,2}})\s+({month_pattern})(?:\s+(\d{{4}}))?",
        text,
        re.IGNORECASE,
    )
    if match:
        day = int(match.group(1))
        month = ITALIAN_MONTHS.get(match.group(2).lower())
        year = int(match.group(3)) if match.group(3) else rome_now().year
        if month:
            try:
                return datetime.date(year, month, day).strftime("%d/%m/%Y")
            except ValueError:
                return ""

    return ""


def panel_published_at(panel: Dict) -> str:
    return panel.get("published_at") or infer_date_from_text(panel.get("text", ""))


def existing_publish_panel_if_today(name: str) -> Optional[Dict]:
    output_dir = publish_dir()
    status_path = os.path.join(output_dir, "status.json")
    if not os.path.exists(status_path):
        return None

    try:
        with open(status_path, "r", encoding="utf-8") as status_file:
            status = json.load(status_file)
    except Exception:
        return None

    for page_status in status.get("pages", []):
        if page_status.get("name") != name:
            continue
        published_at = page_status.get("published_at", "") or infer_date_from_text(page_status.get("text", ""))
        if parse_status_date(published_at) != rome_now().date():
            return None

        image_name = page_status.get("image") or f"{safe_file_name(name)}.jpg"
        image_path = os.path.join(output_dir, image_name)
        if not os.path.exists(image_path):
            return None

        text_name = page_status.get("publish_text") or f"{safe_file_name(name)}.txt"
        text_path = os.path.join(output_dir, text_name)
        text = page_status.get("text", "")
        if os.path.exists(text_path):
            try:
                with open(text_path, "r", encoding="utf-8") as text_file:
                    text = text_file.read()
            except Exception:
                pass

        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()

        return {
            "name": name,
            "image_bytes": image_bytes,
            "text": text,
            "published_at": published_at,
            "published_at_raw": page_status.get("published_at_raw", ""),
            "publish_image": image_name,
            "publish_text": text_name,
            "reused": True,
        }

    return None


def save_publish_files(panels: List[Dict]) -> str:
    output_dir = publish_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")

    for panel in panels:
        if "error" in panel:
            continue

        base_name = safe_file_name(panel["name"])
        latest_name = f"{base_name}.jpg"
        archive_name = f"{base_name}_{timestamp}.jpg"
        panel["publish_image"] = panel.get("publish_image") or latest_name
        panel["publish_text"] = panel.get("publish_text") or f"{base_name}.txt"

        if panel.get("reused"):
            continue

        for filename in (latest_name, archive_name):
            path = os.path.join(output_dir, filename)
            with open(path, "wb") as image_file:
                image_file.write(panel["image_bytes"])

        text_path = os.path.join(output_dir, f"{base_name}.txt")
        with open(text_path, "w", encoding="utf-8") as text_file:
            text_file.write(panel.get("text", ""))

        panel["publish_image"] = latest_name
        panel["publish_text"] = f"{base_name}.txt"

    write_publish_index(panels, output_dir)
    write_publish_status(panels, output_dir)
    return output_dir


def write_publish_status(panels: List[Dict], output_dir: str) -> None:
    status = {
        "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "pages": [
            {
                "name": panel["name"],
                "image": panel.get("publish_image"),
                "text": panel.get("text", ""),
                "published_at": panel_published_at(panel),
                "published_at_raw": panel.get("published_at_raw", ""),
                "error": panel.get("error"),
            }
            for panel in panels
        ],
    }
    status_path = os.path.join(output_dir, "status.json")
    with open(status_path, "w", encoding="utf-8") as status_file:
        json.dump(status, status_file, ensure_ascii=False, indent=2)


def write_publish_index(panels: List[Dict], output_dir: str) -> None:
    updated_at = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    cards = []

    for panel in panels:
        title = html.escape(panel["name"])
        if "error" in panel:
            body = f"<p class=\"error\">{html.escape(panel['error'])}</p>"
        else:
            image = html.escape(panel.get("publish_image", ""))
            text = html.escape(panel.get("text", ""))
            published_at = html.escape(panel_published_at(panel))
            body = f"""
                <img src="{image}?v={int(time.time())}" alt="{title}">
                <p class="published">Facebook: {published_at or "orario non disponibile"}</p>
                <pre>{text}</pre>
            """
        cards.append(f"<section><h2>{title}</h2>{body}</section>")

    index_html = f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="300">
  <title>Rosticcerie</title>
  <style>
    body {{
      margin: 0;
      background: #111;
      color: #fff;
      font-family: Arial, sans-serif;
    }}
    header {{
      padding: 14px 16px;
      border-bottom: 1px solid #333;
    }}
    h1 {{
      margin: 0;
      font-size: 22px;
    }}
    .updated {{
      margin: 4px 0 0;
      color: #ccc;
      font-size: 14px;
    }}
    main {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1px;
      background: #333;
    }}
    section {{
      min-height: 100vh;
      background: #111;
      padding: 12px;
      box-sizing: border-box;
    }}
    h2 {{
      margin: 0 0 10px;
      font-size: 20px;
    }}
    img {{
      width: 100%;
      height: auto;
      display: block;
      background: #000;
    }}
    pre {{
      white-space: pre-wrap;
      font-family: Arial, sans-serif;
      font-size: 16px;
      line-height: 1.35;
      margin: 12px 0 0;
    }}
    .published {{
      color: #ccc;
      font-size: 13px;
      margin: 8px 0 0;
    }}
    .error {{
      color: #ffd0d0;
      font-size: 16px;
    }}
    @media (max-width: 760px) {{
      main {{
        grid-template-columns: 1fr;
      }}
      section {{
        min-height: auto;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Rosticcerie</h1>
    <p class="updated">Aggiornato: {html.escape(updated_at)}</p>
  </header>
  <main>
    {"".join(cards)}
  </main>
</body>
</html>
"""
    index_path = os.path.join(output_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as index_file:
        index_file.write(index_html)


def git_publish_if_available(output_dir: str) -> None:
    repo_dir = find_git_repository(output_dir)
    if not repo_dir:
        print("Cartella pubblicata localmente. GitHub non configurato in questa cartella.")
        return

    rel_output = os.path.relpath(output_dir, repo_dir)
    commands = [
        ["git", "add", rel_output],
        ["git", "commit", "-m", "Aggiorna foto rosticcerie"],
        ["git", "push"],
    ]

    for command in commands:
        result = subprocess.run(command, cwd=repo_dir, capture_output=True, text=True)
        if command[1] == "commit" and result.returncode != 0 and "nothing to commit" in result.stdout.lower():
            print("GitHub: nessuna modifica nuova da pubblicare.")
            return
        if result.returncode != 0:
            print(f"GitHub: comando non riuscito: {' '.join(command)}")
            print((result.stderr or result.stdout).strip())
            return

    print("GitHub: pubblicazione completata.")


def find_git_repository(path: str) -> Optional[str]:
    current = os.path.abspath(path)
    while True:
        if os.path.isdir(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def fit_image(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    fitted = image.copy()
    fitted.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    return fitted


def draw_panel(canvas, image_tk, panel: Dict, left: int, top: int, width: int, height: int):
    canvas.create_rectangle(left, top, left + width, top + height, fill="black", outline="#333333")

    if "error" in panel:
        canvas.create_text(
            left + 28,
            top + 28,
            anchor="nw",
            text=f"{panel['name']}\n{panel['error']}",
            fill="white",
            font=("Arial", 24, "bold"),
            width=max(260, width - 56),
        )
        return None

    image = Image.open(io.BytesIO(panel["image_bytes"]))
    image = fit_image(image, width, height)
    photo = image_tk.PhotoImage(image)

    x = left + (width - image.width) // 2
    y = top + (height - image.height) // 2
    canvas.create_image(x, y, anchor="nw", image=photo)

    title = panel["name"]
    text = panel.get("text", "")
    overlay = title if not text else f"{title}\n{text}"
    text_width = min(680, max(260, width - 56))
    text_id = canvas.create_text(
        left + 28,
        top + 24,
        anchor="nw",
        text=overlay,
        fill="white",
        font=("Arial", 21, "bold"),
        width=text_width,
    )
    bbox = canvas.bbox(text_id)
    if bbox:
        padding = 14
        background = canvas.create_rectangle(
            bbox[0] - padding,
            bbox[1] - padding,
            bbox[2] + padding,
            bbox[3] + padding,
            fill="black",
            outline="white",
        )
        canvas.tag_lower(background, text_id)

    return photo


def show_fullscreen(panels: List[Dict]) -> None:
    from PIL import ImageTk
    from tkinter import Canvas, Tk

    root = Tk()
    root.title("Rosticcerie")
    root.configure(bg="black")
    root.attributes("-fullscreen", True)
    root.focus_force()

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    canvas = Canvas(root, width=screen_width, height=screen_height, bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    panel_count = max(1, len(panels))
    panel_width = screen_width // panel_count
    photos = []
    for index, panel in enumerate(panels):
        left = index * panel_width
        width = screen_width - left if index == panel_count - 1 else panel_width
        photos.append(draw_panel(canvas, ImageTk, panel, left, 0, width, screen_height))
        if index:
            canvas.create_line(left, 0, left, screen_height, fill="white", width=2)
    canvas.photos = photos

    def close(_event=None):
        root.destroy()

    root.bind("<Key>", close)
    root.bind("<Button-1>", close)
    root.bind("<Escape>", close)
    root.after(300, root.focus_force)
    root.mainloop()


def extract_pages() -> List[Dict]:
    panels = []

    for facebook_page in FACEBOOK_PAGES:
        name = facebook_page["name"]
        existing_panel = existing_publish_panel_if_today(name)
        if existing_panel:
            print(f"{name}: foto di oggi già presente, salto la verifica.")
            panels.append(existing_panel)
            continue

        print(f"Cerco la prima immagine su Facebook: {name}...")
        try:
            post = extract_first_facebook_image(facebook_page["url"])
            image_bytes = download_image(post["image_url"])
            image_path = save_image(image_bytes, facebook_page["output_image"])
            print(f"{name}: immagine salvata in {image_path}")
            if not post.get("published_at_raw"):
                print(
                    f"{name}: non ho trovato la data/ora del post su Facebook "
                    "(published_at_raw vuoto). Uso come riserva la data eventualmente "
                    "scritta nel testo del post."
                )
            panels.append(
                {
                    "name": name,
                    "image_bytes": image_bytes,
                    "text": post.get("text", ""),
                    "published_at": post.get("published_at", ""),
                    "published_at_raw": post.get("published_at_raw", ""),
                }
            )
        except Exception as exc:
            panels.append({"name": name, "error": str(exc)})

    existing_panel = existing_publish_panel_if_today(PANECO_PAGE["name"])
    if existing_panel:
        print("Pane&Co: menu di oggi già presente, salto la verifica.")
        panels.append(existing_panel)
        return panels

    print("Creo il menu Pane&Co con primi e secondi del giorno...")
    try:
        panel = extract_paneeco_menu()
        image_path = save_image(panel["image_bytes"], "Rosticceria_Pane_Co.jpg")
        print(f"Pane&Co: immagine salvata in {image_path}")
        panels.append(panel)
    except Exception as exc:
        panels.append({"name": PANECO_PAGE["name"], "error": str(exc)})

    return panels


def run_once(show: bool = False, publish_to_git: bool = True) -> None:
    panels = extract_pages()
    output_dir = publish_dir()
    if panels and all(panel.get("reused") for panel in panels):
        print("Tutte le rosticcerie hanno già il menu di oggi: nessuna verifica necessaria.")
        if show:
            show_fullscreen(panels)
        return

    output_dir = save_publish_files(panels)
    print(f"File per iOS aggiornati in: {output_dir}")

    if publish_to_git:
        git_publish_if_available(output_dir)

    if show:
        show_fullscreen(panels)


def inside_run_window(moment: datetime.datetime) -> bool:
    return RUN_START <= moment.time() <= RUN_END


def next_run_time(now: datetime.datetime) -> datetime.datetime:
    today_start = datetime.datetime.combine(now.date(), RUN_START)
    today_end = datetime.datetime.combine(now.date(), RUN_END)
    interval = datetime.timedelta(minutes=RUN_INTERVAL_MINUTES)

    if now < today_start:
        return today_start
    if now > today_end:
        return today_start + datetime.timedelta(days=1)

    next_time = today_start
    while next_time < now:
        next_time += interval

    if next_time <= today_end:
        return next_time
    return today_start + datetime.timedelta(days=1)


def monitor_loop(show: bool = False, publish_to_git: bool = True) -> None:
    print("Monitor attivo: estrazione ogni minuto tra le 09:00 e le 12:00.")

    while True:
        now = datetime.datetime.now()
        scheduled = next_run_time(now)
        seconds = max(0, int((scheduled - now).total_seconds()))
        print(f"Prossima estrazione: {scheduled.strftime('%d/%m/%Y %H:%M')}")

        while seconds > 0:
            time.sleep(min(seconds, 60))
            now = datetime.datetime.now()
            seconds = max(0, int((scheduled - now).total_seconds()))

        if inside_run_window(datetime.datetime.now()):
            run_once(show=show, publish_to_git=publish_to_git)


def main() -> None:
    parser = argparse.ArgumentParser(description="Estrae e pubblica Fantasia, Cibarìa e Pane&Co.")
    parser.add_argument("--once", action="store_true", help="Esegue una sola estrazione e poi termina.")
    parser.add_argument("--show", action="store_true", help="Mostra anche le due foto a pieno schermo.")
    parser.add_argument("--no-git", action="store_true", help="Non prova a pubblicare con GitHub/git.")
    args = parser.parse_args()

    if args.once:
        run_once(show=args.show, publish_to_git=not args.no_git)
    else:
        monitor_loop(show=args.show, publish_to_git=not args.no_git)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Errore: {exc}")
        sys.exit(1)
