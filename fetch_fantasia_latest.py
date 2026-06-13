import base64
import datetime as dt
import hashlib
import html
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytz
import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


SEARCH_URL = "https://www.facebook.com/search/top?q=rosticceria%20fantasia"
SEARCH_URLS = [
    SEARCH_URL,
    "https://www.facebook.com/search/posts?q=rosticceria%20fantasia",
]
PAGE_NAME = "Rosticceria Fantasia"
OUTPUT_DIR = Path("Fantasia")
ARCHIVE_DIR = OUTPUT_DIR / "archive"
LATEST_JSON = OUTPUT_DIR / "latest.json"
LATEST_IMAGE = OUTPUT_DIR / "Fantasia.jpg"
LATEST_TXT = OUTPUT_DIR / "Fantasia.txt"
INDEX_HTML = OUTPUT_DIR / "Fantasia.html"
COOKIE_FILE = Path("cookies.txt")
ROME = pytz.timezone("Europe/Rome")

MENU_KEYWORDS = [
    "menu del giorno",
    "menu' del giorno",
    "menu di oggi",
    "menu",
    "menu'",
    "men\u00f9",
    "primo",
    "secondo",
    "contorno",
]


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def now_rome() -> dt.datetime:
    return dt.datetime.now(ROME)


def inside_time_window(moment: Optional[dt.datetime] = None) -> bool:
    moment = moment or now_rome()
    start = moment.replace(hour=10, minute=0, second=0, microsecond=0)
    end = moment.replace(hour=12, minute=0, second=0, microsecond=0)
    return start <= moment <= end


def should_skip_for_time_window() -> bool:
    if os.getenv("FANTASIA_IGNORE_TIME_WINDOW") == "1":
        return False
    if os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
        return False
    return not inside_time_window()


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def decode_cookie_secret() -> Optional[Path]:
    raw = os.getenv("FACEBOOK_COOKIES_B64", "").strip()
    if not raw:
        raw = os.getenv("FB_COOKIES_B64", "").strip()
    if not raw:
        return None

    cookie_path = Path("facebook_cookies_from_secret.txt")
    try:
        cookie_path.write_bytes(base64.b64decode(raw))
        logging.info("Loaded Facebook cookies from base64 secret.")
        return cookie_path
    except Exception as exc:
        logging.warning("Could not decode FACEBOOK_COOKIES_B64: %s", exc)
        return None


