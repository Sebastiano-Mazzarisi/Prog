"""
SinnerVoce.py
Versione per GitHub Actions.

Scopo:
- Cerca la situazione di Sinner nelle pagine Flashscore ATP Roma.
- Scrive Tennis/Sinner.txt con una frase leggibile da Siri.
- Scrive Tennis/Sinner-dati.csv con i dati strutturati minimi.

Correzione importante:
- Il turno NON è fisso.
- "ottavi di finale", "quarti di finale", "semifinale", "finale", ecc. vengono usati
  solo se il programma riesce a ricavarli dalla pagina.
- Se il turno non viene trovato con certezza, viene omesso dalla frase invece di inventarlo.

Uso locale:
    python SinnerVoce.py

Su GitHub Actions:
    viene eseguito automaticamente dal workflow .github/workflows/sinner.yml

Nota:
GitHub Actions non è adatto al refresh ogni 10 secondi.
Con il workflow programmato l'aggiornamento realistico è circa ogni 5 minuti.
"""

import os
import re
import csv
import time
from dataclasses import dataclass
from datetime import datetime, timedelta


ROOT = os.path.dirname(os.path.abspath(__file__))
TENNIS_DIR = os.path.join(ROOT, "Tennis")
os.makedirs(TENNIS_DIR, exist_ok=True)

F_TXT = os.path.join(TENNIS_DIR, "Sinner.txt")
F_CSV = os.path.join(TENNIS_DIR, "Sinner-dati.csv")

COGNOME = "SINNER"
NOME = "Jannik"

TORNEO = "Tennis, Roma, Internazionali d'Italia 2026"

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
    stato: str
    data: str
    ora: str
    avversario: str
    punteggio: str
    fonte: str
    turno: str = ""
    recupero_sec: float = 0.0


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
}


ROUND_PATTERNS = [
    # prima i casi più specifici
    (r"\bFINAL(E)?\b|\bFINALE\b", "finale"),
    (r"\bSEMI[- ]?FINAL(S)?\b|\bSEMIFINAL(E|I)\b", "semifinale"),
    (r"\bQUARTER[- ]?FINAL(S)?\b|\bQUARTI\b|\b1/4[- ]?FINAL(S)?\b", "quarti di finale"),
    (r"\b1/8[- ]?FINAL(S)?\b|\bEIGHTH[- ]?FINAL(S)?\b|\bROUND OF 16\b|\bOTTAVI\b", "ottavi di finale"),
    (r"\bROUND OF 32\b|\b1/16[- ]?FINAL(S)?\b|\bSEDICESIMI\b", "sedicesimi di finale"),
    (r"\bROUND OF 64\b|\b1/32[- ]?FINAL(S)?\b|\bTRENTADUESIMI\b", "trentaduesimi di finale"),
    (r"\bROUND OF 128\b|\b1/64[- ]?FINAL(S)?\b", "sessantaquattresimi di finale"),
    (r"\bQUALIFICATION\b|\bQUALIFICAZIONI\b|\bQUALIFYING\b", "qualificazioni"),
]


def normalizza_turno(line):
    """
    Prova a capire se una riga della pagina Flashscore indica il turno.

    Flashscore può usare intestazioni diverse a seconda della lingua:
    - Quarter-finals
    - Semi-finals
    - Final
    - 1/8-finals
    - Round of 16
    - Ottavi di finale
    ecc.

    Restituisce una stringa italiana pronta per Siri, oppure "".
    """
    s = pulisci(line)
    if not s:
        return ""

    up = s.upper()

    # Evita falsi positivi su righe troppo lunghe, pubblicità o descrizioni generiche.
    if len(up) > 70:
        return ""

    for pattern, turno in ROUND_PATTERNS:
        if re.search(pattern, up):
            return turno

    return ""


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


