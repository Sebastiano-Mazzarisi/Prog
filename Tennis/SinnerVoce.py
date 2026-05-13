"""
SinnerVoce.py
Versione per GitHub Actions.

Scopo:
- Cerca la situazione di Sinner nelle pagine Flashscore ATP Roma.
- Scrive Tennis/Sinner.txt con una frase leggibile da Siri.
- Scrive Tennis/Sinner-dati.csv con i dati strutturati minimi.
- Durante una partita live può restare attivo e aggiornare il file più volte.
- Permette anche una simulazione usando una partita live qualsiasi, senza aspettare Sinner.

Uso locale:
    python SinnerVoce.py

Uso locale simulazione live:
    python SinnerVoce.py --test-live

Uso locale simulando un altro giocatore:
    python SinnerVoce.py --giocatore RUUD --nome Casper

Su GitHub Actions:
    viene eseguito automaticamente dal workflow .github/workflows/sinner.yml

Nota:
GitHub Actions non è adatto a un refresh ogni 10 secondi tramite cron.
Per aggiornare durante il match, questo script può restare in esecuzione
e ripetere il controllo ogni LIVE_INTERVAL_SEC secondi.
"""

import os
import re
import csv
import sys
import time
import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta


ROOT = os.path.dirname(os.path.abspath(__file__))

# Se lo script è già nella cartella Tennis, scrive lì.
# Se invece è nella root del progetto, scrive nella sottocartella Tennis.
if os.path.basename(ROOT).lower() == "tennis":
    TENNIS_DIR = ROOT
else:
    TENNIS_DIR = os.path.join(ROOT, "Tennis")

os.makedirs(TENNIS_DIR, exist_ok=True)

F_TXT = os.path.join(TENNIS_DIR, "Sinner.txt")
F_CSV = os.path.join(TENNIS_DIR, "Sinner-dati.csv")

NOME_TORNEO = "Tennis, Roma, Internazionali d'Italia 2026"

DEFAULT_COGNOME = "SINNER"
DEFAULT_NOME = "Jannik"

COGNOME = os.environ.get("SINNER_COGNOME", DEFAULT_COGNOME).strip().upper()
NOME = os.environ.get("SINNER_NOME", DEFAULT_NOME).strip()

# Se LIVE_LOOP=1, quando trova una partita live resta acceso e aggiorna il file.
LIVE_LOOP = os.environ.get("LIVE_LOOP", "1").strip().lower() not in ("0", "no", "false")
LIVE_INTERVAL_SEC = int(os.environ.get("LIVE_INTERVAL_SEC", "60"))
LIVE_MAX_MINUTES = int(os.environ.get("LIVE_MAX_MINUTES", "180"))

