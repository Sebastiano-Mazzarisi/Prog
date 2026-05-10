# Tennis.py
# Pubblica su GitHub Pages la situazione dei tennisti italiani agli Internazionali d'Italia.
#
# Legge:
# - dati.json
# - meta.json, se presente
#
# Pubblica:
# - Tennis.html
# - Tennis.txt
# - dati.json
# - meta.json, se presente
#
# Refresh:
# - se c'è almeno un LIVE: 6 secondi
# - se non c'è LIVE: 60 secondi
#
# Uscita:
# - premi INVIO nella console

import base64
import csv
import io
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
import unicodedata


DIR = os.path.dirname(os.path.abspath(__file__))

F_HTML = os.path.join(DIR, "Tennis.html")
F_TXT = os.path.join(DIR, "Tennis.txt")
F_JSON = os.path.join(DIR, "dati.json")
F_META = os.path.join(DIR, "meta.json")
F_ICON = os.path.join(DIR, "tennis_icon.png")
F_TOKEN = os.path.join(DIR, "token.txt")
F_RANKING_CACHE = os.path.join(DIR, "ranking_cache.json")

DATA_FINE = "17/05/2026"
VERSIONE_SCRIPT = "2026-05-10-rank-avversari-v8"

GITHUB_USER = "Sebastiano-Mazzarisi"
GITHUB_REPO = "Prog"
GITHUB_BRANCH = "main"

INTERVALLO_LIVE = 6
INTERVALLO_NORMAL = 60
PUNTINO_LIVE = 2
PUNTINO_NORMAL = 3

# Le classifiche ATP/WTA vengono scaricate al massimo una volta al giorno.
# Ho scelto le 06:00 perché di solito è un orario tranquillo e non disturba
# i controlli live del torneo. Se la cache manca, vengono scaricate subito.
ORA_AGGIORNAMENTO_RANKING = 6

URL_ATP_RANKINGS = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_rankings_current.csv"
URL_ATP_PLAYERS = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_players.csv"
URL_WTA_RANKINGS = "https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_rankings_current.csv"
URL_WTA_PLAYERS = "https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_players.csv"

GIOCATRICI_WTA = {
    "PAOLINI",
    "COCCIARETTO",
    "GRANT",
    "BASILETTI",
}

# Piccola rete di sicurezza: se il download della classifica non trova subito un nome
# ma la posizione è nota dalla cache precedente, non lasciamo vuoto il cartellino.
# Viene usata solo se la fonte principale non restituisce nulla.
RANKING_FALLBACK = {
    ("ATP", "SINNER"): 1,
    ("ATP", "POPYRIN"): 25,
    ("ATP", "CERUNDOLO"): 18,
    ("WTA", "COCCIARETTO"): 81,
    ("WTA", "SWIATEK"): 2,
}

# Correzioni manuali di sicurezza: hanno precedenza anche sulla cache scaricata.
# Servono quando la fonte automatica è in ritardo o contiene una classifica non allineata.
# In questo momento Sinner deve essere mostrato come ATP n.1.
RANKING_CORREZIONI = {
    ("ATP", "SINNER"): 1,
}


def ora_adesso():
    return datetime.now().strftime("%H:%M:%S del %d/%m/%Y")