def parse_lines(lines, fonte, forced_state="", elapsed=0.0, turno_default=""):
    found = []
    turno_corrente = turno_default

    for i, line in enumerate(lines):
        turno_trovato = normalizza_turno(line)
        if turno_trovato:
            turno_corrente = turno_trovato
            continue

        data, ora = parse_data_ora(line)
        if not data or i + 2 >= len(lines):
            continue

        p1_raw = lines[i + 1]
        p2_raw = lines[i + 2]

        c1 = cognome_flashscore(p1_raw)
        c2 = cognome_flashscore(p2_raw)

        if COGNOME not in (c1, c2):
            continue

        sinner_primo = c1 == COGNOME
        avversario = normalizza_giocatore(p2_raw if sinner_primo else p1_raw)

        tail = []
        j = i + 3
        while j < len(lines) and j < i + 22:
            d2, _ = parse_data_ora(lines[j])
            if d2:
                break

            turno_tail = normalizza_turno(lines[j])
            if turno_tail:
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
            turno=turno_corrente,
            recupero_sec=elapsed,
        ))

    return found


def parse_text(text, fonte, forced_state="", elapsed=0.0):
    lines = [pulisci(x) for x in text.splitlines() if pulisci(x)]
    return parse_lines(lines, fonte, forced_state, elapsed)


def parse_dom_blocks(blocks, fonte, forced_state="", elapsed=0.0):
    """
    I blocchi DOM spesso contengono solo la singola partita, senza l'intestazione del turno.
    Per questo motivo il turno viene preso soprattutto da parse_text().
    Se dentro il blocco compare una riga di turno, viene comunque usata.
    """
    found = []
    for block in blocks:
        lines = [pulisci(x) for x in block.splitlines() if pulisci(x)]
        if len(lines) == 1:
            one = lines[0]
            one = re.sub(r"(\d{1,2}\.\d{1,2}\.\s+\d{1,2}:\d{2})", r"\n\1\n", one)
            lines = [pulisci(x) for x in one.splitlines() if pulisci(x)]
        found.extend(parse_lines(lines, fonte + "#dom", forced_state, elapsed))
    return found


def match_datetime(m):
    return to_datetime(m.data, m.ora)


def punteggio_match(m):
    """
    Serve solo per scegliere il record migliore quando la stessa partita viene letta
    sia dal testo pagina sia dal DOM.
    """
    score = 0
    if m.avversario:
        score += 10
    if m.data and m.ora:
        score += 10
    if m.turno:
        score += 8
    if m.punteggio:
        score += 6
    if "#dom" in m.fonte:
        score += 2
    return score


def unisci_record_stessa_partita(matches):
    """
    Quando Flashscore viene letto da più pagine, la stessa partita può apparire più volte.
    Unisco i duplicati conservando le informazioni più complete, soprattutto il turno.
    """
    per_chiave = {}

    for m in matches:
        chiave = (
            m.stato,
            m.data,
            m.ora,
            m.avversario.upper(),
        )

        if chiave not in per_chiave:
            per_chiave[chiave] = m
            continue

        old = per_chiave[chiave]

        migliore = old
        if punteggio_match(m) > punteggio_match(old):
            migliore = m

        # Conserva il turno se uno dei due record lo ha.
        turno = old.turno or m.turno
        punteggio = old.punteggio or m.punteggio
        fonte = migliore.fonte

        per_chiave[chiave] = Match(
            stato=migliore.stato,
            data=migliore.data,
            ora=migliore.ora,
            avversario=migliore.avversario,
            punteggio=punteggio,
            fonte=fonte,
            turno=turno,
            recupero_sec=migliore.recupero_sec,
        )

    return list(per_chiave.values())


def scegli_migliore(matches):
    if not matches:
        return Match("F", "", "", "", "", "fallback", "", 0.0)

    matches = unisci_record_stessa_partita(matches)
    now = datetime.now()

    live = [m for m in matches if m.stato == "X"]
    if live:
        live.sort(key=lambda m: (punteggio_match(m), match_datetime(m) or now), reverse=True)
        return live[0]

    future = []
    for m in matches:
        dt = match_datetime(m)
        if m.stato == "F" and dt and dt >= now - timedelta(minutes=10):
            future.append(m)

    if future:
        future.sort(key=lambda m: (match_datetime(m), -punteggio_match(m)))
        return future[0]

    played = [m for m in matches if m.stato == "P"]
    if played:
        played.sort(key=lambda m: (match_datetime(m) or datetime.min, punteggio_match(m)), reverse=True)
        return played[0]

    matches.sort(key=punteggio_match, reverse=True)
    return matches[0]