URLS = [
    ("main", "https://www.flashscore.com/tennis/atp-singles/rome/"),
    ("fixtures", "https://www.flashscore.com/tennis/atp-singles/rome/fixtures/"),
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
    stato: str          # F=futuro, X=live, P=passato
    data: str
    ora: str
    avversario: str
    punteggio: str
    fonte: str
    recupero_sec: float = 0.0
    giocatore: str = ""
    raw: str = ""


def pulisci(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def title_name(s):
    return " ".join(
        p[:1].upper() + p[1:].lower()
        for p in pulisci(s).split()
    )


NOMI_NOTI = {
    "POPYRIN A": "Popyrin Alexei",
    "OFNER S": "Ofner Sebastian",
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
    "RUBLEV A": "Rublev Andrey",
    "KHACHANOV K": "Khachanov Karen",
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


def solo_cognome(s):
    """
    Flashscore spesso scrive "Rublev A" oppure la normalizzazione produce
    "Rublev Andrey". Per la frase Siri usiamo solo il cognome.
    """
    s = normalizza_giocatore(s)
    if not s:
        return ""
    return s.split()[0]


def cognome_flashscore(s):
    s = pulisci(s).replace(".", "")
    s = re.sub(r"\([^)]+\)", "", s)
    s = pulisci(s)
    if not s:
        return ""
    return s.upper().split()[0]


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

    data = f"{g:02d}/{mese:02d}/{datetime.now().year}"
    ora = f"{hh:02d}:{mm:02d}:00"
    return data, ora


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
    v1 = 0
    v2 = 0
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
        a = nums[i]
        b = nums[i + 1]
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

    elapsed = time.perf_counter() - t0
    return text, blocchi, elapsed


def parse_lines(lines, fonte, forced_state="", elapsed=0.0, target_cognome=None):
    """
    Vecchio parser: funziona quando il blocco contiene una riga data/ora.
    Lo manteniamo per fixtures e risultati.
    """
    if target_cognome is None:
        target_cognome = COGNOME

    found = []

    for i, line in enumerate(lines):
        data, ora = parse_data_ora(line)
        if not data or i + 2 >= len(lines):
            continue

        p1_raw = lines[i + 1]
        p2_raw = lines[i + 2]

        c1 = cognome_flashscore(p1_raw)
        c2 = cognome_flashscore(p2_raw)

        if target_cognome not in (c1, c2):
            continue

        target_primo = c1 == target_cognome
        avversario = solo_cognome(p2_raw if target_primo else p1_raw)
        giocatore = solo_cognome(p1_raw if target_primo else p2_raw)

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
        punteggio = estrai_punteggio_da_numeri(numeri, sinner_primo=target_primo)
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
            elif dt and dt <= now <= dt + timedelta(hours=4):
                stato = "X"
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
            giocatore=giocatore,
            raw="\n".join(lines[i:j]),
        ))

    return found


def sembra_giocatore(line):
    line = pulisci(line)
    if not line:
        return False
    up = line.upper()
    if parse_data_ora(line)[0]:
        return False
    if up in {"ATP", "WTA", "SINGLES", "DOUBLES", "STANDINGS", "DRAW", "LIVE", "FINISHED", "SCHEDULE"}:
        return False
    if re.fullmatch(r"\d{1,2}", line):
        return False
    if re.fullmatch(r"(0|15|30|40|A|AD)\s*[-:]\s*(0|15|30|40|A|AD)", up):
        return False
    # Nomi tipo "Sinner J", "Rublev A", "Carlos Alcaraz".
    return bool(re.search(r"[A-Za-zÀ-ÿ]", line)) and len(line) <= 40


def parse_live_block(lines, fonte, elapsed=0.0, target_cognome=None, accetta_primo_live=False):
    """
    Nuovo parser: serve per i live.
    Su Flashscore un match live può non avere più la riga "13.05. 15:00".
    Il vecchio parser lo saltava perché pretendeva sempre la data/ora.
    Qui cerchiamo invece due righe consecutive che sembrano giocatori
    e vicino a loro parole/punteggi da live.
    """
    if target_cognome is None:
        target_cognome = COGNOME

    found = []
    joined = "\n".join(lines)
    up_joined = joined.upper()

    live_words = ["LIVE", "SET", "GAME", "BREAK", "1ST", "2ND", "3RD", "4TH", "5TH"]
    has_live_hint = any(w in up_joined for w in live_words)
    has_point_score = bool(re.search(r"\b(0|15|30|40|A|AD)\s*[-:]\s*(0|15|30|40|A|AD)\b", up_joined))
    # Attenzione: NON basta trovare molti numeri per dire che una partita è live.
    # Un risultato finale tipo 6-2 6-3 contiene numeri, ma non è live.
    # Quindi qui accettiamo il blocco live solo se troviamo parole da live
    # oppure un punteggio di game tipo 15-30, 40-A, ecc.
    if not (has_live_hint or has_point_score):
        return found

    for i in range(len(lines) - 1):
        p1_raw = lines[i]
        p2_raw = lines[i + 1]

        if not (sembra_giocatore(p1_raw) and sembra_giocatore(p2_raw)):
            continue

        c1 = cognome_flashscore(p1_raw)
        c2 = cognome_flashscore(p2_raw)

        if c1 == c2:
            continue

        if accetta_primo_live:
            target_here = c1
        else:
            if target_cognome not in (c1, c2):
                continue
            target_here = target_cognome

        target_primo = c1 == target_here
        avversario = solo_cognome(p2_raw if target_primo else p1_raw)
        giocatore = solo_cognome(p1_raw if target_primo else p2_raw)

        tail = lines[i + 2:i + 18]
        tail_text = "\n".join(tail)
        numeri = [t for t in tail if re.fullmatch(r"\d{1,2}", t)]
        punteggio = estrai_punteggio_da_numeri(numeri, sinner_primo=target_primo)
        punteggio = completa_con_game(punteggio, estrai_game_da_testo(tail_text + "\n" + joined))

        found.append(Match(
            stato="X",
            data=datetime.now().strftime("%d/%m/%Y"),
            ora=datetime.now().strftime("%H:%M:%S"),
            avversario=avversario,
            punteggio=punteggio,
            fonte=fonte + "#live",
            recupero_sec=elapsed,
            giocatore=giocatore,
            raw=joined,
        ))

        if accetta_primo_live:
            return found

    return found


def parse_text(text, fonte, forced_state="", elapsed=0.0, target_cognome=None):
    lines = [pulisci(x) for x in text.splitlines() if pulisci(x)]
    return parse_lines(lines, fonte, forced_state, elapsed, target_cognome=target_cognome)


def parse_dom_blocks(blocks, fonte, forced_state="", elapsed=0.0, target_cognome=None, test_live=False):
    found = []
    for block in blocks:
        lines = [pulisci(x) for x in block.splitlines() if pulisci(x)]
        if len(lines) == 1:
            one = lines[0]
            one = re.sub(r"(\d{1,2}\.\d{1,2}\.\s+\d{1,2}:\d{2})", r"\n\1\n", one)
            lines = [pulisci(x) for x in one.splitlines() if pulisci(x)]

        # Prima provo il parser nuovo per i live senza data/ora.
        found.extend(parse_live_block(
            lines,
            fonte,
            elapsed=elapsed,
            target_cognome=target_cognome,
            accetta_primo_live=test_live,
        ))

        # Poi mantengo il parser classico.
        found.extend(parse_lines(lines, fonte + "#dom", forced_state, elapsed, target_cognome=target_cognome))

    return found


def match_datetime(m):
    return to_datetime(m.data, m.ora)


def scegli_migliore(matches):
    if not matches:
        return Match("F", "", "", "", "", "fallback", 0.0, giocatore=solo_cognome(COGNOME))

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


def ora_in_parole(hhmm):
    try:
        hh, mm = hhmm.split(":")[:2]
        hh = int(hh)
        mm = int(mm)
        if mm == 0:
            return f"{hh}"
        return f"{hh} e {mm:02d}"
    except Exception:
        return hhmm


def data_in_parole(data):
    try:
        d = datetime.strptime(data, "%d/%m/%Y")
    except Exception:
        return data

    giorni = [
        "lunedì", "martedì", "mercoledì", "giovedì",
        "venerdì", "sabato", "domenica"
    ]
    mesi = [
        "", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"
    ]
    return f"{giorni[d.weekday()]} {d.day} {mesi[d.month]} {d.year}"


def nome_voce_giocatore(m):
    # In modalità normale vogliamo dire sempre Sinner.
    # Però in modalità test-live, se il parser ha trovato una partita live
    # di un altro giocatore, usiamo il cognome reale trovato nel blocco.
    if m.giocatore:
        if m.giocatore.upper() != "SINNER":
            return m.giocatore
        return "Sinner"

    if COGNOME == "SINNER":
        return "Sinner"

    return solo_cognome(COGNOME)


def frase_siri(m):
    aggiornato = datetime.now().strftime("%H:%M")
    aggiornato_parole = ora_in_parole(aggiornato)
    giocatore = nome_voce_giocatore(m)

    if not m.avversario:
        return f"{NOME_TORNEO}, non ho trovato la partita di {giocatore}. Ultimo controllo alle {aggiornato_parole}."

    if m.stato == "X":
        if m.punteggio:
            return (
                f"{NOME_TORNEO}, {giocatore} sta giocando contro {m.avversario}. "
                f"Punteggio: {m.punteggio.replace('-', ' a ')}. "
                f"Dati aggiornati alle {aggiornato_parole} di oggi."
            )
        return (
            f"{NOME_TORNEO}, {giocatore} sta probabilmente giocando contro {m.avversario}. "
            f"Non ho ancora letto il punteggio. "
            f"Dati aggiornati alle {aggiornato_parole} di oggi."
        )

    if m.stato == "F":
        quando = ""
        if m.data and m.ora:
            ora_breve = m.ora[:5]
            oggi = datetime.now().strftime("%d/%m/%Y")
            if m.data == oggi:
                quando = f"oggi alle ore {ora_in_parole(ora_breve)}"
            else:
                quando = f"{data_in_parole(m.data)}, alle ore {ora_in_parole(ora_breve)}"
        return (
            f"{NOME_TORNEO}, {giocatore} giocherà contro {m.avversario}"
            + (f" {quando}" if quando else "")
            + f". Dati aggiornati alle {aggiornato_parole} di oggi."
        )

    if m.stato == "P":
        if m.punteggio:
            return (
                f"{NOME_TORNEO}, {giocatore} ha giocato contro {m.avversario}. "
                f"Risultato: {m.punteggio.replace('-', ' a ')}. "
                f"Dati aggiornati alle {aggiornato_parole} di oggi."
            )
        return (
            f"{NOME_TORNEO}, {giocatore} ha giocato contro {m.avversario}. "
            f"Risultato non disponibile. "
            f"Dati aggiornati alle {aggiornato_parole} di oggi."
        )

    return f"{NOME_TORNEO}, situazione {giocatore} non disponibile. Ultimo controllo alle {aggiornato_parole}."


def scrivi_file(m, total_time):
    frase = frase_siri(m)

    with open(F_TXT, "w", encoding="utf-8") as f:
        f.write(frase + "\n")

    with open(F_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([
            "Cognome",
            "Nome",
            "Stato",
            "Data",
            "Ora",
            "Avversario",
            "Punteggio",
            "Fonte",
            "TempoRecupero",
            "Giocatore",
            "Raw",
        ])
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
            m.giocatore,
            m.raw[:1000].replace("\n", " | "),
        ])

    log("File aggiornati:")
    log(f"  {F_TXT}")
    log(f"  {F_CSV}")