def leggi_token():
    try:
        with open(F_TOKEN, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def carica_icon_b64():
    if not os.path.exists(F_ICON):
        return ""
    try:
        with open(F_ICON, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""


ICON_B64 = carica_icon_b64()


def carica_dati():
    try:
        with open(F_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"ERRORE lettura dati.json: {e}")
        return []


def carica_meta():
    if not os.path.exists(F_META):
        return {}
    try:
        with open(F_META, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return meta if isinstance(meta, dict) else {}
    except Exception:
        return {}


def data_key(data_testo):
    if not data_testo:
        return 99999999
    try:
        g, m = str(data_testo).split("/")[:2]
        return datetime.now().year * 10000 + int(m) * 100 + int(g)
    except Exception:
        return 99999999


def orario_key(orario):
    if not orario:
        return 9999
    testo = str(orario).lower().replace(".", ":")
    import re
    m = re.search(r"(\d{1,2}):(\d{2})", testo)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return 9999


def ordine_giocatore(g):
    stato = g.get("stato", "")
    p = g.get("prossimo") or {}

    if stato == "live":
        return (0, data_key(p.get("data")), -1, g.get("nome", ""))
    if stato in ("next", "ok"):
        return (1, data_key(p.get("data")), orario_key(p.get("orario")), g.get("nome", ""))
    if stato == "elim":
        return (9, 99999999, 9999, g.get("nome", ""))
    return (5, 99999999, 9999, g.get("nome", ""))


def dati_ordinati(DATA):
    return sorted(DATA, key=ordine_giocatore)


def c_live(DATA):
    return any(g.get("stato") == "live" for g in DATA)






# -----------------------------------------------------------------------------
# Classifiche ATP/WTA aggiornate una volta al giorno
# -----------------------------------------------------------------------------
def oggi_iso():
    return datetime.now().date().isoformat()


def normalizza_nome(testo):
    testo = str(testo or "").strip().upper()
    testo = unicodedata.normalize("NFKD", testo)
    testo = "".join(c for c in testo if not unicodedata.combining(c))
    testo = re.sub(r"[^A-Z0-9 ]+", " ", testo)
    testo = re.sub(r"\s+", " ", testo).strip()
    return testo


def leggi_ranking_cache():
    if not os.path.exists(F_RANKING_CACHE):
        return {}
    try:
        with open(F_RANKING_CACHE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return cache if isinstance(cache, dict) else {}
    except Exception:
        return {}


def salva_ranking_cache(cache):
    try:
        with open(F_RANKING_CACHE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"ATTENZIONE: impossibile salvare ranking_cache.json: {e}")
        return False


def cache_ranking_valida(cache):
    if not cache:
        return False
    if cache.get("data") != oggi_iso():
        return False
    return isinstance(cache.get("players"), dict) and bool(cache.get("players"))


def devo_aggiornare_ranking(cache):
    if not cache_ranking_valida(cache):
        return True
    return False


def scarica_testo(url, timeout=20):
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 TennisTracker-Nino",
                "Accept": "text/csv,text/plain,*/*",
                "Accept-Language": "it-IT,it;q=0.9,en;q=0.7",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return raw.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"ATTENZIONE: classifica non scaricata da {url}: {e}")
        return ""


def righe_csv(testo):
    if not testo:
        return []
    return list(csv.reader(io.StringIO(testo)))


def crea_indice_giocatori(players_csv):
    indice = {}
    for r in righe_csv(players_csv):
        if len(r) < 3:
            continue
        if r[0].strip().lower() in ("player_id", "id"):
            continue
        player_id = r[0].strip()
        first = r[1].strip()
        last = r[2].strip()
        if not player_id or not last:
            continue
        full = normalizza_nome((first + " " + last).strip())
        surname = normalizza_nome(last)
        indice[player_id] = {
            "first": first,
            "last": last,
            "full": full,
            "surname": surname,
        }
    return indice


def crea_classifica_tour(tour, rankings_csv, players_csv):
    players = crea_indice_giocatori(players_csv)
    risultati = {}

    for r in righe_csv(rankings_csv):
        if len(r) < 3:
            continue
        if r[0].strip().lower() in ("ranking_date", "date"):
            continue

        # Nei file Jeff Sackmann il formato più comune è:
        # ranking_date, rank, player_id, points
        # ma gestisco anche eventuali varianti con intestazioni o 3 colonne.
        try:
            if len(r[0].strip()) == 8 and r[0].strip().isdigit():
                rank = int(r[1])
                player_id = r[2].strip()
                points = r[3].strip() if len(r) > 3 else ""
            else:
                rank = int(r[0])
                player_id = r[1].strip()
                points = r[2].strip() if len(r) > 2 else ""
        except Exception:
            continue

        info = players.get(player_id)
        if not info:
            continue

        item = {
            "tour": tour,
            "pos": rank,
            "punti": points,
            "nome_completo": (info["first"] + " " + info["last"]).strip(),
        }

        # Chiave per cognome: utile per i tuoi dati, dove il nome è quasi sempre il cognome.
        surname = info["surname"]
        if surname and surname not in risultati:
            risultati[surname] = item

        # Chiave per nome completo: utile se in futuro inserisci anche nome + cognome.
        full = info["full"]
        if full and full not in risultati:
            risultati[full] = item

    return risultati


def scarica_classifiche():
    atp_rankings = scarica_testo(URL_ATP_RANKINGS)
    atp_players = scarica_testo(URL_ATP_PLAYERS)
    wta_rankings = scarica_testo(URL_WTA_RANKINGS)
    wta_players = scarica_testo(URL_WTA_PLAYERS)

    players = {}
    if atp_rankings and atp_players:
        players.update(crea_classifica_tour("ATP", atp_rankings, atp_players))
    if wta_rankings and wta_players:
        players.update(crea_classifica_tour("WTA", wta_rankings, wta_players))

    return {
        "data": oggi_iso(),
        "aggiornato": ora_adesso(),
        "fonte": "Jeff Sackmann tennis_atp/tennis_wta",
        "players": players,
    }


def tour_giocatore(nome):
    return "WTA" if normalizza_nome(nome) in GIOCATRICI_WTA else "ATP"


def formato_ranking(ranking):
    if not ranking or not ranking.get("pos"):
        return ""
    return f"{ranking.get('tour', '')} n.{ranking.get('pos')}"


def trova_ranking_nome(nome, cache, tour_atteso=None):
    nome_norm = normalizza_nome(nome)
    if not nome_norm:
        return None

    # 1) Prima guardo le correzioni manuali: devono prevalere anche su una cache errata.
    pos_corretta = RANKING_CORREZIONI.get((tour_atteso or "", nome_norm))
    if pos_corretta:
        item = {"tour": tour_atteso or "", "pos": pos_corretta, "punti": "", "fonte_extra": "correzione manuale"}
    else:
        players = cache.get("players") or {}
        item = players.get(nome_norm)

        if item and tour_atteso and item.get("tour") != tour_atteso:
            item = None

        if not item:
            pos_fallback = RANKING_FALLBACK.get((tour_atteso or "", nome_norm))
            if not pos_fallback:
                return None
            item = {"tour": tour_atteso or "", "pos": pos_fallback, "punti": "", "fonte_extra": "fallback interno"}

    return {
        "tour": item.get("tour", tour_atteso or ""),
        "pos": item.get("pos"),
        "punti": item.get("punti", ""),
        "aggiornato": cache.get("aggiornato", ""),
        "fonte": item.get("fonte_extra") or cache.get("fonte", "") or "fallback interno",
    }


def trova_ranking_per_giocatore(g, cache):
    nome = normalizza_nome(g.get("nome", ""))
    return trova_ranking_nome(nome, cache, tour_giocatore(nome))


def applica_ranking_a_match(match, cache, tour_atteso):
    if not isinstance(match, dict):
        return False

    avv = match.get("avv", "")
    ranking = trova_ranking_nome(avv, cache, tour_atteso)

    if ranking and ranking.get("pos"):
        precedente = match.get("ranking_avv") or {}
        match["ranking_avv"] = ranking
        return precedente.get("pos") != ranking.get("pos") or precedente.get("tour") != ranking.get("tour")

    # Non cancello una vecchia classifica se oggi non viene trovata.
    if not match.get("ranking_avv"):
        match["ranking_avv"] = None
    return False


def applica_classifiche(DATA, cache):
    aggiornati = []
    for g in DATA:
        nome = g.get("nome", "")
        tour_atteso = tour_giocatore(nome)
        g["tour"] = tour_atteso

        ranking = trova_ranking_per_giocatore(g, cache)
        if ranking and ranking.get("pos"):
            precedente = g.get("ranking") or {}
            g["ranking"] = ranking
            if precedente.get("pos") != ranking.get("pos") or precedente.get("tour") != ranking.get("tour"):
                aggiornati.append(nome)
        else:
            # Non cancello una vecchia classifica se il download del giorno non trova il giocatore:
            # meglio mostrare l'ultimo dato noto che perdere tutto per un problema temporaneo.
            if not g.get("ranking"):
                g["ranking"] = None

        if applica_ranking_a_match(g.get("prossimo"), cache, tour_atteso):
            aggiornati.append(f"avversario di {nome}")

        if applica_ranking_a_match(g.get("live"), cache, tour_atteso):
            aggiornati.append(f"avversario live di {nome}")

        for m in (g.get("storico") or []):
            if applica_ranking_a_match(m, cache, tour_atteso):
                aggiornati.append(f"avversario storico di {nome}")

    unici = []
    for n in aggiornati:
        if n and n not in unici:
            unici.append(n)
    return unici


def aggiorna_classifiche_giornaliere(DATA, meta):
    cache = leggi_ranking_cache()
    scaricata_oggi = False

    # Scarico una volta al giorno. Prima delle 06:00 uso la cache, se esiste.
    if devo_aggiornare_ranking(cache):
        if not cache or datetime.now().hour >= ORA_AGGIORNAMENTO_RANKING:
            nuova_cache = scarica_classifiche()
            if nuova_cache.get("players"):
                cache = nuova_cache
                salva_ranking_cache(cache)
                scaricata_oggi = True
            elif not cache:
                cache = nuova_cache

    aggiornati = applica_classifiche(DATA, cache) if cache else []

    if cache.get("aggiornato"):
        meta["ranking_aggiornato"] = cache.get("aggiornato")
        meta["ranking_fonte"] = cache.get("fonte", "")

    return DATA, aggiornati, scaricata_oggi

# -----------------------------------------------------------------------------
# Integrazione automatica dei prossimi avversari
# -----------------------------------------------------------------------------
URL_PROSSIMI = [
    "https://www.atptour.com/en/news/rome-2026-schedule",
    "https://sport.sky.it/tennis/sinner-internazionali-roma-2026-tabellone-avversari",
    "https://www.eurosport.it/tennis/atp-rome/2026/internazionali-ditalia-2026-diretta-live-sabato-9-maggio-2026-sinner-paolini-cobolli-pellegrino-e-fonseca-in-campo-oggi-al-foro-italico_sto23297906/story.shtml",
]

FALLBACK_PROSSIMI = {
    "SINNER": {"avv": "POPYRIN", "data": "11/05", "orario": "da definire"},
    "ARNALDI": {"avv": "JODAR", "data": "10/05", "orario": "20:30"},
    "COCCIARETTO": {"avv": "SWIATEK", "data": "10/05", "orario": "19:00"},
    "COBOLLI": {"avv": "TIRANTE", "data": "da definire", "orario": "da definire"},
    "BELLUCCI": {"avv": "LANDALUCE", "data": "da definire", "orario": "da definire"},
    "PELLEGRINO": {"avv": "TIAFOE", "data": "da definire", "orario": "da definire"},
    "DARDERI": {"avv": "PAUL", "data": "10/05", "orario": "16:00"},
    "MUSETTI": {"avv": "CERUNDOLO", "data": "10/05", "orario": "15:00"},
}


def pulisci_testo_html(html):
    testo = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    testo = re.sub(r"<style[\s\S]*?</style>", " ", testo, flags=re.I)
    testo = re.sub(r"<[^>]+>", " ", testo)
    testo = testo.replace("&nbsp;", " ").replace("&#39;", "'").replace("&amp;", "&")
    testo = re.sub(r"\s+", " ", testo)
    return testo


def scarica_url(url, timeout=4):
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 TennisTracker-Nino",
                "Accept-Language": "it-IT,it;q=0.9,en;q=0.7",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1", errors="ignore")
    except Exception:
        return ""


def cognome_da_lato(lato):
    lato = re.sub(r"\[[^\]]+\]", " ", lato)
    lato = re.sub(r"\([^)]*\)", " ", lato)
    lato = lato.replace("[WC]", " ").replace("[Q]", " ").replace("[LL]", " ")
    lato = re.sub(r"\bATP\b|\bWTA\b", " ", lato, flags=re.I)
    lato = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ' -]", " ", lato)
    parole = [x for x in lato.strip().split() if x]
    if not parole:
        return ""
    return parole[-1].upper()


def estrai_data_da_testo(testo, default="da definire"):
    if re.search(r"SUNDAY,\s*10\s*MAY\s*2026", testo, re.I) or "domenica 10 maggio" in testo.lower():
        return "10/05"
    if re.search(r"MONDAY,\s*11\s*MAY\s*2026", testo, re.I) or "lunedì" in testo.lower():
        return "11/05"
    return default


def estrai_orario_da_contesto(contesto):
    m = re.search(r"Not Before\s*(\d{1,2})(?::(\d{2}))?\s*(a\.m\.|p\.m\.)?", contesto, re.I)
    if not m:
        m = re.search(r"non prima delle\s*(\d{1,2})(?::(\d{2}))?", contesto, re.I)
    if not m:
        return "da definire"
    hh = int(m.group(1))
    mm = m.group(2) or "00"
    ampm = (m.group(3) or "").lower()
    if ampm.startswith("p") and hh < 12:
        hh += 12
    return f"{hh:02d}:{mm}"


def prossimo_valido(p):
    if not isinstance(p, dict):
        return False
    avv = str(p.get("avv", "")).strip().lower()
    return bool(avv and avv not in ("da definire", "tbd", "n/d", "nd", "none", "null"))


def aggiorna_prossimo_giocatore(g, avv, data="da definire", orario="da definire"):
    avv = (avv or "").strip().upper()
    if not avv or avv == str(g.get("nome", "")).strip().upper():
        return False
    if prossimo_valido(g.get("prossimo")):
        return False
    g["prossimo"] = {"orario": orario or "da definire", "data": data or "da definire", "avv": avv}
    if g.get("stato") not in ("live", "elim"):
        g["stato"] = "ok"
    return True


def integra_da_order_of_play(DATA, html):
    testo = pulisci_testo_html(html)
    data_default = estrai_data_da_testo(testo)
    nomi = {str(g.get("nome", "")).upper(): g for g in DATA}
    modificati = []
    pattern = re.compile(r"((?:Not Before[^A-Z]{0,40})?(?:ATP|WTA)\s*-\s*[^.]{0,180}?\s+vs\s+[^.]{0,180}?)(?=\s+(?:ATP|WTA|Not Before|Court|Campo|BNP|Supertennis|Pietrangeli|$))", re.I)
    for m in pattern.finditer(testo):
        riga = m.group(1).strip()
        if "(ITA)" not in riga or " vs " not in riga:
            continue
        parti = re.split(r"\s+vs\s+", riga, maxsplit=1, flags=re.I)
        if len(parti) != 2:
            continue
        sin, des = parti[0], parti[1]
        lato_ita = sin if "(ITA)" in sin else des
        lato_avv = des if "(ITA)" in sin else sin
        italiano = cognome_da_lato(lato_ita)
        avv = cognome_da_lato(lato_avv)
        if italiano not in nomi or not avv:
            continue
        contesto = testo[max(0, m.start() - 80):m.start() + 40]
        orario = estrai_orario_da_contesto(contesto)
        if aggiorna_prossimo_giocatore(nomi[italiano], avv, data_default, orario):
            modificati.append(italiano)
    return modificati


def integra_da_notizie(DATA, html):
    testo = pulisci_testo_html(html)
    nomi = {str(g.get("nome", "")).upper(): g for g in DATA}
    modificati = []
    regole = [
        ("SINNER", r"Sinner[^.]{0,120}?contro\s+l['’]australiano\s+Alexei\s+Popyrin", "POPYRIN", "11/05"),
        ("SINNER", r"SINNER\s*-\s*POPYRIN", "POPYRIN", "11/05"),
        ("COBOLLI", r"Cobolli[^.]{0,160}?trova\s+Thiago\s+Agustin\s+Tirante", "TIRANTE", "da definire"),
        ("BELLUCCI", r"Bellucci[^.]{0,180}?Martin\s+Landaluce", "LANDALUCE", "da definire"),
        ("PELLEGRINO", r"Tiafoe[^.]{0,120}?Pellegrino|Pellegrino[^.]{0,120}?Tiafoe", "TIAFOE", "da definire"),
        ("ARNALDI", r"Arnaldi[^.]{0,120}?Rafael\s+Jodar|J[oó]dar[^.]{0,120}?Arnaldi", "JODAR", "10/05"),
    ]
    for nome, rx, avv, data in regole:
        if nome in nomi and re.search(rx, testo, re.I):
            if aggiorna_prossimo_giocatore(nomi[nome], avv, data, "da definire"):
                modificati.append(nome)
    return modificati


def integra_prossimi_mancanti(DATA):
    modificati = []
    for url in URL_PROSSIMI:
        html = scarica_url(url)
        if not html:
            continue
        modificati.extend(integra_da_order_of_play(DATA, html))
        modificati.extend(integra_da_notizie(DATA, html))
    nomi = {str(g.get("nome", "")).upper(): g for g in DATA}
    for nome, p in FALLBACK_PROSSIMI.items():
        if nome in nomi and nomi[nome].get("stato") != "elim":
            if aggiorna_prossimo_giocatore(nomi[nome], p["avv"], p["data"], p["orario"]):
                modificati.append(nome)
    unici = []
    for n in modificati:
        if n not in unici:
            unici.append(n)
    return DATA, unici



# -----------------------------------------------------------------------------
# Pulizia storico: evita di mostrare come partita passata un incontro non ancora giocato
# -----------------------------------------------------------------------------
def score_da_verificare(score):
    testo = normalizza_nome(score)
    return testo in ("", "DA VERIFICARE", "DA DEFINIRE", "TBD", "ND", "N D")


def avversario_match(match):
    if not isinstance(match, dict):
        return ""
    return normalizza_nome(match.get("avv", ""))


def pulisci_storico_non_giocato(DATA):
    """
    Se un avversario è già presente come prossimo incontro, non deve comparire
    anche nello storico con punteggio 'da verificare'.
    Esempio: ARNALDI vs JODAR prossimo incontro + riga storica JODAR da verificare.
    """
    rimossi = []
    for g in DATA:
        storico = g.get("storico") or []
        if not isinstance(storico, list):
            continue

        avv_correnti = set()
        for campo in ("prossimo", "live"):
            avv = avversario_match(g.get(campo))
            if avv:
                avv_correnti.add(avv)

        nuovo_storico = []
        for m in storico:
            avv = avversario_match(m)
            score = m.get("score", "") if isinstance(m, dict) else ""
            if avv and avv in avv_correnti and score_da_verificare(score):
                rimossi.append(f"{g.get('nome','')} - {m.get('avv','')}")
                continue
            nuovo_storico.append(m)

        g["storico"] = nuovo_storico

    unici = []
    for x in rimossi:
        if x not in unici:
            unici.append(x)
    return DATA, unici



def nomi_ranking_utili(DATA):
    nomi = []

    def aggiungi(nome, tour):
        nome_norm = normalizza_nome(nome)
        if nome_norm and (nome_norm, tour) not in nomi:
            nomi.append((nome_norm, tour))

    for g in DATA:
        tour = tour_giocatore(g.get("nome", ""))
        aggiungi(g.get("nome", ""), tour)

        for campo in ("prossimo", "live"):
            m = g.get(campo)
            if isinstance(m, dict):
                aggiungi(m.get("avv", ""), tour)

        for m in (g.get("storico") or []):
            if isinstance(m, dict):
                aggiungi(m.get("avv", ""), tour)

    return nomi


def crea_ranking_frontend(DATA):
    """
    Crea una piccola mappa solo con i ranking utili alla pagina.
    Serve come rete di sicurezza: se per un avversario manca ranking_avv
    dentro dati.json, la pagina può comunque recuperarlo dalla mappa.
    """
    cache = leggi_ranking_cache()
    if not cache or not isinstance(cache.get("players"), dict):
        return {}

    ranking = {}
    for nome_norm, tour in nomi_ranking_utili(DATA):
        item = trova_ranking_nome(nome_norm, cache, tour)
        if item and item.get("pos"):
            ranking[f"{tour}|{nome_norm}"] = item
    return ranking

def genera_html(DATA, meta, ora_pubblicazione):
    icon_tag = (
        f'<link rel="apple-touch-icon" href="data:image/png;base64,{ICON_B64}">'
        if ICON_B64 else ""
    )
    favicon_tag = (
        f'<link rel="icon" href="data:image/png;base64,{ICON_B64}">'
        if ICON_B64
        else '<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 64 64\'%3E%3Ctext y=\'50\' font-size=\'48\'%3E🎾%3C/text%3E%3C/svg%3E">'
    )

    meta_agg = meta.get("aggiornato", "non disponibile")
    meta_fonte = meta.get("fonte", "")
    data_embedded = json.dumps(DATA, ensure_ascii=False)
    ranking_embedded = json.dumps(crea_ranking_frontend(DATA), ensure_ascii=False)

    return fr"""<!-- Tennis.html generato da Tennis.py - VERSIONE: {VERSIONE_SCRIPT} - generato: {ora_pubblicazione} -->
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Tennis Roma">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
{icon_tag}
{favicon_tag}
<title>🎾 Tennis Roma</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Barlow+Condensed:wght@400;600;700;800&display=swap');

  :root {{
    --clay:#C1440E;
    --clay2:#E8622A;
    --bg:#F5F0EB;
    --card:#FFFFFF;
    --line:#E0D8D0;
    --text:#1A1410;
    --muted:#8A7F74;
    --win:#1A7A40;
    --lose:#C0392B;
    --next:#B8860B;
    --live:#D60000;
  }}

  * {{ box-sizing:border-box; margin:0; padding:0; }}

  body {{
    background:var(--bg);
    color:var(--text);
    font-family:'Barlow Condensed',sans-serif;
    min-height:100vh;
    padding-bottom:50px;
    font-size:18px;
  }}

  .header {{
    background:linear-gradient(135deg,var(--clay) 0%,var(--clay2) 60%,#F07840 100%);
    padding:24px 18px 18px;
    position:relative;
    overflow:hidden;
    color:#fff;
  }}

  .header::after {{
    content:'🎾';
    position:absolute;
    font-size:90px;
    right:8px;
    top:-10px;
    opacity:0.18;
    transform:rotate(20deg);
  }}

  .header h1 {{
    font-size:34px;
    font-weight:800;
    letter-spacing:.02em;
    text-transform:uppercase;
    line-height:1;
    text-shadow:0 2px 8px rgba(0,0,0,.25);
  }}

  .header .subtitle {{
    font-size:16px;
    opacity:.9;
    margin-top:5px;
    font-family:'DM Mono',monospace;
  }}

  .header .finale {{
    display:inline-block;
    margin-top:10px;
    background:rgba(0,0,0,.25);
    border-radius:4px;
    padding:4px 12px;
    font-size:14px;
    font-family:'DM Mono',monospace;
  }}

  .agg {{
    background:#FFF8F3;
    border-bottom:1px solid var(--line);
    padding:10px 18px;
    font-size:13px;
    font-family:'DM Mono',monospace;
    color:var(--muted);
    line-height:1.45;
  }}

  .agg-top {{
    display:flex;
    align-items:center;
    gap:8px;
  }}

  .dot {{
    width:8px;
    height:8px;
    border-radius:50%;
    background:var(--win);
    flex-shrink:0;
  }}

  .dot.live-dot {{
    background:var(--live);
    animation:blinkLive .8s infinite;
  }}

  @keyframes blinkLive {{
    0%, 100% {{ opacity:1; transform:scale(1); }}
    50% {{ opacity:.20; transform:scale(.75); }}
  }}

  .section-label {{
    padding:16px 16px 7px;
    font-size:13px;
    font-weight:700;
    letter-spacing:.1em;
    text-transform:uppercase;
    color:var(--clay);
    font-family:'DM Mono',monospace;
  }}

  .card {{
    margin:0 10px 10px;
    background:var(--card);
    border-radius:12px;
    border:1px solid var(--line);
    overflow:hidden;
    box-shadow:0 2px 8px rgba(0,0,0,.07);
  }}

  .card.live {{
    border-color:var(--live);
    box-shadow:0 0 0 2px var(--live),0 4px 20px rgba(214,0,0,.22);
  }}

  .card.eliminato {{ opacity:.55; }}

  .card-head {{
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:16px 16px 13px;
    border-bottom:1px solid var(--line);
    gap:8px;
    background:#BFE3FF;
  }}

  .nome-wrap {{
    display:flex;
    align-items:baseline;
    gap:8px;
    flex-wrap:wrap;
    min-width:0;
  }}

  .nome {{
    font-size:32px;
    font-weight:800;
    letter-spacing:.03em;
    text-transform:uppercase;
    line-height:1;
    color:#1A1410;
  }}

  .ranking {{
    font-family:'DM Mono',monospace;
    font-size:13px;
    font-weight:600;
    color:#4F6475;
    background:rgba(255,255,255,.55);
    border:1px solid rgba(79,100,117,.18);
    border-radius:999px;
    padding:2px 7px;
    white-space:nowrap;
  }}

  .badge {{
    font-size:11px;
    font-weight:700;
    letter-spacing:.05em;
    padding:5px 10px;
    border-radius:20px;
    text-transform:uppercase;
    font-family:'DM Mono',monospace;
    white-space:nowrap;
  }}

  .badge.live {{
    background:var(--live);
    color:#fff;
    animation:blinkBadge .75s infinite;
    box-shadow:0 0 12px rgba(214,0,0,.45);
  }}

  @keyframes blinkBadge {{
    0%, 100% {{ opacity:1; }}
    50% {{ opacity:.25; }}
  }}

  .badge.next {{ background:#FFF8DC; color:#8B6914; border:1px solid #D4A800; }}
  .badge.elim {{ background:#FDECEA; color:#C0392B; border:1px solid #E57373; }}
  .badge.ok {{ background:#EBF7F0; color:#1A7A40; border:1px solid #4CAF78; }}

  .card-body {{ padding:14px 16px 16px; background:#FFFFFF; }}

  .live-score {{
    margin-bottom:10px;
    background:#FFF0F0;
    border-radius:8px;
    padding:14px 16px;
    border-left:5px solid var(--live);
  }}

  .live-score .vs {{ font-size:26px; font-weight:800; color:#1A1410; display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; }}
  .live-score .score {{ font-family:'DM Mono',monospace; font-size:30px; font-weight:500; color:var(--live); margin-top:5px; }}

  .prossimo {{
    margin-bottom:10px;
    background:#FFFBEE;
    border-radius:8px;
    padding:14px 16px;
    border-left:4px solid var(--next);
  }}

  .prossimo .vs {{ font-size:26px; font-weight:800; letter-spacing:.02em; color:#1A1410; display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; }}
  .prossimo .orario {{ font-family:'DM Mono',monospace; font-size:17px; color:#996600; margin-top:5px; font-weight:500; }}

  .avv-ranking {{
    font-family:'DM Mono',monospace;
    font-size:12px;
    font-weight:600;
    color:#806000;
    background:rgba(255,255,255,.70);
    border:1px solid rgba(128,96,0,.18);
    border-radius:999px;
    padding:2px 7px;
    white-space:nowrap;
  }}

  .match-row {{
    display:flex;
    align-items:center;
    gap:10px;
    padding:10px 0;
    border-bottom:1px solid rgba(0,0,0,.06);
  }}

  .match-row:last-child {{ border-bottom:none; }}
  .match-date {{ color:var(--muted); font-family:'DM Mono',monospace; font-size:15px; min-width:46px; }}
  .match-esito {{ font-size:18px; min-width:22px; }}
  .match-avv {{ flex:1; font-weight:700; font-size:20px; letter-spacing:.02em; display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; }}
  .match-score {{ color:var(--muted); font-family:'DM Mono',monospace; font-size:17px; font-weight:500; text-align:right; }}
</style>
</head>

<body>
<div class="versione-debug">VERSIONE NUOVA ATTIVA: {VERSIONE_SCRIPT}</div>
<div class="header">
  <h1>Internazionali d'Italia</h1>
  <div class="subtitle">Roma 2026 — Italiani</div>
  <div class="finale">Finale: {DATA_FINE}</div>
</div>

<div class="agg" id="barra-aggiornamento">
  <div class="agg-top">
    <div id="live-dot" class="dot"></div>
    <span id="pagina-refresh">Pagina: avvio...</span>
  </div>
  <div id="dati-refresh" style="margin-top:3px">Dati: avvio...</div>
  <div id="html-version" style="margin-top:2px;font-size:11px;opacity:.65">Versione: {VERSIONE_SCRIPT}</div>
</div>

<div id="container"></div>

<script>
const DATA_EMBEDDED = {data_embedded};
const HTML_VERSION = "{VERSIONE_SCRIPT}";
const RANKING_EMBEDDED = {ranking_embedded};
let RANKING_MAP = Object.assign({{}}, RANKING_EMBEDDED);
let timerRefresh = null;
let ultimaFirmaDati = "";
let primoCaricamento = true;

function firmaDati(DATA) {{
  try {{ return JSON.stringify(DATA); }}
  catch(e) {{ return String(Date.now()); }}
}}

function pad(n) {{ return String(n).padStart(2, "0"); }}

function oraLocale() {{
  const d = new Date();
  return pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds()) +
         " del " + pad(d.getDate()) + "/" + pad(d.getMonth()+1) + "/" + d.getFullYear();
}}

function sistemaBarraAggiornamento() {{
  // Difesa contro vecchie versioni/cache: deve esistere UNA SOLA barra.
  const barre = document.querySelectorAll(".agg");
  barre.forEach((b, i) => {{ if(i > 0) b.remove(); }});

  let barra = document.getElementById("barra-aggiornamento") || document.querySelector(".agg");
  if(!barra) return;

  barra.id = "barra-aggiornamento";
  barra.innerHTML =
    '<div class="agg-top">' +
    '<div id="live-dot" class="dot"></div>' +
    '<span id="pagina-refresh">Pagina: avvio...</span>' +
    '</div>' +
    '<div id="dati-refresh" style="margin-top:3px">Dati: avvio...</div>' +
    '<div id="html-version" style="margin-top:2px;font-size:11px;opacity:.65">Versione: {VERSIONE_SCRIPT}</div>';
}}

function dataKey(data) {{
  if(!data) return 99999999;
  const p = String(data).split("/");
  if(p.length === 2) {{
    const g = parseInt(p[0],10);
    const m = parseInt(p[1],10);
    const a = new Date().getFullYear();
    if(!isNaN(g) && !isNaN(m)) return a*10000 + m*100 + g;
  }}
  return 99999999;
}}

function orarioKey(orario) {{
  if(!orario) return 9999;
  const testo = String(orario).toLowerCase().replace(".", ":");
  const m = testo.match(/(\\d{{1,2}}):(\\d{{2}})/);
  if(m) return parseInt(m[1],10) * 60 + parseInt(m[2],10);
  return 9999;
}}

function dataLabel(data) {{
  if(!data) return "";
  const testo = String(data).trim();
  const m = testo.match(/^(\d{{1,2}})\/(\d{{1,2}})$/);
  if(!m) return testo;

  const oggi = new Date();
  const anno = oggi.getFullYear();
  const d = new Date(anno, parseInt(m[2],10) - 1, parseInt(m[1],10));
  const o = new Date(anno, oggi.getMonth(), oggi.getDate());
  const diff = Math.round((d - o) / 86400000);

  if(diff === 0) return "oggi";
  if(diff === 1) return "domani";
  return testo;
}}

function scoreLabel(score) {{
  const testo = String(score ?? "").trim();
  if(!testo) return "";
  if(testo.toLowerCase() === "da verificare") return "";
  return testo;
}}

function ordineGiocatore(g) {{
  const stato = g.stato || "";
  const p = g.prossimo || {{}};
  if(stato === "live") return [0, dataKey(p.data), -1, g.nome || ""];
  if(stato === "next" || stato === "ok") return [1, dataKey(p.data), orarioKey(p.orario), g.nome || ""];
  if(stato === "elim") return [9, 99999999, 9999, g.nome || ""];
  return [5, 99999999, 9999, g.nome || ""];
}}

function confronta(a,b) {{
  const ka = ordineGiocatore(a);
  const kb = ordineGiocatore(b);
  for(let i=0;i<ka.length;i++) {{
    if(ka[i] < kb[i]) return -1;
    if(ka[i] > kb[i]) return 1;
  }}
  return 0;
}}

function esc(s) {{
  return String(s ?? "")
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;");
}}

function rankingHtml(g) {{
  const r = g.ranking || null;
  const tour = (g.tour || (r && r.tour) || "").trim();
  if(r && r.pos) return '<span class="ranking">' + esc(r.tour || tour) + ' n.' + esc(r.pos) + '</span>';
  if(tour) return '<span class="ranking">' + esc(tour) + ' n.d.</span>';
  return "";
}}

function normalizzaNome(s) {{
  return String(s ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toUpperCase()
    .replace(/[^A-Z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}}

function aggiornaRankingMap(cache) {{
  if(!cache || !cache.players) return;
  Object.entries(cache.players).forEach(([nome, item]) => {{
    if(!item || !item.pos) return;
    const t = item.tour || "";
    const n = normalizzaNome(nome);
    if(t && n) RANKING_MAP[t + "|" + n] = item;
  }});
}}

function rankingDaMappa(nome, tour) {{
  const key = String(tour || "") + "|" + normalizzaNome(nome);
  return RANKING_MAP[key] || null;
}}

function rankingAvvHtml(m, tour) {{
  let r = (m && m.ranking_avv) ? m.ranking_avv : null;
  if((!r || !r.pos) && m && m.avv) r = rankingDaMappa(m.avv, tour);
  if(r && r.pos) return '<span class="avv-ranking">' + esc(r.tour || tour || "") + ' n.' + esc(r.pos) + '</span>';
  if(m && m.avv && tour) return '<span class="avv-ranking">' + esc(tour) + ' n.d.</span>';
  return "";
}}

function applicaCorrezioniClient(DATA) {{
  // Ultima rete di sicurezza: anche se dati.json contiene una cache vecchia,
  // il browser corregge i valori noti prima di disegnare la pagina.
  (DATA || []).forEach(g => {{
    const nome = normalizzaNome(g.nome);
    if(nome === "SINNER") {{
      g.tour = "ATP";
      g.ranking = {{ tour: "ATP", pos: 1, punti: "", fonte: "correzione client" }};
    }}
  }});
  return DATA;
}}

function renderCard(g) {{
  const stato = g.stato || "";
  const tour = g.tour || ((g.ranking && g.ranking.tour) ? g.ranking.tour : "");
  const isLive = stato === "live";
  const isElim = stato === "elim";

  let badge = "";
  if(isLive) {{
    badge = '<span class="badge live">LIVE</span>';
  }} else if(isElim) {{
    badge = '<span class="badge elim">ELIMINATO</span>';
  }} else if(g.prossimo) {{
    badge = '<span class="badge next">' + esc(dataLabel(g.prossimo.data)) + '</span>';
  }} else {{
    badge = '<span class="badge ok">IN GARA</span>';
  }}

  let body = "";

  if(isLive && g.live) {{
    body += '<div class="live-score">' +
            '<div class="vs">vs ' + esc(g.live.avv) + rankingAvvHtml(g.live, tour) + '</div>' +
            '<div class="score">' + esc(scoreLabel(g.live.score)) + '</div>' +
            '</div>';
  }}

  if(g.prossimo && !isElim && !isLive) {{
    body += '<div class="prossimo">' +
            '<div class="vs">vs ' + esc(g.prossimo.avv) + rankingAvvHtml(g.prossimo, tour) + '</div>' +
            '<div class="orario">' + esc(g.prossimo.orario) + ' · ' + esc(dataLabel(g.prossimo.data)) + '</div>' +
            '</div>';
  }}

  (g.storico || []).forEach(m => {{
    const sym = m.esito === "W" ? "✓" : "✗";
    const col = m.esito === "W" ? "var(--win)" : "var(--lose)";
    body += '<div class="match-row">' +
            '<span class="match-date">' + esc(dataLabel(m.data)) + '</span>' +
            '<span class="match-esito" style="color:' + col + '">' + sym + '</span>' +
            '<span class="match-avv">' + esc(m.avv) + rankingAvvHtml(m, tour) + '</span>' +
            '<span class="match-score">' + esc(scoreLabel(m.score)) + '</span>' +
            '</div>';
  }});

  if(!body) {{
    body = '<div style="font-size:14px;color:var(--muted);font-family:DM Mono,monospace;padding:4px 0">Nessun dettaglio disponibile</div>';
  }}

  return '<div class="card' + (isLive ? ' live' : '') + (isElim ? ' eliminato' : '') + '">' +
         '<div class="card-head"><div class="nome-wrap"><div class="nome">' + esc(g.nome) + '</div>' + rankingHtml(g) + '</div>' + badge + '</div>' +
         '<div class="card-body">' + body + '</div>' +
         '</div>';
}}

function render(DATA) {{
  const ordinati = [...DATA].sort(confronta);
  const inGara = ordinati.filter(g => g.stato !== "elim");
  const eliminati = ordinati.filter(g => g.stato === "elim");
  const isLive = DATA.some(g => g.stato === "live");

  document.getElementById("live-dot").className = isLive ? "dot live-dot" : "dot";

  let html = "";

  if(inGara.length) {{
    html += '<div class="section-label">Italiani ancora in gara</div>';
    inGara.forEach(g => html += renderCard(g));
  }}

  if(eliminati.length) {{
    html += '<div class="section-label">Italiani fuori dai giochi</div>';
    eliminati.forEach(g => html += renderCard(g));
  }}

  if(!html) {{
    html = '<div style="margin:20px 14px;padding:18px;border-radius:12px;background:#fff;border:1px solid var(--line);font-family:DM Mono,monospace;font-size:14px;color:var(--muted)">Nessun dato disponibile.</div>';
  }}

  document.getElementById("container").innerHTML = html;
}}

async function carica() {{
  if(timerRefresh) clearTimeout(timerRefresh);

  try {{
    const r = await fetch("dati.json?t=" + Date.now(), {{ cache: "no-store" }});
    const DATA = applicaCorrezioniClient(await r.json());

    try {{
      const rr = await fetch("ranking_cache.json?t=" + Date.now(), {{ cache: "no-store" }});
      if(rr.ok) aggiornaRankingMap(await rr.json());
    }} catch(e) {{}}

    sistemaBarraAggiornamento();
    render(DATA);

    // Forza il ridisegno della videata anche quando resta aperta ferma su monitor/tablet.
    // Non aggiorno soltanto l'orario: rileggo dati.json, ricostruisco le card e marco il DOM come aggiornato.
    const firma = firmaDati(DATA);
    if(!primoCaricamento && firma !== ultimaFirmaDati) {{
      window.scrollBy(0, 0);
    }}
    ultimaFirmaDati = firma;
    primoCaricamento = false;
    document.documentElement.setAttribute("data-refresh", String(Date.now()));

    const isLive = DATA.some(g => g.stato === "live");
    const intervallo = isLive ? 6000 : 60000;

    document.getElementById("pagina-refresh").textContent =
      "Pagina aggiornata: " + oraLocale();

    try {{
      const rm = await fetch("meta.json?t=" + Date.now(), {{ cache: "no-store" }});
      if(rm.ok) {{
        const meta = await rm.json();
        let txt = "Dati aggiornati: " + (meta.aggiornato || "non disponibile");
        if(meta.fonte) txt += " · " + meta.fonte;
        document.getElementById("dati-refresh").textContent = txt;
        if(meta.html_version && meta.html_version !== HTML_VERSION) {{
          const base = window.location.href.split("?")[0];
          window.location.replace(base + "?v=" + Date.now());
          return;
        }}
      }}
    }} catch(e) {{}}

    timerRefresh = setTimeout(carica, intervallo);

  }} catch(e) {{
    document.getElementById("pagina-refresh").textContent =
      "Errore refresh pagina: " + oraLocale() + " · ritento tra 10 sec";
    timerRefresh = setTimeout(carica, 10000);
  }}
}}

sistemaBarraAggiornamento();
carica();

(function() {{
  let startY = 0;
  let pulling = false;

  const ind = document.createElement("div");
  ind.style.cssText =
    "position:fixed;top:0;left:0;right:0;height:48px;display:flex;align-items:center;justify-content:center;" +
    "font-family:DM Mono,monospace;font-size:13px;font-weight:600;color:#C1440E;background:#FFF8F3;" +
    "border-bottom:1px solid #E0D8D0;transform:translateY(-100%);transition:transform .2s ease;z-index:9999";

  document.body.prepend(ind);

  document.addEventListener("touchstart", e => {{
    if(window.scrollY === 0) {{
      startY = e.touches[0].clientY;
      pulling = true;
    }}
  }}, {{ passive:true }});

  document.addEventListener("touchmove", e => {{
    if(!pulling) return;
    const dy = e.touches[0].clientY - startY;
    if(dy > 10) {{
      ind.style.transform = "translateY(" + Math.min(dy - 10, 60) + "px)";
      ind.innerHTML = dy > 70 ? "↑ Rilascia per aggiornare" : "↓ Trascina per aggiornare";
    }}
  }}, {{ passive:true }});

  document.addEventListener("touchend", e => {{
    if(!pulling) return;
    pulling = false;

    const dy = e.changedTouches[0].clientY - startY;
    ind.style.transform = "translateY(-100%)";

    if(dy > 70) carica();
  }}, {{ passive:true }});
}})();
</script>
</body>
</html>"""


def data_label_txt(data_testo):
    testo = str(data_testo or "").strip()
    m = re.match(r"^(\d{1,2})/(\d{1,2})$", testo)
    if not m:
        return testo
    oggi = datetime.now().date()
    try:
        d = datetime(oggi.year, int(m.group(2)), int(m.group(1))).date()
    except Exception:
        return testo
    diff = (d - oggi).days
    if diff == 0:
        return "oggi"
    if diff == 1:
        return "domani"
    return testo


def score_label_txt(score):
    testo = str(score or "").strip()
    if testo.lower() == "da verificare":
        return ""
    return testo


def nome_con_ranking_txt(g):
    nome = g.get("nome", "")
    r = g.get("ranking") or {}
    if r.get("pos"):
        return f"{nome} ({r.get('tour', '')} n.{r.get('pos')})"
    return nome


def avversario_con_ranking_txt(match):
    if not isinstance(match, dict):
        return ""
    avv = match.get("avv", "")
    r = match.get("ranking_avv") or {}
    if r.get("pos"):
        return f"{avv} ({r.get('tour', '')} n.{r.get('pos')})"
    return avv


def genera_txt(DATA, meta, ora_pubblicazione):
    ordinati = dati_ordinati(DATA)
    in_gara = [g for g in ordinati if g.get("stato") != "elim"]
    eliminati = [g for g in ordinati if g.get("stato") == "elim"]

    righe = [
        "-" * 50,
        "Internazionali d'Italia - Roma",
        "Italiani",
        f"Finale: {DATA_FINE}",
        f"Dati aggiornati: {meta.get('aggiornato', 'non disponibile')}",
        f"Fonte dati: {meta.get('fonte', 'non disponibile')}",
        "-" * 50,
        "",
        "ITALIANI ANCORA IN GARA",
        "-" * 50,
    ]

    if not in_gara:
        righe.append("Nessuno.")

    for g in in_gara:
        nome = nome_con_ranking_txt(g)

        if g.get("stato") == "live" and g.get("live"):
            live = g["live"]
            righe.append(f"{nome} - {avversario_con_ranking_txt(live)}")
            righe.append(f">>> LIVE  {score_label_txt(live.get('score', ''))}")

        elif g.get("prossimo"):
            p = g["prossimo"]
            righe.append(f"{nome} - {avversario_con_ranking_txt(p)}")
            righe.append(f"{p.get('orario', '')} - {data_label_txt(p.get('data', ''))}")

        else:
            righe.append(f"{nome} - ancora in gara, prossimo incontro da definire")

        for m in (g.get("storico") or []):
            esito = "V" if m.get("esito") == "W" else "X"
            righe.append(f"  {data_label_txt(m.get('data', ''))}  {esito}  {avversario_con_ranking_txt(m)}  {score_label_txt(m.get('score', ''))}")

        righe.append("-" * 50)

    righe += ["", "ITALIANI FUORI DAI GIOCHI", "-" * 50]

    if not eliminati:
        righe.append("Nessuno.")

    for g in eliminati:
        righe.append(nome_con_ranking_txt(g))

        for m in (g.get("storico") or []):
            esito = "V" if m.get("esito") == "W" else "X"
            righe.append(f"  {data_label_txt(m.get('data', ''))}  {esito}  {avversario_con_ranking_txt(m)}  {score_label_txt(m.get('score', ''))}")

        righe.append("-" * 50)

    return "\n".join(righe)


def github_upload(filepath, repo_path, ora_pubblicazione):
    token = leggi_token()

    if not token:
        sys.stdout.write(" ERRORE: manca token.txt")
        sys.stdout.flush()
        return False

    if not os.path.exists(filepath):
        sys.stdout.write(" SALTATO: file mancante")
        sys.stdout.flush()
        return True

    api_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{repo_path}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "TennisTracker-Nino",
    }

    with open(filepath, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("ascii")

    sha = None
    try:
        req = urllib.request.Request(api_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            sha = json.loads(resp.read().decode("utf-8")).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            sys.stdout.write(f" ERRORE GET {e.code}")
            sys.stdout.flush()
            return False
    except Exception as e:
        sys.stdout.write(f" ERRORE GET {e}")
        sys.stdout.flush()
        return False

    body = {
        "message": f"Tennis: aggiorna {ora_pubblicazione}",
        "content": content_b64,
        "branch": GITHUB_BRANCH,
    }
    if sha:
        body["sha"] = sha

    data = json.dumps(body).encode("utf-8")

    try:
        req2 = urllib.request.Request(api_url, data=data, headers=headers, method="PUT")
        with urllib.request.urlopen(req2, timeout=30) as resp:
            json.loads(resp.read().decode("utf-8"))
        return True
    except urllib.error.HTTPError as e:
        dettaglio = ""
        try:
            dettaglio = e.read().decode("utf-8")[:300]
        except Exception:
            pass
        sys.stdout.write(f" ERRORE PUT {e.code} {dettaglio}")
        sys.stdout.flush()
        return False
    except Exception as e:
        sys.stdout.write(f" ERRORE PUT {e}")
        sys.stdout.flush()
        return False


def git_push(ora_pubblicazione):
    files = [
        (F_HTML, "Tennis/Tennis.html", "Tennis.html"),
        (F_TXT, "Tennis/Tennis.txt", "Tennis.txt"),
        (F_JSON, "Tennis/dati.json", "dati.json"),
        (F_META, "Tennis/meta.json", "meta.json"),
        (F_RANKING_CACHE, "Tennis/ranking_cache.json", "ranking_cache.json"),
    ]

    for filepath, repo_path, label in files:
        sys.stdout.write(f"  {label} ")
        sys.stdout.flush()

        stop = threading.Event()

        def puntini():
            while not stop.is_set():
                sys.stdout.write(".")
                sys.stdout.flush()
                time.sleep(1)

        t = threading.Thread(target=puntini, daemon=True)
        t.start()

        ok = github_upload(filepath, repo_path, ora_pubblicazione)

        stop.set()
        t.join()

        sys.stdout.write(" OK\n" if ok else " ERRORE\n")
        sys.stdout.flush()


def avvia_controllo_uscita(stop_event):
    if not sys.stdin or not sys.stdin.isatty():
        return

    def aspetta_invio():
        try:
            input()
            stop_event.set()
        except Exception:
            pass

    threading.Thread(target=aspetta_invio, daemon=True).start()



def forza_correzioni_ranking_data(DATA):
    """Applica correzioni manuali direttamente ai dati da pubblicare.
    Serve anche quando dati.json contiene una classifica vecchia: il file pubblicato
    e la pagina devono comunque mostrare la correzione.
    """
    cambiati = []
    for g in DATA:
        nome_norm = normalizza_nome(g.get("nome", ""))
        tour = tour_giocatore(nome_norm)
        g["tour"] = tour
        pos = RANKING_CORREZIONI.get((tour, nome_norm))
        if pos:
            precedente = g.get("ranking") or {}
            if precedente.get("pos") != pos or precedente.get("tour") != tour:
                g["ranking"] = {
                    "tour": tour,
                    "pos": pos,
                    "punti": "",
                    "fonte": "correzione manuale forzata",
                }
                cambiati.append(g.get("nome", nome_norm))
    return cambiati

def aggiorna():
    DATA = carica_dati()
    meta = carica_meta()

    DATA, integrati = integra_prossimi_mancanti(DATA)
    DATA, storico_rimosso = pulisci_storico_non_giocato(DATA)

    DATA, ranking_aggiornati, ranking_scaricata = aggiorna_classifiche_giornaliere(DATA, meta)
    ranking_corretti_forzati = forza_correzioni_ranking_data(DATA)
    for _nome in ranking_corretti_forzati:
        if _nome not in ranking_aggiornati:
            ranking_aggiornati.append(_nome)
    meta["html_version"] = VERSIONE_SCRIPT
    if integrati:
        meta["fonte"] = (meta.get("fonte", "") + " + integrazione prossimi").strip(" +")
        meta["italiani_integrati"] = integrati
    if ranking_aggiornati:
        meta["ranking_giocatori_aggiornati"] = ranking_aggiornati
    if ranking_scaricata:
        meta["ranking_scaricata_oggi"] = True
    if storico_rimosso:
        meta["storico_non_giocato_rimosso"] = storico_rimosso
    if integrati or ranking_aggiornati or ranking_scaricata or storico_rimosso:
        try:
            with open(F_JSON, "w", encoding="utf-8", newline="\n") as f:
                json.dump(DATA, f, ensure_ascii=False, indent=2)
            with open(F_META, "w", encoding="utf-8", newline="\n") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"ATTENZIONE: impossibile salvare integrazioni: {e}")

    ora_console = datetime.now().strftime("%H:%M:%S")
    ora_pubblicazione = ora_adesso()

    sys.stdout.write(f"\n[{ora_console}] Pubblicazione ({len(DATA)} giocatori)\n")
    if integrati:
        sys.stdout.write("  Prossimi avversari integrati: " + ", ".join(integrati) + "\n")
    if storico_rimosso:
        sys.stdout.write("  Rimosse dallo storico le partite non ancora giocate: " + ", ".join(storico_rimosso) + "\n")
    if ranking_aggiornati:
        sys.stdout.write("  Classifiche aggiornate: " + ", ".join(ranking_aggiornati) + "\n")
    elif ranking_scaricata:
        sys.stdout.write("  Classifiche scaricate, nessuna variazione sui giocatori già presenti.\n")
    sys.stdout.flush()

    try:
        with open(F_HTML, "w", encoding="utf-8", newline="\n") as f:
            f.write(genera_html(DATA, meta, ora_pubblicazione))

        with open(F_TXT, "w", encoding="utf-8", newline="\n") as f:
            f.write(genera_txt(DATA, meta, ora_pubblicazione) + "\n")

    except Exception as e:
        print(f"ERRORE generazione file: {e}")
        return DATA

    try:
        html_test = open(F_HTML, "r", encoding="utf-8").read()
        ok_html = (VERSIONE_SCRIPT in html_test and "avv-ranking" in html_test and "function dataLabel" in html_test and "VERSIONE NUOVA ATTIVA" in html_test)
        if ok_html:
            sys.stdout.write(f"  HTML generato con versione: {VERSIONE_SCRIPT} - OK locale\n")
        else:
            sys.stdout.write(f"  ATTENZIONE: HTML locale non contiene le ultime modifiche ({VERSIONE_SCRIPT})\n")
        sys.stdout.write(f"  File locale HTML: {F_HTML}\n")
    except Exception as e:
        sys.stdout.write(f"  ATTENZIONE: controllo HTML locale non riuscito: {e}\n")
    sys.stdout.flush()

    git_push(ora_pubblicazione)
    return DATA

def main():
    stop_event = threading.Event()
    avvia_controllo_uscita(stop_event)

    sys.stdout.write(f"Tennis.py versione {VERSIONE_SCRIPT}\n")
    sys.stdout.write("Premi INVIO per uscire regolarmente.\n")
    sys.stdout.flush()

    DATA = aggiorna()

    while not stop_event.is_set():
        live = c_live(DATA)
        intervallo = INTERVALLO_LIVE if live else INTERVALLO_NORMAL

        puntino_ogni = PUNTINO_LIVE if live else PUNTINO_NORMAL

        if live:
            sys.stdout.write("\n  [LIVE] prossimo controllo tra 6 sec")
        else:
            sys.stdout.write("\n  prossimo controllo tra 60 sec")
        sys.stdout.flush()

        secondi_passati = 0
        while secondi_passati < intervallo:
            if stop_event.is_set():
                break

            sleep_time = min(puntino_ogni, intervallo - secondi_passati)
            time.sleep(sleep_time)
            secondi_passati += sleep_time

            sys.stdout.write(".")
            sys.stdout.flush()

        if stop_event.is_set():
            break

        DATA = aggiorna()

    sys.stdout.write("\nUscita richiesta: ciclo interrotto regolarmente.\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