def load_netscape_cookies(cookie_path: Path) -> List[Dict]:
    if not cookie_path.exists():
        logging.warning("Cookie file not found: %s", cookie_path)
        return []

    cookies = []
    for line_number, line in enumerate(cookie_path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#") or "Netscape" in line:
            continue

        parts = line.split("\t")
        if len(parts) < 7:
            logging.warning("Skipping malformed cookie line %s.", line_number)
            continue

        domain, _flag, path, secure, expires, name, value = parts[:7]
        try:
            expires_int = int(expires)
        except ValueError:
            expires_int = -1

        cookies.append(
            {
                "domain": domain,
                "path": path or "/",
                "secure": secure.upper() == "TRUE",
                "expires": expires_int if expires_int > 0 else -1,
                "name": name,
                "value": value,
                "httpOnly": False,
                "sameSite": "Lax",
            }
        )

    facebook_cookies = [cookie for cookie in cookies if "facebook.com" in cookie["domain"]]
    logging.info("Loaded %s cookies, %s for Facebook.", len(cookies), len(facebook_cookies))
    return facebook_cookies


def normalize_text(value: str) -> str:
    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def text_looks_like_menu(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in MENU_KEYWORDS)


def today_patterns(moment: Optional[dt.datetime] = None) -> List[str]:
    moment = moment or now_rome()
    day = moment.day
    month = moment.month
    year = moment.year
    short_year = year % 100
    return [
        f"{day:02d}/{month:02d}/{short_year:02d}",
        f"{day}/{month:02d}/{short_year:02d}",
        f"{day:02d}/{month}/{short_year:02d}",
        f"{day}/{month}/{short_year:02d}",
        f"{day:02d}/{month:02d}/{year}",
        f"{day}/{month:02d}/{year}",
        f"{day:02d}/{month}/{year}",
        f"{day}/{month}/{year}",
        f"{day:02d}-{month:02d}-{short_year:02d}",
        f"{day:02d}-{month:02d}-{year}",
    ]


def menu_candidate_score(text: str, image_url: str) -> int:
    lowered = text.lower()
    score = 0
    if "rosticceria fantasia" in lowered:
        score += 50
    if "menu del giorno" in lowered or "men\u00f9 del giorno" in lowered:
        score += 100
    if any(pattern in text for pattern in today_patterns()):
        score += 1000
    if image_url:
        score += 10
    return score


def post_hash(text: str, image_url: str) -> str:
    seed = f"{normalize_text(text)}\n{image_url}".encode("utf-8", errors="ignore")
    return hashlib.sha256(seed).hexdigest()[:16]


def extract_best_image_from_article(article) -> Optional[str]:
    candidates: List[Tuple[int, str]] = []
    locators = article.locator("img").all()
    for image in locators:
        try:
            src = image.get_attribute("src") or ""
            if not src or src.startswith("data:"):
                continue
            if "scontent" not in src and "fbcdn" not in src:
                continue
            box = image.bounding_box() or {}
            width = int(box.get("width") or 0)
            height = int(box.get("height") or 0)
            score = width * height
            if score < 10_000:
                continue
            candidates.append((score, src))
        except Exception:
            continue

    if not candidates:
        return None
    candidates.sort(reverse=True, key=lambda item: item[0])
    return candidates[0][1]


def find_menu_post(cookies: List[Dict]) -> Optional[Dict]:
    best_candidate: Optional[Dict] = None
    best_score = -1

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            context = browser.new_context(
                locale="it-IT",
                timezone_id="Europe/Rome",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1365, "height": 1600},
            )
            if cookies:
                context.add_cookies(cookies)

            page = context.new_page()
            for search_url in SEARCH_URLS:
                logging.info("Opening Facebook search page: %s", search_url)
                page.goto(search_url, wait_until="domcontentloaded", timeout=60_000)
                time.sleep(6)

                for _ in range(4):
                    page.mouse.wheel(0, 1200)
                    time.sleep(2)

                selectors = ["div[role='article']", "div[aria-posinset]"]
                articles = []
                for selector in selectors:
                    try:
                        found = page.locator(selector).all()
                        if found:
                            articles = found
                            logging.info("Found %s candidate posts with selector %s.", len(found), selector)
                            break
                    except PlaywrightTimeoutError:
                        continue

                for index, article in enumerate(articles[:30], 1):
                    try:
                        text = normalize_text(article.inner_text(timeout=5_000))
                    except Exception:
                        continue

                    if not text_looks_like_menu(text):
                        continue

                    image_url = extract_best_image_from_article(article)
                    if not image_url:
                        logging.info("Candidate post %s has menu text but no usable image.", index)
                        continue

                    score = menu_candidate_score(text, image_url)
                    logging.info("Menu candidate in post %s scored %s.", index, score)
                    candidate = {
                        "page": PAGE_NAME,
                        "source_url": search_url,
                        "text": text,
                        "image_url": image_url,
                        "found_at": now_rome().isoformat(),
                        "hash": post_hash(text, image_url),
                        "score": score,
                    }
                    if score > best_score:
                        best_candidate = candidate
                        best_score = score

                if best_candidate and best_score >= 1000:
                    logging.info("Today's menu candidate found with score %s.", best_score)
                    return best_candidate

            logging.info("No menu post found in the visible Facebook results.")
            return best_candidate
        finally:
            browser.close()


def download_image(image_url: str, destination: Path) -> None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(image_url, headers=headers, timeout=45)
    response.raise_for_status()
    destination.write_bytes(response.content)
    logging.info("Saved image %s (%s bytes).", destination, len(response.content))