def esegui(test_live=False, target_cognome=None):
    global COGNOME, NOME

    if target_cognome:
        COGNOME = target_cognome.strip().upper()

    print("=" * 70)
    print(f"SinnerVoce.py - {datetime.now().strftime('%H:%M:%S del %d/%m/%Y')}")
    if test_live:
        print("MODALITÀ TEST: userò la prima partita live trovata.")
    else:
        print(f"Giocatore seguito: {COGNOME}")
    print("=" * 70)

    t0 = time.perf_counter()
    tutti = []

    for tipo, url in URLS:
        forced = "fixtures" if tipo == "fixtures" else ("results" if tipo == "results" else "")
        log(f"Controllo: {url}")

        try:
            text, blocks, elapsed = scarica_con_playwright(url)
            log(f"  recupero pagina: {elapsed:.2f}s, blocchi: {len(blocks)}")

            if not test_live:
                rec_text = parse_text(text, url, forced, elapsed, target_cognome=COGNOME)
            else:
                rec_text = []

            rec_dom = parse_dom_blocks(
                blocks,
                url,
                forced,
                elapsed,
                target_cognome=COGNOME,
                test_live=test_live,
            )

            log(f"  record trovati: {len(rec_text) + len(rec_dom)}")
            tutti.extend(rec_text)
            tutti.extend(rec_dom)

            # In test live basta trovare una partita live, non serve scaricare tutto.
            if test_live and any(m.stato == "X" for m in tutti):
                break

        except Exception as e:
            log(f"  errore: {e}")

    total = time.perf_counter() - t0
    match = scegli_migliore(tutti)
    scrivi_file(match, total)

    frase = frase_siri(match)
    print("\nFRASE PER SIRI:")
    print(frase)
    print(f"\nTempo recupero dati: {total:.2f}s")

    return match.stato == "X", match


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--giocatore", default="", help="Cognome del giocatore da seguire, es. RUUD")
    parser.add_argument("--nome", default="", help="Nome del giocatore, es. Casper")
    parser.add_argument("--test-live", action="store_true", help="Usa la prima partita live trovata, per provare senza aspettare Sinner")
    parser.add_argument("--once", action="store_true", help="Esegue un solo controllo e poi termina")
    args = parser.parse_args()

    global COGNOME, NOME

    if args.giocatore:
        COGNOME = args.giocatore.strip().upper()
    if args.nome:
        NOME = args.nome.strip()

    live, match = esegui(test_live=args.test_live, target_cognome=COGNOME)

    if args.once or not LIVE_LOOP:
        return

    if not live:
        return

    start = time.time()
    max_seconds = LIVE_MAX_MINUTES * 60

    log(f"Partita live trovata. Aggiornamento automatico ogni {LIVE_INTERVAL_SEC} secondi.")
    while True:
        elapsed = time.time() - start
        if elapsed >= max_seconds:
            log("Raggiunto tempo massimo live. Termino.")
            break

        time.sleep(LIVE_INTERVAL_SEC)

        live, match = esegui(test_live=args.test_live, target_cognome=COGNOME)
        if not live:
            log("La partita non risulta più live. Termino il ciclo.")
            break


if __name__ == "__main__":
    main()