MESI = {
    1: "gennaio",
    2: "febbraio",
    3: "marzo",
    4: "aprile",
    5: "maggio",
    6: "giugno",
    7: "luglio",
    8: "agosto",
    9: "settembre",
    10: "ottobre",
    11: "novembre",
    12: "dicembre",
}

GIORNI = {
    0: "lunedì",
    1: "martedì",
    2: "mercoledì",
    3: "giovedì",
    4: "venerdì",
    5: "sabato",
    6: "domenica",
}


def format_data_parlata(data):
    try:
        d = datetime.strptime(data, "%d/%m/%Y")
        return f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month]} {d.year}"
    except Exception:
        return data


def format_ora_parlata(ora):
    if not ora:
        return ""

    try:
        hh, mm, _ = ora.split(":")
        hh = int(hh)
        mm = int(mm)
        if mm == 0:
            return str(hh)
        return f"{hh} e {mm:02d}"
    except Exception:
        return ora[:5]


def format_aggiornato():
    adesso = datetime.now()
    h = adesso.hour
    m = adesso.minute
    if m == 0:
        return f"{h}"
    return f"{h} e {m:02d}"


def frase_turno(m):
    """
    Restituisce ', quarti di finale' oppure stringa vuota.
    Il turno viene scritto solo se è stato letto davvero.
    """
    if not m.turno:
        return ""
    return f", {m.turno}"


def frase_siri(m):
    aggiornato = format_aggiornato()
    prefisso = TORNEO + frase_turno(m)

    if not m.avversario:
        return f"{TORNEO}. Non ho trovato la partita di Sinner. Ultimo controllo alle {aggiornato} di oggi."

    if m.stato == "X":
        if m.punteggio:
            return (
                f"{prefisso}, Sinner sta giocando contro {m.avversario}. "
                f"Punteggio: {m.punteggio.replace('-', ' a ')}. "
                f"Dati aggiornati alle {aggiornato} di oggi."
            )
        return (
            f"{prefisso}, Sinner sta probabilmente giocando contro {m.avversario}. "
            f"Non ho ancora letto il punteggio. "
            f"Dati aggiornati alle {aggiornato} di oggi."
        )

    if m.stato == "F":
        quando = ""
        if m.data and m.ora:
            quando = f" {format_data_parlata(m.data)}, alle ore {format_ora_parlata(m.ora)}"

        return (
            f"{prefisso}, Sinner giocherà contro {m.avversario}"
            + quando
            + f". Dati aggiornati alle {aggiornato} di oggi."
        )

    if m.stato == "P":
        if m.punteggio:
            return (
                f"{prefisso}, Sinner ha giocato contro {m.avversario}. "
                f"Risultato: {m.punteggio.replace('-', ' a ')}. "
                f"Dati aggiornati alle {aggiornato} di oggi."
            )
        return (
            f"{prefisso}, Sinner ha giocato contro {m.avversario}. "
            f"Risultato non disponibile. "
            f"Dati aggiornati alle {aggiornato} di oggi."
        )

    return f"{TORNEO}. Situazione Sinner non disponibile. Ultimo controllo alle {aggiornato} di oggi."


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
            "Turno",
            "Avversario",
            "Punteggio",
            "Fonte",
            "TempoRecupero",
        ])
        w.writerow([
            COGNOME,
            NOME,
            m.stato,
            m.data,
            m.ora,
            m.turno,
            m.avversario,
            m.punteggio,
            m.fonte,
            f"{total_time:.2f}",
        ])

    log("File aggiornati:")
    log(f"  {F_TXT}")
    log(f"  {F_CSV}")


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

    frase = frase_siri(match)
    print("\nFRASE PER SIRI:")
    print(frase)
    print(f"\nTempo recupero dati: {total:.2f}s")

    return match.stato == "X"


def main():
    esegui()


if __name__ == "__main__":
    main()
