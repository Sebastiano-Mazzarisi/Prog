"""
SinnerVoce.py
Aggiorna Tennis/Sinner.txt con una frase leggibile da Siri.

Versione corretta:
- evita falsi avversari tipo "The Latest News";
- non considera LIVE una riga senza punteggio solo perché l'orario è passato;
- preferisce dati chiari da fixtures/results/main.
"""

import os
import re
import csv
import time
from dataclasses import dataclass
from datetime import datetime, timedelta


DIR = os.path.dirname(os.path.abspath(__file__))

F_TXT = os.path.join(DIR, "Sinner.txt")
F_CSV = os.path.join(DIR, "Sinner-dati.csv")

COGNOME = "SINNER"
NOME = "Jannik"

URLS = [
    ("fixtures", "https://www.flashscore.com/tennis/atp-singles/rome/fixtures/"),
    ("main", "https://www.flashscore.com/tennis/atp-singles/rome/"),
    ("results", "https://www.flashscore.com/tennis/atp-singles/rome/results/"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}


@dataclass
class Match:
    stato: str
    data: str
    ora: str
    avversario: str
    punteggio: str
    fonte: str
    recupero_sec: float = 0.0


def pulisci(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def title_name(s):
    out = []
    for p in pulisci(s).split():
        if len(p) <= 2 and p.isupper():
            out.append(p)
        else:
            out.append(p[:1].upper() + p[1:].lower())
    return " ".join(out)


NOMI_NOTI = {
    "POPYRIN A": "Popyrin Alexei",
    "POPYRIN ALEXEI": "Popyrin Alexei",
    "OFNER S": "Ofner Sebastian",
    "OFNER SEBASTIAN": "Ofner Sebastian",
    "ALCARAZ C": "Alcaraz Carlos",
    "DJOKOVIC N": "Djokovic Novak",
    "ZVEREV A": "Zverev Alexander",
    "MUSETTI L": "Musetti Lorenzo",
    "RUUD C": "Ruud Casper",
    "CERUNDOLO F": "Cerundolo Francisco",
    "FRITZ T": "Fritz Taylor",
    "RUNE H": "Rune Holger",
    "MEDVEDEV D": "Medvedev Daniil",
    "TSITSIPAS S": "Tsitsipas Stefanos",
    "DE MINAUR A": "De Minaur Alex",
    "DIMITROV G": "Dimitrov Grigor",
    "PAUL T": "Paul Tommy",
    "TIAFOE F": "Tiafoe Frances",
    "LANDALUCE M": "Landaluce Martin",
    "TIRANTE T A": "Tirante Thiago Agustin",
}


BLACKLIST_AVVERSARI = {
    "THE LATEST NEWS",
    "LATEST NEWS",
    "NEWS",
    "DRAW",
    "RESULTS",
    "FIXTURES",
    "STANDINGS",
    "SUMMARY",
    "ODDS",
    "ATP",
    "WTA",
    "TENNIS",
    "ROME",
    "SINGLES",
    "DOUBLES",
    "PREVIEW",
    "HIGHLIGHTS",
    "ADVERTISEMENT",
    "SHOW MORE MATCHES",
}


def normalizza_giocatore(s):
    s = pulisci(s).replace(".", "")
    s = re.sub(r"\([^)]+\)", "", s)
    s = pulisci(s)

    if not s:
        return ""

    up = s.upper()
    if up in NOMI_NOTI:
        return NOMI_NOTI[up]

    return title_name(up)


def cognome_flashscore(s):
    s = pulisci(s).replace(".", "")
    s = re.sub(r"\([^)]+\)", "", s)
    s = pulisci(s)
    if not s:
        return ""
    return s.upper().split()[0]


def giocatore_plausibile(s):
    s = pulisci(s)
    if not s:
        return False

    up = s.upper().replace(".", "")
    if up in BLACKLIST_AVVERSARI:
        return False

    if any(x in up for x in ["LATEST NEWS", "ADVERTISEMENT", "SHOW MORE", "FLASH SCORE"]):
        return False

    if re.fullmatch(r"[\d\s:.\-]+", s):
        return False

    if not re.search(r"[A-Za-zÀ-ÿ]", s):
        return False

    # Evita titoli o sezioni troppo lunghe.
    if len(s) > 40:
        return False

    return True


def avversario_valido(s):
    if not giocatore_plausibile(s):
        return False

    up = s.upper()
    if "SINNER" in up:
        return False

    return True


def parse_data_ora(line):
    line = pulisci(line)
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.\s*(\d{1,2}):(\d{2})", line)
    if not m:
        return "", ""

    g = int(m.group(1))
    mese = int(m.group(2))
    hh = int(m.group(3))
    mm = int(m.group(4))

    if not (1 <= g <= 31 and 1 <= mese <= 12 and 0 <= hh <= 23 and 0 <= mm <= 59):
        return "", ""

    return f"{g:02d}/{mese:02d}/{datetime.now().year}", f"{hh:02d}:{mm:02d}:00"


def to_datetime(data, ora):
    if not data or not ora:
        return None
    try:
        return datetime.strptime(data + " " + ora, "%d/%m/%Y %H:%M:%S")
    except Exception:
        return None


def set_plausibile(a, b):
    if a == b:
        return False
    if a == 6 and 0 <= b <= 4:
        return True
    if b == 6 and 0 <= a <= 4:
        return True
    if a == 7 and b in (5, 6):
        return True
    if b == 7 and a in (5, 6):
        return True
    return False


def conta_set(pairs):
    v1, v2 = 0, 0
    for a, b in pairs:
        if a > b:
            v1 += 1
        elif b > a:
            v2 += 1
    return v1, v2


def ricostruisci_set(resto, set_p1, set_p2):
    n_set = set_p1 + set_p2
    if n_set <= 0 or n_set > 5:
        return []

    nums = []
    for x in resto:
        try:
            nums.append(int(x))
        except Exception:
            pass

    pairs = []
    i = 0

    while i + 1 < len(nums) and len(pairs) < n_set:
        a, b = nums[i], nums[i + 1]
        if not set_plausibile(a, b):
            break

        pairs.append((a, b))
        i += 2

        if (a, b) in [(7, 6), (6, 7)]:
            if i < len(nums) and not (i + 1 < len(nums) and set_plausibile(nums[i], nums[i + 1])):
                i += 1
            if i < len(nums) and not (i + 1 < len(nums) and set_plausibile(nums[i], nums[i + 1])):
                i += 1

    if len(pairs) == n_set and conta_set(pairs) == (set_p1, set_p2):
        return pairs

    return []


def estrai_punteggio_da_numeri(numeri, sinner_primo=True):
    if len(numeri) < 4:
        return ""

    try:
        nums = [int(x) for x in numeri]
    except Exception:
        return ""

    set_p1, set_p2 = nums[0], nums[1]

    if set_p1 not in (0, 1, 2, 3) or set_p2 not in (0, 1, 2, 3):
        return ""

    if set_p1 == set_p2:
        return ""

    pairs = ricostruisci_set(nums[2:], set_p1, set_p2)
    if not pairs:
        return ""

    out = []
    for a, b in pairs:
        out.append(f"{a}-{b}" if sinner_primo else f"{b}-{a}")

    return " ".join(out)


def estrai_game_da_testo(testo):
    up = testo.upper()
    m = re.search(r"\b(0|15|30|40|A|AD)\s*[-:]\s*(0|15|30|40|A|AD)\b", up)
    if not m:
        return ""
    a = m.group(1).replace("AD", "A")
    b = m.group(2).replace("AD", "A")
    return f"{a}-{b}"


def completa_con_game(punteggio, game):
    if not game:
        return punteggio
    parts = punteggio.split() if punteggio else []
    if parts and parts[-1] == game:
        return punteggio
    parts.append(game)
    return " ".join(parts)


def scarica_con_playwright(url):
    from playwright.sync_api import sync_playwright

    t0 = time.perf_counter()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="it-IT",
            timezone_id="Europe/Rome",
            viewport={"width": 1400, "height": 1000},
        )
        page = ctx.new_page()

        page.route(
            "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,ico}",
            lambda route: route.abort()
        )

        page.goto(url, timeout=35000, wait_until="domcontentloaded")

        for sel in [
            "#onetrust-accept-btn-handler",
            "button:has-text('I Accept')",
            "button:has-text('Accept')",
            "button:has-text('Accetta')",
            "[id*='accept']",
            "[class*='accept']",
        ]:
            try:
                page.click(sel, timeout=1200)
                page.wait_for_timeout(400)
                break
            except Exception:
                pass

        page.wait_for_timeout(4500)

        text = page.inner_text("body")

        blocchi = []
        for sel in [".event__match", "[class*='event__match']", "[id^='g_2_']"]:
            try:
                els = page.query_selector_all(sel)
                if els:
                    for el in els:
                        raw = "\n".join(pulisci(x) for x in el.inner_text().splitlines() if pulisci(x))
                        if raw:
                            blocchi.append(raw)
                    break
            except Exception:
                pass

        browser.close()

    return text, blocchi, time.perf_counter() - t0


def parse_lines(lines, fonte, forced_state="", elapsed=0.0):
    found = []

    for i, line in enumerate(lines):
        data, ora = parse_data_ora(line)
        if not data or i + 2 >= len(lines):
            continue

        p1_raw = lines[i + 1]
        p2_raw = lines[i + 2]

        if not giocatore_plausibile(p1_raw) or not giocatore_plausibile(p2_raw):
            continue

        c1 = cognome_flashscore(p1_raw)
        c2 = cognome_flashscore(p2_raw)

        if COGNOME not in (c1, c2):
            continue

        sinner_primo = c1 == COGNOME
        avv_raw = p2_raw if sinner_primo else p1_raw

        if not avversario_valido(avv_raw):
            continue

        avversario = normalizza_giocatore(avv_raw)

        tail = []
        j = i + 3
        while j < len(lines) and j < i + 22:
            d2, _ = parse_data_ora(lines[j])
            if d2:
                break
            tail.append(lines[j])
            j += 1

        tail_text = "\n".join(tail)
        tail_up = tail_text.upper()

        numeri = [t for t in tail if re.fullmatch(r"\d{1,2}", t)]
        punteggio = estrai_punteggio_da_numeri(numeri, sinner_primo=sinner_primo)
        punteggio = completa_con_game(punteggio, estrai_game_da_testo(tail_text))

        dt = to_datetime(data, ora)
        now = datetime.now()

        if forced_state == "fixtures":
            stato = "F"
            punteggio = ""
        elif forced_state == "results":
            stato = "P"
        else:
            live_words = ["LIVE", "SET", "GAME", "BREAK", "1ST", "2ND", "3RD", "4TH", "5TH"]
            if any(w in tail_up for w in live_words):
                stato = "X"
            elif punteggio and dt and dt.date() == now.date() and dt <= now <= dt + timedelta(hours=4):
                stato = "X"
            elif punteggio:
                stato = "P"
            elif dt and dt > now:
                stato = "F"
            else:
                stato = "P"

        found.append(Match(
            stato=stato,
            data=data,
            ora=ora,
            avversario=avversario,
            punteggio=punteggio,
            fonte=fonte,
            recupero_sec=elapsed,
        ))

    return found


def parse_text(text, fonte, forced_state="", elapsed=0.0):
    lines = [pulisci(x) for x in text.splitlines() if pulisci(x)]
    return parse_lines(lines, fonte, forced_state, elapsed)


def parse_dom_blocks(blocks, fonte, forced_state="", elapsed=0.0):
    found = []
    for block in blocks:
        lines = [pulisci(x) for x in block.splitlines() if pulisci(x)]
        if len(lines) == 1:
            one = re.sub(r"(\d{1,2}\.\d{1,2}\.\s+\d{1,2}:\d{2})", r"\n\1\n", lines[0])
            lines = [pulisci(x) for x in one.splitlines() if pulisci(x)]
        found.extend(parse_lines(lines, fonte + "#dom", forced_state, elapsed))
    return found


def match_datetime(m):
    return to_datetime(m.data, m.ora)


def scegli_migliore(matches):
    if not matches:
        return Match("F", "", "", "", "", "fallback", 0.0)

    now = datetime.now()

    live = [m for m in matches if m.stato == "X"]
    if live:
        live.sort(key=lambda m: match_datetime(m) or now, reverse=True)
        return live[0]

    future = []
    for m in matches:
        dt = match_datetime(m)
        if m.stato == "F" and dt and dt >= now - timedelta(minutes=10):
            future.append(m)

    if future:
        future.sort(key=lambda m: match_datetime(m))
        return future[0]

    played = [m for m in matches if m.stato == "P"]
    if played:
        played.sort(key=lambda m: match_datetime(m) or datetime.min, reverse=True)
        return played[0]

    return matches[0]


def frase_siri(m):
    aggiornato = datetime.now().strftime("%H:%M")

    if not m.avversario:
        return f"Non ho trovato la partita di Sinner. Ultimo controllo alle {aggiornato}."

    if m.stato == "X":
        if m.punteggio:
            return (
                f"Sinner contro {m.avversario}. "
                f"Partita in corso. "
                f"Punteggio: {m.punteggio.replace('-', ' a ')}. "
                f"Aggiornato alle {aggiornato}."
            )
        return (
            f"Sinner contro {m.avversario}. "
            f"Partita in corso, ma il punteggio non è ancora disponibile. "
            f"Aggiornato alle {aggiornato}."
        )

    if m.stato == "F":
        quando = ""
        if m.data and m.ora:
            ora_breve = m.ora[:5]
            oggi = datetime.now().strftime("%d/%m/%Y")
            if m.data == oggi:
                quando = f"oggi alle {ora_breve}"
            else:
                quando = f"il {m.data} alle {ora_breve}"
        return f"Sinner giocherà contro {m.avversario}" + (f" {quando}" if quando else "") + f". Ultimo controllo alle {aggiornato}."

    if m.stato == "P":
        if m.punteggio:
            return f"Sinner ha giocato contro {m.avversario}. Risultato: {m.punteggio.replace('-', ' a ')}. Aggiornato alle {aggiornato}."
        return f"Sinner ha giocato contro {m.avversario}. Risultato non disponibile. Aggiornato alle {aggiornato}."

    return f"Situazione Sinner non disponibile. Ultimo controllo alle {aggiornato}."


def scrivi_file(m, total_time):
    frase = frase_siri(m)

    with open(F_TXT, "w", encoding="utf-8") as f:
        f.write(frase + "\n")

    with open(F_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Cognome", "Nome", "Stato", "Data", "Ora", "Avversario", "Punteggio", "Fonte", "TempoRecupero"])
        w.writerow([
            COGNOME,
            NOME,
            m.stato,
            m.data,
            m.ora,
            m.avversario,
            m.punteggio,
            m.fonte,
            f"{total_time:.2f}",
        ])

    log(f"Aggiornato {F_TXT}")
    log(f"Aggiornato {F_CSV}")


def esegui():
    print("=" * 70)
    print(f"SinnerVoce.py - {datetime.now().strftime('%H:%M:%S del %d/%m/%Y')}")
    print("=" * 70)

    t0 = time.perf_counter()
    tutti = []

    for tipo, url in URLS:
        forced = "fixtures" if tipo == "fixtures" else ("results" if tipo == "results" else "")
        log(f"Controllo: {url}")

        try:
            text, blocks, elapsed = scarica_con_playwright(url)
            log(f"  recupero pagina: {elapsed:.2f}s, blocchi: {len(blocks)}")
            rec_text = parse_text(text, url, forced, elapsed)
            rec_dom = parse_dom_blocks(blocks, url, forced, elapsed)
            log(f"  record Sinner: {len(rec_text) + len(rec_dom)}")
            tutti.extend(rec_text)
            tutti.extend(rec_dom)
        except Exception as e:
            log(f"  errore: {e}")

    total = time.perf_counter() - t0
    match = scegli_migliore(tutti)
    scrivi_file(match, total)

    print("\nFRASE PER SIRI:")
    print(frase_siri(match))
    print(f"\nTempo recupero dati: {total:.2f}s")


if __name__ == "__main__":
    esegui()
