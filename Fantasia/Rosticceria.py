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
from PIL import Image

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
COOKIE_FILE = "cookies.txt"
PUBLISH_DIR = os.path.join("output", "rosticceria_ios")
RUN_START = datetime.time(10, 0)
RUN_END = datetime.time(12, 0)
RUN_INTERVAL_MINUTES = 30


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


def best_text_from_post(post) -> str:
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
            return text
    except Exception:
        pass

    try:
        return clean_post_text(post.inner_text(timeout=3000))
    except Exception:
        return ""


def best_published_time_from_post(post) -> str:
    selectors = [
        "abbr",
        'a[aria-label]',
        'span[aria-label]',
        'time',
    ]

    for selector in selectors:
        try:
            for element in post.locator(selector).all():
                for attribute in ("title", "aria-label", "datetime"):
                    value = element.get_attribute(attribute)
                    if value and looks_like_facebook_time(value):
                        return value.strip()

                try:
                    text = element.inner_text(timeout=1000).strip()
                except Exception:
                    text = ""
                if text and looks_like_facebook_time(text):
                    return text
        except Exception:
            pass

    return ""


def rome_now() -> datetime.datetime:
    return datetime.datetime.now(ZoneInfo("Europe/Rome"))


def normalize_facebook_time(value: str) -> str:
    value = value.strip()
    if not value:
        return ""

    lower_value = value.lower()
    now = rome_now()

    match = re.fullmatch(r"(\d+)\s*(min|m)", lower_value)
    if match:
        minutes = int(match.group(1))
        return (now - datetime.timedelta(minutes=minutes)).strftime("%d/%m/%Y %H:%M circa")

    match = re.fullmatch(r"(\d+)\s*(h|ore?|ora)", lower_value)
    if match:
        hours = int(match.group(1))
        return (now - datetime.timedelta(hours=hours)).strftime("%d/%m/%Y %H:%M circa")

    match = re.search(r"ieri.*?(\d{1,2})[:.](\d{2})", lower_value)
    if match:
        published = now - datetime.timedelta(days=1)
        published = published.replace(hour=int(match.group(1)), minute=int(match.group(2)), second=0, microsecond=0)
        return published.strftime("%d/%m/%Y %H:%M")

    return value


def looks_like_facebook_time(value: str) -> bool:
    value = value.strip().lower()
    if not value:
        return False

    month_words = [
        "gennaio",
        "febbraio",
        "marzo",
        "aprile",
        "maggio",
        "giugno",
        "luglio",
        "agosto",
        "settembre",
        "ottobre",
        "novembre",
        "dicembre",
    ]
    relative_words = ["min", "h", "ore", "ieri", "oggi"]
    has_digit = any(char.isdigit() for char in value)

    return has_digit and (
        any(month in value for month in month_words)
        or any(word in value for word in relative_words)
        or "/" in value
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
                    published_at_raw = best_published_time_from_post(post)
                    try:
                        photo_url = best_image.evaluate(
                            "image => { const link = image.closest('a[href]'); return link ? link.href : ''; }"
                        )
                    except Exception:
                        photo_url = ""
                    return {
                        "image_url": image_url,
                        "photo_url": photo_url,
                        "text": best_text_from_post(post),
                        "published_at": normalize_facebook_time(published_at_raw),
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


def save_publish_files(panels: List[Dict]) -> str:
    output_dir = publish_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")

    for panel in panels:
        if "error" in panel:
            continue

        base_name = safe_file_name(panel["name"])
        latest_name = f"{base_name}.jpg"
        archive_name = f"{base_name}_{timestamp}.jpg"

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
                "published_at": panel.get("published_at", ""),
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
            published_at = html.escape(panel.get("published_at", ""))
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

    half_width = screen_width // 2
    photos = []
    photos.append(draw_panel(canvas, ImageTk, panels[0], 0, 0, half_width, screen_height))
    photos.append(draw_panel(canvas, ImageTk, panels[1], half_width, 0, screen_width - half_width, screen_height))
    canvas.create_line(half_width, 0, half_width, screen_height, fill="white", width=2)
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
        print(f"Cerco la prima immagine su Facebook: {name}...")
        try:
            post = extract_first_facebook_image(facebook_page["url"])
            image_bytes = download_image(post["image_url"])
            image_path = save_image(image_bytes, facebook_page["output_image"])
            print(f"{name}: immagine salvata in {image_path}")
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

    return panels


def run_once(show: bool = False, publish_to_git: bool = True) -> None:
    panels = extract_pages()
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
    print("Monitor attivo: estrazione ogni 30 minuti tra le 10:00 e le 12:00.")

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
    parser = argparse.ArgumentParser(description="Estrae e pubblica le foto di Fantasia e Cibarìa.")
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