def load_previous() -> Optional[Dict]:
    if not LATEST_JSON.exists():
        return None
    try:
        return json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(data: Dict) -> None:
    LATEST_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def html_page(data: Dict) -> str:
    escaped_text = html.escape(data.get("text", ""))
    found_at = data.get("found_at", "")
    generated_at = now_rome().strftime("%d/%m/%Y %H:%M")
    source_url = html.escape(data.get("source_url", SEARCH_URL), quote=True)

    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="300">
  <title>Rosticceria Fantasia - Menu del giorno</title>
  <link rel="manifest" href="Fantasia-manifest.json">
  <meta name="theme-color" content="#E8521A">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="Fantasia">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <style>
    :root {{
      color-scheme: light;
      --ink: #251b14;
      --muted: #6f6259;
      --line: #e7ded6;
      --paper: #fffaf4;
      --accent: #b84f17;
      --accent-dark: #7c2f0d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f4ede5;
      color: var(--ink);
      line-height: 1.45;
    }}
    main {{
      max-width: 860px;
      margin: 0 auto;
      padding: 18px 14px 28px;
    }}
    header {{
      padding: 8px 2px 16px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(1.55rem, 5vw, 2.25rem);
      letter-spacing: 0;
      color: var(--accent-dark);
    }}
    .meta {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .actions {{
      margin-top: 12px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .actions a {{
      display: inline-flex;
      align-items: center;
      min-height: 38px;
      padding: 8px 11px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--accent-dark);
      text-decoration: none;
      font-weight: 600;
      font-size: 0.92rem;
    }}
    .panel {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    .menu-text {{
      padding: 14px;
      white-space: pre-wrap;
      font-size: 1rem;
      border-bottom: 1px solid var(--line);
    }}
    img {{
      display: block;
      width: 100%;
      height: auto;
      background: #fff;
    }}
    footer {{
      padding: 12px 2px 0;
      color: var(--muted);
      font-size: 0.9rem;
    }}
    a {{ color: var(--accent); }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Rosticceria Fantasia</h1>
      <div class="meta">Menu trovato: {html.escape(found_at)}<br>Aggiornato: {html.escape(generated_at)}</div>
      <div class="actions">
        <a href="Fantasia.jpg">Apri foto</a>
        <a href="latest.json">Dati JSON</a>
      </div>
    </header>
    <section class="panel" aria-label="Menu del giorno">
      <div class="menu-text">{escaped_text}</div>
      <img src="Fantasia.jpg?v={html.escape(data.get("hash", generated_at), quote=True)}" alt="Foto del menu del giorno">
    </section>
    <footer>
      Fonte: <a href="{source_url}">ricerca Facebook</a>. Questa pagina si aggiorna automaticamente ogni 5 minuti.
    </footer>
  </main>
</body>
</html>
"""


def status_html_page(status: Dict) -> str:
    generated_at = now_rome().strftime("%d/%m/%Y %H:%M")
    message = html.escape(status.get("message", "Menu non trovato."))
    detail = html.escape(status.get("detail", ""))
    source_url = html.escape(status.get("source_url", SEARCH_URL), quote=True)

    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="300">
  <title>Rosticceria Fantasia - Menu del giorno</title>
  <link rel="manifest" href="Fantasia-manifest.json">
  <meta name="theme-color" content="#E8521A">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="Fantasia">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <style>
    :root {{
      color-scheme: light;
      --ink: #251b14;
      --muted: #6f6259;
      --line: #e7ded6;
      --paper: #fffaf4;
      --accent: #b84f17;
      --accent-dark: #7c2f0d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f4ede5;
      color: var(--ink);
      line-height: 1.45;
    }}
    main {{
      max-width: 760px;
      margin: 0 auto;
      padding: 18px 14px 28px;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: clamp(1.55rem, 5vw, 2.25rem);
      color: var(--accent-dark);
    }}
    .meta {{
      color: var(--muted);
      font-size: 0.95rem;
      margin-bottom: 16px;
    }}
    .panel {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }}
    .message {{
      font-size: 1.15rem;
      font-weight: 700;
      margin-bottom: 8px;
    }}
    .detail {{
      color: var(--muted);
      white-space: pre-wrap;
    }}
    a {{ color: var(--accent); }}
  </style>
</head>
<body>
  <main>
    <h1>Rosticceria Fantasia</h1>
    <div class="meta">Ultimo controllo: {html.escape(generated_at)}</div>
    <section class="panel" aria-label="Stato menu del giorno">
      <div class="message">{message}</div>
      <div class="detail">{detail}</div>
    </section>
    <p class="meta">Fonte: <a href="{source_url}">ricerca Facebook</a>. Questa pagina si aggiorna automaticamente ogni 5 minuti.</p>
  </main>
</body>
</html>
"""


def write_html(data: Dict) -> None:
    INDEX_HTML.write_text(html_page(data), encoding="utf-8")


def write_status_html(status: Dict) -> None:
    INDEX_HTML.write_text(status_html_page(status), encoding="utf-8")


def save_no_menu_found() -> None:
    checked_at = now_rome()
    status = {
        "page": PAGE_NAME,
        "source_url": SEARCH_URL,
        "status": "not_found",
        "checked_at": checked_at.isoformat(),
        "message": "Nessun menu nuovo trovato oggi.",
        "detail": (
            "Il controllo automatico ha cercato sulla pagina Facebook, "
            "ma non ha trovato una foto del menu con testo riconoscibile. "
            "La vecchia immagine non viene mostrata per evitare confusione."
        ),
    }
    write_json(status)
    LATEST_TXT.write_text(
        checked_at.strftime("%Y-%m-%d\n%H-%M\nNO_MENU"),
        encoding="utf-8",
    )
    write_status_html(status)


def save_existing_image_page() -> None:
    checked_at = now_rome()
    image_mtime = dt.datetime.fromtimestamp(LATEST_IMAGE.stat().st_mtime, ROME)
    data = {
        "page": PAGE_NAME,
        "source_url": SEARCH_URL,
        "status": "existing_image",
        "text": (
            "Ultima foto del menu disponibile.\n"
            "Il controllo automatico non ha trovato una foto nuova, "
            "quindi viene mantenuta questa."
        ),
        "found_at": image_mtime.isoformat(),
        "checked_at": checked_at.isoformat(),
        "hash": str(int(image_mtime.timestamp())),
    }
    write_json(data)
    LATEST_TXT.write_text(
        checked_at.strftime("%Y-%m-%d\n%H-%M\nOLD_IMAGE"),
        encoding="utf-8",
    )
    write_html(data)


def save_menu(post: Dict) -> bool:
    previous = load_previous()
    if previous and previous.get("hash") == post.get("hash"):
        logging.info("Menu already saved; nothing to update.")
        return False

    today = now_rome().strftime("%Y-%m-%d")
    archive_image = ARCHIVE_DIR / f"{today}-{post['hash']}.jpg"
    download_image(post["image_url"], archive_image)
    LATEST_IMAGE.write_bytes(archive_image.read_bytes())

    post["archive_image"] = archive_image.as_posix().replace("Fantasia/", "")
    write_json(post)
    LATEST_TXT.write_text(
        now_rome().strftime("%Y-%m-%d\n%H-%M"),
        encoding="utf-8",
    )
    write_html(post)
    logging.info("Saved latest menu files in %s.", OUTPUT_DIR)
    return True


def main() -> int:
    setup_logging()
    ensure_dirs()

    if should_skip_for_time_window():
        logging.info("Outside 10:00-12:00 Europe/Rome window. Exiting cleanly.")
        return 0

    cookie_path = decode_cookie_secret() or COOKIE_FILE
    cookies = load_netscape_cookies(cookie_path)
    post = find_menu_post(cookies)
    if not post:
        previous = load_previous()
        if previous and previous.get("status") != "not_found":
            logging.info("No new menu found; keeping the last saved menu.")
        elif LATEST_IMAGE.exists():
            logging.info("No new menu found; restoring the existing image page.")
            save_existing_image_page()
        else:
            save_no_menu_found()
        return 0

    save_menu(post)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
