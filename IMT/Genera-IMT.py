# Nome.py: GeneraMenu.py
# Ultimo aggiornamento: 27/11/2026 (contatore utenti, condivisione, salvataggio sulla Home)
# Descrizione: Legge menu-giornaliero-completo-autunno-2026.xlsx e genera Menu-IMT.html.
#              Generazione del file menu_siri.json con date multi-formato per evitare
#              qualsiasi formattazione lato iOS Shortcuts.
#              Contatore utenti: ogni dispositivo riceve un codice univoco nascosto;
#              ogni 5 secondi la pagina mostra "<n> utenti collegati adesso su <t>"
#              usando il database Firebase indicato in CONTATORE_URL.
#              Un clic su quella riga mostra la tabella dei dispositivi registrati
#              (prima i collegati in rosso, poi gli altri in blu; ognuno dal più recente).
#              Toccando la propria riga si può scrivere il nome del dispositivo.
#              A destra, per i soli collegati, la lingua in uso (IT / EN), comunicata
#              da ogni dispositivo ogni 5 secondi. Ai lati della riga del contatore
#              due bandierine (IT a sinistra, EN a destra) per scegliere la lingua.
#              All'avvio la pagina si apre nella lingua usata l'ultima volta.
#              Pulsante Condividi (in basso a destra): condivide/copia il link e
#              spiega come salvare la pagina sulla Home (PC, Mac, iPhone, Android).
#              Genera anche manifest.webmanifest, sw.js e le icone (IMT-anteprima.jpg,
#              IMT-180.png, IMT-192.png, IMT-512.png) a partire da IMT.jpg.
# File di input: menu-giornaliero-completo-autunno-2026.xlsx
# File di output: Menu-IMT.html, menu_siri.json, manifest.webmanifest, sw.js, icone IMT-*
# Parametri: --input FILE.xlsx, --traduci (traduzione online facoltativa)

import pandas as pd
import json
from datetime import datetime
import urllib.request
import urllib.parse
import os
import time
import argparse
import html
import re
from pathlib import Path

# Indirizzo del Firebase Realtime Database usato dal contatore utenti
# (es. https://imt-menu-xxxxx-default-rtdb.europe-west1.firebasedatabase.app).
# Se resta vuoto, la riga del contatore non viene mostrata.
CONTATORE_URL = "https://imt-menu-default-rtdb.europe-west1.firebasedatabase.app"

PAGINA_URL = "https://sebastiano-mazzarisi.github.io/Prog/IMT/Menu-IMT.html"
CARTELLA_URL = PAGINA_URL.rsplit('/', 1)[0] + '/'

# Icone ricavate da IMT.jpg: nome file -> (lato in pixel, frazione occupata dal logo).
# L'anteprima ha ampi margini bianchi per non essere tagliata da WhatsApp e dai social.
ICONE = {
    'IMT-anteprima.jpg': (800, 0.62),
    'IMT-180.png': (180, 0.86),
    'IMT-192.png': (192, 0.80),
    'IMT-512.png': (512, 0.80),
}

def prepara_icone(base):
    """Crea (o ricrea se IMT.jpg è più recente) le icone quadrate con margini bianchi."""
    sorgente = base / 'IMT.jpg'
    if not sorgente.exists():
        print('Attenzione: IMT.jpg non trovato, icone non generate.')
        return
    da_fare = [n for n in ICONE if not (base / n).exists()
               or (base / n).stat().st_mtime < sorgente.stat().st_mtime]
    if not da_fare:
        return
    try:
        from PIL import Image, ImageChops
    except ImportError:
        print('Attenzione: Pillow non installato (pip install pillow), icone non generate: ' + ', '.join(da_fare))
        return
    im = Image.open(sorgente).convert('RGB')
    bianco = Image.new('RGB', im.size, (255, 255, 255))
    maschera = ImageChops.difference(im, bianco).convert('L').point(lambda p: 255 if p > 12 else 0)
    logo = im.crop(maschera.getbbox() or (0, 0, im.width, im.height))
    for nome in da_fare:
        lato, frazione = ICONE[nome]
        tela = Image.new('RGB', (lato, lato), (255, 255, 255))
        k = lato * frazione / max(logo.size)
        ridotto = logo.resize((round(logo.width * k), round(logo.height * k)), Image.LANCZOS)
        tela.paste(ridotto, ((lato - ridotto.width) // 2, (lato - ridotto.height) // 2))
        if nome.endswith('.jpg'):
            tela.save(base / nome, 'JPEG', quality=92)
        else:
            # 256 colori: aspetto invariato, file grandi la metà
            tela.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG).save(base / nome, 'PNG', optimize=True)
    print('Icone generate: ' + ', '.join(da_fare))

def scrivi_file_app(base, versione):
    """Scrive manifest.webmanifest e sw.js per poter installare la pagina come app."""
    manifest = {
        "name": "IMT - Menu",
        "short_name": "IMT Menu",
        "description": "Menu giornaliero Pranzo e Cena",
        "lang": "it",
        "start_url": "Menu-IMT.html",
        "scope": "./",
        "display": "standalone",
        "background_color": "#f2f2f7",
        "theme_color": "#007aff",
        "icons": [
            {"src": "IMT-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "IMT-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}
        ]
    }
    with open(base / 'manifest.webmanifest', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write('\n')
    sw = """// sw.js - generato da Genera-IMT.py: permette l'installazione come app.
// Strategia "prima la rete": la pagina è sempre aggiornata; la copia salvata
// serve solo quando manca la connessione.
const CACHE = 'imt-menu-__VERSIONE__';
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(
    caches.keys().then(k => Promise.all(k.filter(n => n !== CACHE).map(n => caches.delete(n))))
        .then(() => self.clients.claim())));
self.addEventListener('fetch', e => {
    const r = e.request;
    if (r.method !== 'GET' || new URL(r.url).origin !== self.location.origin) return;
    const chiave = r.url.split('?')[0].split('#')[0];
    e.respondWith(fetch(r).then(risposta => {
        if (risposta.ok) { const copia = risposta.clone(); caches.open(CACHE).then(c => c.put(chiave, copia)); }
        return risposta;
    }).catch(() => caches.match(chiave)));
});
""".replace('__VERSIONE__', versione)
    with open(base / 'sw.js', 'w', encoding='utf-8', newline='\n') as f:
        f.write(sw)

def genera_html(file_input=None, traduci=False):
    base = Path(__file__).resolve().parent
    file_input = Path(file_input) if file_input else base / 'menu-giornaliero-completo-autunno-2026.xlsx'
    file_output = base / 'Menu-IMT.html'
    dizionario_file = base / 'dizionario_menu.json'
    file_siri = base / 'menu_siri.json'
    
    try:
        df = pd.read_excel(file_input)
    except FileNotFoundError:
        raise FileNotFoundError(f"Il file {file_input} non è stato trovato.") from None
        
    df = df.fillna('')
    required = ['Data', 'Pranzo Cena', 'Primi', 'Secondi', 'Contorni', 'Frutta e Dessert']
    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError('Colonne obbligatorie mancanti: ' + ', '.join(sorted(missing)))
    if df.empty:
        raise ValueError('Il foglio Excel non contiene menu')
    df['Data'] = pd.to_datetime(df['Data'], errors='coerce').dt.normalize()
    if df['Data'].isna().any():
        raise ValueError('Una o più date sono mancanti o non valide')
    df['Pranzo Cena'] = df['Pranzo Cena'].astype(str).str.strip().str.capitalize()
    if not df['Pranzo Cena'].isin(['Pranzo', 'Cena']).all():
        raise ValueError('La colonna Pranzo Cena deve contenere solo Pranzo oppure Cena')
    if df.duplicated(['Data', 'Pranzo Cena']).any():
        raise ValueError('Menu duplicati per data e pasto')
    incomplete = df.groupby('Data')['Pranzo Cena'].nunique()
    if (incomplete != 2).any():
        dates = ', '.join(d.strftime('%d/%m/%Y') for d in incomplete[incomplete != 2].index)
        raise ValueError('Pranzo o cena mancante per: ' + dates)
    for col in ['Primi', 'Secondi', 'Contorni']:
        if df[col].astype(str).str.strip().eq('').any():
            raise ValueError(f'Una o più celle della colonna {col} sono vuote')
    
    unique_terms = set()
    for col in ['Primi', 'Secondi', 'Contorni', 'Frutta e Dessert']:
        for val in df[col]:
            if str(val).strip():
                lines = str(val).split('\n')
                for line in lines:
                    cleaned = line.strip().lstrip('•').strip()
                    if cleaned:
                        unique_terms.add(cleaned)
                        
    dizionario = {}
    if os.path.exists(dizionario_file):
        try:
            with open(dizionario_file, 'r', encoding='utf-8') as f:
                dizionario = json.load(f)
        except Exception:
            pass
            
    nuovi_termini = [t for t in unique_terms if t not in dizionario]
    
    if nuovi_termini and traduci:
        print(f"Trovati {len(nuovi_termini)} piatti da tradurre...")
        for i, term in enumerate(nuovi_termini):
            url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=it&tl=en&dt=t&q=" + urllib.parse.quote(term)
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                response = urllib.request.urlopen(req, timeout=15)
                data = json.loads(response.read().decode('utf-8'))
                tradotto = data[0][0][0]
                if term.isupper():
                    tradotto = tradotto.upper()
                dizionario[term] = tradotto
            except Exception as e:
                dizionario[term] = term 
            time.sleep(0.3) 
                
        with open(dizionario_file, 'w', encoding='utf-8') as f:
            json.dump(dizionario, f, indent=4, ensure_ascii=False)

    blocks = []
    
    giorni_it = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
    mesi_it = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
    
    giorni_en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    mesi_en = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    
    def get_items(text, lang='it'):
        if not text: 
            return []
        lines = str(text).split('\n')
        cleaned = []
        for line in lines:
            line = line.strip().lstrip('•').strip()
            if line:
                val = line if lang == 'it' else dizionario.get(line, line)
                val = re.sub(r'\(\s*[\d\s,;*/–-]+\)', '', val)
                val = re.sub(r'\(\s*\*+\s*\)', '', val).replace('*', '')
                val = html.escape(re.sub(r'\s+', ' ', val).strip())
                if line.isupper():
                    val = f"<strong>{val}</strong>"
                cleaned.append(val)
        return cleaned

    for index, row in df.iterrows():
        pasto_val = str(row.get('Pranzo Cena', '')).strip()
        if not pasto_val:
            continue
            
        data_val = row.get('Data', '')
        d = None
        if isinstance(data_val, pd.Timestamp) or isinstance(data_val, datetime):
            d = data_val
        else:
            try:
                d = pd.to_datetime(data_val)
            except Exception:
                d = None
                
        if pd.notnull(d):
            iso_date = d.strftime("%Y-%m-%d")
            giorno_nome_it = giorni_it[d.weekday()]
            mese_nome_it = mesi_it[d.month]
            formatted_date_it = f"{giorno_nome_it} {d.day} {mese_nome_it} {d.year}"
            giorno_nome_en = giorni_en[d.weekday()]
            mese_nome_en = mesi_en[d.month]
            formatted_date_en = f"{giorno_nome_en} {mese_nome_en} {d.day}, {d.year}"
        else:
            iso_date = str(data_val)
            formatted_date_it = str(data_val)
            formatted_date_en = str(data_val)

        meal_type_it = pasto_val.upper()
        meal_type_en = "LUNCH" if pasto_val.lower() == "pranzo" else "DINNER"
            
        block = {
            'type': pasto_val,
            'date': iso_date,
            'meal_type_it': meal_type_it,
            'meal_type_en': meal_type_en,
            'date_it': formatted_date_it,
            'date_en': formatted_date_en,
            'Primi_it': get_items(row.get('Primi', ''), 'it'),
            'Primi_en': get_items(row.get('Primi', ''), 'en'),
            'Secondi_it': get_items(row.get('Secondi', ''), 'it'),
            'Secondi_en': get_items(row.get('Secondi', ''), 'en'),
            'Contorno_it': get_items(row.get('Contorni', ''), 'it'),
            'Contorno_en': get_items(row.get('Contorni', ''), 'en'),
            'Frutta_it': get_items(row.get('Frutta e Dessert', ''), 'it'),
            'Frutta_en': get_items(row.get('Frutta e Dessert', ''), 'en')
        }
        blocks.append(block)

    def sort_key(b):
        return (b['date'], 0 if b['type'].lower() == 'pranzo' else 1)
    blocks.sort(key=sort_key)

    # === NUOVA CREAZIONE FILE JSON PER SIRI (MULTIFORMATO A PROVA DI ERRORE) ===
    siri_data = {}
    pasti_per_data = {}
    
    for block in blocks:
        d = block['date']
        if d not in pasti_per_data:
            pasti_per_data[d] = []
        pasti_per_data[d].append(block)
        
    for data_iso, pasti in pasti_per_data.items():
        try:
            d_obj = datetime.strptime(data_iso, "%Y-%m-%d")
            
            data_it_str = pasti[0]['date_it']
            testo_siri = f"Ciao! Ecco il menu della IMT di oggi, {data_it_str}. "
            
            for b in pasti:
                is_pranzo = b['type'].lower() == 'pranzo'
                testo_siri += "A pranzo abbiamo: " if is_pranzo else "Mentre a cena c'è: "
                
                def estrai_testo(lista_html):
                    piatti = [html.unescape(item.replace("<strong>", "").replace("</strong>", "")) for item in lista_html if "<strong>" in item]
                    if piatti:
                        return " e ".join(piatti) + ". "
                    return ""
                
                primi = estrai_testo(b['Primi_it'])
                secondi = estrai_testo(b['Secondi_it'])
                contorni = estrai_testo(b['Contorno_it'])
                
                testo_siri += primi + secondi + contorni
                
            testo_siri += "Buon appetito!"
            
            # Genera TUTTE le possibili stringhe di data che l'iPhone potrebbe inviare
            formati_possibili = [
                data_iso,
                d_obj.strftime("%d/%m/%Y"),
                d_obj.strftime("%d/%m/%y"),
                f"{d_obj.day}/{d_obj.month}/{d_obj.year}",
                f"{d_obj.day:02d}/{d_obj.month:02d}/{d_obj.year}",
                f"{d_obj.day} {mesi_it[d_obj.month][:3]} {d_obj.year}",
                f"{d_obj.day} {mesi_it[d_obj.month][:3]}. {d_obj.year}",
                f"{d_obj.day} {mesi_it[d_obj.month]} {d_obj.year}",
                f"{giorni_it[d_obj.weekday()]} {d_obj.day} {mesi_it[d_obj.month]} {d_obj.year}",
                f"{giorni_it[d_obj.weekday()].lower()} {d_obj.day} {mesi_it[d_obj.month]} {d_obj.year}"
            ]
            
            for fmt in set(formati_possibili):
                siri_data[fmt] = testo_siri
                
        except Exception as e:
            pass

    with open(file_siri, 'w', encoding='utf-8') as f:
        json.dump(siri_data, f, indent=4, ensure_ascii=False)
    # === FINE CREAZIONE JSON ===

    html_template = """<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Menu IMT - Autunno 2026</title>
    <link rel="apple-touch-icon" href="IMT-180.png">
    <link rel="icon" href="IMT.jpg" type="image/jpeg">
    <link rel="manifest" href="manifest.webmanifest">
    <meta name="theme-color" content="#007aff">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-title" content="IMT Menu">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta property="og:title" content="IMT - Menu">
    <meta property="og:description" content="Menu giornaliero Pranzo e Cena">
    <meta property="og:type" content="website">
    <meta property="og:url" content="__PAGINA_URL__">
    <meta property="og:image" content="__CARTELLA_URL__IMT-anteprima.jpg">
    <meta property="og:image:secure_url" content="__CARTELLA_URL__IMT-anteprima.jpg">
    <meta property="og:image:type" content="image/jpeg">
    <meta property="og:image:width" content="800">
    <meta property="og:image:height" content="800">
    <meta name="twitter:card" content="summary">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f2f2f7; margin: 0; padding: 6px; color: #1c1c1e; overflow-x: hidden; }
        .app-container { max-width: 500px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; position: sticky; top: 6px; z-index: 100; box-shadow: 0 2px 6px rgba(0,0,0,0.15); border-radius: 12px; margin-bottom: 10px; transition: background-color 0.3s ease, color 0.3s ease; }
        .header-pranzo { background-color: #007aff !important; color: white !important; }
        .header-cena { background-color: #d1b246 !important; color: #1c1c1e !important; }
        .header-side { display: flex; gap: 6px; align-items: center; }
        .header button { border: none; font-size: 28px; font-weight: bold; width: 48px; height: 48px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: background-color 0.3s ease, color 0.3s ease; }
        .header-pranzo button { background: rgba(255, 255, 255, 0.2); color: white; }
        .header-cena button { background: rgba(0, 0, 0, 0.1); color: #1c1c1e; }
        .header button:disabled { opacity: 0.3; }
        .header-center { display: flex; flex-direction: column; align-items: center; flex-grow: 1; min-width: 0; min-height: 48px; justify-content: center; cursor: pointer; padding: 0 4px; }
        .header-top { font-size: 1.2rem; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 2px; }
        .header h1 { margin: 0; font-size: 0.85rem; text-align: center; font-weight: 500; }
        .content-wrapper { position: relative; overflow: hidden; border-radius: 10px; }
        .content { cursor: pointer; position: relative; z-index: 2; background-color: #f2f2f7; width: 100%; box-sizing: border-box; }
        .course-card { background: white; border-radius: 10px; padding: 8px 12px; margin-bottom: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .course-title { color: #007aff; background-color: #e6f4ff; font-size: 0.95rem; margin-top: 0; margin-bottom: 6px; padding: 6px 8px; border-radius: 6px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; text-align: center; }
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { padding: 2px 0; border-bottom: 1px solid #f2f2f7; position: relative; padding-left: 12px; line-height: 1.15; font-size: 0.9rem; }
        li:last-child { border-bottom: none; }
        li::before { content: "•"; color: #007aff; font-weight: bold; position: absolute; left: 0; font-size: 1.1rem; top: 0px; }
        .hidden { display: none !important; }
        .contatore-riga { display: flex; justify-content: center; align-items: center; gap: 10px; margin: 4px 0 12px; }
        .bandiera { border: none; background: none; padding: 0; cursor: pointer; line-height: 0; opacity: 0.35; transition: opacity 0.2s; flex-shrink: 0; }
        .bandiera.attiva { opacity: 1; }
        .bandiera svg { width: 26px; height: 17px; border-radius: 3px; box-shadow: 0 0 0 1px rgba(0,0,0,0.15); display: block; }
        .contatore { display: inline-block; margin: 0; padding: 5px 16px; background: #e6f4ff; color: #3a3a3c; border: 1px solid #b3d7ff; border-radius: 999px; box-shadow: 0 1px 2px rgba(0,0,0,0.06); text-align: center; font-size: 0.95rem; min-height: 1.2em; cursor: pointer; }
        .contatore:hover { text-decoration: underline; }
        .utenti-legenda { text-align: center; font-size: 0.85rem; color: #52525b; margin-bottom: 8px; }
        .utenti-tab { width: 100%; border-collapse: collapse; font-size: 0.9rem; font-variant-numeric: tabular-nums; }
        .utenti-tab th { text-align: left; padding: 6px 8px; border-bottom: 2px solid #e5e5ea; color: #52525b; font-weight: 600; }
        .utenti-tab td { padding: 6px 8px; border-bottom: 1px solid #f2f2f7; }
        .utenti-tab .online, .utenti-legenda .online { color: #d70015; font-weight: 600; }
        .utenti-tab .offline, .utenti-legenda .offline { color: #007aff; }
        .utenti-tab td:first-child, .utenti-tab th:first-child { white-space: nowrap; width: 1%; }
        .utenti-tab td.nome { word-break: break-word; width: 99%; }
        .utenti-tab tr.mio { cursor: pointer; background: #fff5f5; }
        .utenti-tab .lingua { width: 1%; white-space: nowrap; text-align: right; }
        .utenti-tab td.lingua span { font-size: 0.75rem; font-weight: 700; border: 1px solid currentColor; border-radius: 4px; padding: 0 4px; }
        .nome-modifica { display: flex; gap: 4px; align-items: center; }
        .nome-input { flex: 1 1 auto; width: 0; min-width: 0; font-size: 0.9rem; padding: 4px 6px; border: 1px solid #c7c7cc; border-radius: 6px; box-sizing: border-box; }
        .nome-ok { flex-shrink: 0; padding: 4px 8px; border: none; border-radius: 6px; background: #007aff; color: white; font-weight: 600; cursor: pointer; }
        .footer-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
        .footer-row .source-note { flex: 1; min-width: 0; }
        .share-btn { flex-shrink: 0; border: none; background: none; color: #007aff; width: 40px; height: 40px; margin-top: 1px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .share-btn:hover, .share-btn:active { background: #e6f4ff; }
        .share-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.35); z-index: 1000; display: flex; align-items: flex-end; justify-content: center; padding: 10px; box-sizing: border-box; }
        .share-panel { background: white; border-radius: 14px; width: 100%; max-width: 480px; padding: 16px; box-sizing: border-box; position: relative; max-height: 90vh; overflow: auto; font-size: 0.9rem; box-shadow: 0 6px 24px rgba(0,0,0,0.2); }
        .share-panel h3 { margin: 0 0 12px; font-size: 1rem; text-align: center; }
        .share-close { position: absolute; top: 4px; right: 8px; border: none; background: none; font-size: 26px; line-height: 1; padding: 6px; cursor: pointer; color: #6b6b70; }
        .share-action { display: block; width: 100%; padding: 12px; margin-bottom: 8px; border: none; border-radius: 10px; background: #007aff; color: white; font-size: 0.95rem; font-weight: 600; cursor: pointer; }
        .share-action.secondario { background: #e6f4ff; color: #007aff; }
        .share-msg { text-align: center; color: #1a7f37; min-height: 1.2em; margin: 2px 0 6px; }
        .share-msg:empty { min-height: 0; margin: 0; }
        .share-help { line-height: 1.45; background: #f2f2f7; border-radius: 10px; padding: 10px; }
        .share-help:empty { display: none; }
        .share-all { margin-top: 10px; color: #52525b; line-height: 1.45; }
        .share-all summary { cursor: pointer; }
        .share-all p { margin: 8px 0; }
        .source-note { font-size:0.8rem; line-height:1.5; color:#52525b; padding:10px; }
        .source-note a { color:#0056b3; }
        .anim-next { animation: slideOverRight 1s cubic-bezier(0.25, 1, 0.5, 1) forwards; }
        .anim-prev { animation: slideOverLeft 1s cubic-bezier(0.25, 1, 0.5, 1) forwards; }
        .anim-lang { animation: dropDown 1s cubic-bezier(0.25, 1, 0.5, 1) forwards; }
        @keyframes slideOverRight { 0% { transform: translateX(100%); box-shadow: -15px 0 20px rgba(0,0,0,0.1); } 100% { transform: translateX(0); box-shadow: 0 0 0 rgba(0,0,0,0); } }
        @keyframes slideOverLeft { 0% { transform: translateX(-100%); box-shadow: 15px 0 20px rgba(0,0,0,0.1); } 100% { transform: translateX(0); box-shadow: 0 0 0 rgba(0,0,0,0); } }
        @keyframes dropDown { 0% { transform: translateY(-100%); box-shadow: 0 15px 20px rgba(0,0,0,0.1); opacity: 1; } 100% { transform: translateY(0); box-shadow: 0 0 0 rgba(0,0,0,0); opacity: 1; } }
    </style>
</head>
<body>
    <div class="app-container">
        <div class="header" id="main-header">
            <div class="header-side">
                <button id="btn-prev" aria-label="Pasto precedente / Previous meal" onclick="navigate(-1)">&#9664;</button>
            </div>
            <div class="header-center" onclick="speakMenu(event)" role="button" tabindex="0" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();speakMenu(event);}" aria-label="Ascolta o interrompi il menu / Play or stop menu" title="Ascolta o interrompi / Play or stop">
                <div class="header-top" id="meal-type">IMT - Menu</div>
                <h1 id="meal-date">Caricamento...</h1>
            </div>
            <div class="header-side">
                <button id="btn-next" aria-label="Pasto successivo / Next meal" onclick="navigate(1)">&#9654;</button>
            </div>
        </div>
        <div class="contatore-riga">
            <button class="bandiera" id="bandiera-it" onclick="scegliLingua('it')" aria-label="Italiano" title="Italiano"><svg viewBox="0 0 3 2" aria-hidden="true"><rect width="1" height="2" fill="#009246"/><rect x="1" width="1" height="2" fill="#ffffff"/><rect x="2" width="1" height="2" fill="#ce2b37"/></svg></button>
            <div class="contatore hidden" id="contatore-utenti" aria-live="polite" role="button" tabindex="0" onclick="apriUtenti()" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();apriUtenti();}" title="Mostra i dispositivi / Show devices"></div>
            <button class="bandiera" id="bandiera-en" onclick="scegliLingua('en')" aria-label="English" title="English"><svg viewBox="0 0 60 30" aria-hidden="true"><clipPath id="uk-s"><path d="M0,0 v30 h60 v-30 z"/></clipPath><clipPath id="uk-t"><path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z"/></clipPath><g clip-path="url(#uk-s)"><path d="M0,0 v30 h60 v-30 z" fill="#012169"/><path d="M0,0 L60,30 M60,0 L0,30" stroke="#ffffff" stroke-width="6"/><path d="M0,0 L60,30 M60,0 L0,30" clip-path="url(#uk-t)" stroke="#C8102E" stroke-width="4"/><path d="M30,0 v30 M0,15 h60" stroke="#ffffff" stroke-width="10"/><path d="M30,0 v30 M0,15 h60" stroke="#C8102E" stroke-width="6"/></g></svg></button>
        </div>
        <div class="content-wrapper" id="content-wrapper">
            <div class="content" id="menu-content" onclick="toggleLanguage()" title="Clicca per cambiare lingua">
                <div class="course-card" id="card-primi"><h2 class="course-title" id="title-primi">Primi</h2><ul id="list-primi"></ul></div>
                <div class="course-card" id="card-secondi"><h2 class="course-title" id="title-secondi">Secondi</h2><ul id="list-secondi"></ul></div>
                <div class="course-card" id="card-contorno"><h2 class="course-title" id="title-contorno">Contorni</h2><ul id="list-contorno"></ul></div>
                <div class="course-card" id="card-frutta"><h2 class="course-title" id="title-frutta">Frutta / Dessert</h2><ul id="list-frutta"></ul></div>
            </div>
        </div>
        <div class="footer-row">
        <details class="source-note"><summary>by Teresa Mazzarisi</summary>
            <p>Piatti del giorno in grassetto; alternative fisse in carattere normale. I riferimenti agli allergeni sono disponibili nei PDF originali.</p>
            <p>Daily dishes in bold; fixed alternatives in regular type. Allergen references are available in the original PDFs.</p>
            <p><a href="Autunno/MENU_IMT_PRANZO_AUTUNNO_2026.pdf">PDF pranzo / Lunch</a> · <a href="Autunno/MENU_IMT_CENA_AUTUNNO_2026.pdf">PDF cena / Dinner</a> · <a href="menu-giornaliero-completo-autunno-2026.xlsx">Excel completo</a></p>
            <p>Alternative: pagina 5 dei PDF autunnali. La sezione Frutta / Dessert riporta le alternative indicate. I refusi 2025 nelle date sono ricondotti alla decorrenza 2026.</p>
        </details>
        <button class="share-btn" id="btn-condividi" onclick="apriCondivisione()" aria-label="Condividi o salva sulla Home / Share or save to Home screen" title="Condividi / Salva sulla Home">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12"/><path d="M7 8l5-5 5 5"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/></svg>
        </button>
        </div>
    </div>

    <div class="share-overlay hidden" id="share-overlay" onclick="if (event.target === this) chiudiCondivisione()">
        <div class="share-panel" role="dialog" aria-modal="true" aria-labelledby="share-title">
            <button class="share-close" onclick="chiudiCondivisione()" aria-label="Chiudi / Close">&times;</button>
            <h3 id="share-title"></h3>
            <button class="share-action" id="share-link" onclick="condividiLink()"></button>
            <button class="share-action secondario" id="share-copy" onclick="copiaLink()"></button>
            <button class="share-action secondario" id="share-install" onclick="aggiungiHome()"></button>
            <div class="share-msg" id="share-msg" aria-live="polite"></div>
            <div class="share-help" id="share-help"></div>
            <details class="share-all"><summary id="share-all-title"></summary><div id="share-all"></div></details>
        </div>
    </div>

    <div class="share-overlay hidden" id="utenti-overlay" onclick="if (event.target === this) chiudiUtenti()">
        <div class="share-panel" role="dialog" aria-modal="true" aria-labelledby="utenti-title">
            <button class="share-close" onclick="chiudiUtenti()" aria-label="Chiudi / Close">&times;</button>
            <h3 id="utenti-title"></h3>
            <div class="utenti-legenda" id="utenti-legenda"></div>
            <table class="utenti-tab" id="utenti-tabella"></table>
        </div>
    </div>

    <script>
        const menuData = __JSON_DATA__;
        let currentIndex = 0;
        let currentLang = 'it'; 
        let isAnimating = false; 

        let speakTimeout;
        let isSpeakingTimeout = false;

        let availableVoices = [];
        function loadVoices() { availableVoices = window.speechSynthesis.getVoices(); }
        if ('speechSynthesis' in window) { loadVoices(); if (window.speechSynthesis.onvoiceschanged !== undefined) window.speechSynthesis.onvoiceschanged = loadVoices; }

        function getBestVoice(langCode) {
            if (availableVoices.length === 0) loadVoices();
            const langPrefix = langCode.split('-')[0].toLowerCase();
            const filteredVoices = availableVoices.filter(v => v.lang.toLowerCase().startsWith(langPrefix));
            if (filteredVoices.length === 0) return null;
            const premiumKeywords = ['siri', 'enhanced', 'premium', 'natural', 'network', 'online', 'alice', 'luca'];
            for (let keyword of premiumKeywords) {
                const best = filteredVoices.find(v => v.name.toLowerCase().includes(keyword));
                if (best) return best;
            }
            return filteredVoices.find(v => v.default) || filteredVoices[0];
        }

        function speakMenu(event) {
            event.stopPropagation(); 
            if (!('speechSynthesis' in window)) return;
            if (window.speechSynthesis.speaking || isSpeakingTimeout) {
                window.speechSynthesis.cancel(); clearTimeout(speakTimeout); isSpeakingTimeout = false; return;
            }

            const meal = menuData[currentIndex];
            const isIt = currentLang === 'it';

            let chunksToRead = [];

            const dateStr = isIt ? meal.date_it : meal.date_en;
            let mealNameIt = meal.type.toLowerCase() === 'pranzo' ? 'il pranzo' : 'la cena';
            let mealNameEn = meal.type.toLowerCase() === 'pranzo' ? 'lunch' : 'dinner';
            
            let introText = isIt ? `Ciao, ecco ${mealNameIt} della IMT per ${dateStr}.` : `Hello, here is the IMT ${mealNameEn} for ${dateStr}.`;
            chunksToRead.push({ text: introText, delay: 200 });
            
            function extractCardBoldTexts(cardId, translatedTitle) {
                const card = document.getElementById(cardId);
                if (card.classList.contains('hidden')) return;
                const boldElements = card.querySelectorAll('strong');
                if (boldElements.length === 0) return;
                let itemsArray = [];
                boldElements.forEach(el => itemsArray.push(el.innerText));
                let conjunction = isIt ? " e " : " and ";
                chunksToRead.push({ text: translatedTitle + ". " + itemsArray.join(conjunction) + ".", delay: 200 });
            }
            
            extractCardBoldTexts('card-primi', isIt ? "Primi" : "First Courses");
            extractCardBoldTexts('card-secondi', isIt ? "Secondi" : "Main Courses");
            extractCardBoldTexts('card-contorno', isIt ? "Contorni" : "Side Dishes");
            extractCardBoldTexts('card-frutta', isIt ? "Frutta e Dessert" : "Fruit and Dessert");
            
            if (chunksToRead.length === 1) chunksToRead.push({ text: isIt ? "Nessun piatto in grassetto." : "No bold items.", delay: 200 });

            let closingTextIt = meal.type.toLowerCase() === 'pranzo' ? "Buon pranzo!" : "Buona cena!";
            let closingTextEn = meal.type.toLowerCase() === 'pranzo' ? "Enjoy your lunch!" : "Enjoy your dinner!";
            chunksToRead.push({ text: isIt ? closingTextIt : closingTextEn, delay: 0 });

            const langCode = isIt ? 'it-IT' : 'en-US';
            const bestVoice = getBestVoice(langCode);

            let chunkIndex = 0;
            function playNextChunk() {
                if (chunkIndex >= chunksToRead.length) { isSpeakingTimeout = false; return; }
                let currentChunk = chunksToRead[chunkIndex];
                const utterance = new SpeechSynthesisUtterance(currentChunk.text);
                if (bestVoice) utterance.voice = bestVoice; else utterance.lang = langCode;
                utterance.rate = 0.9; 
                utterance.onend = function() {
                    chunkIndex++;
                    if (chunkIndex < chunksToRead.length) {
                        isSpeakingTimeout = true;
                        speakTimeout = setTimeout(playNextChunk, currentChunk.delay); 
                    } else isSpeakingTimeout = false;
                };
                utterance.onerror = function() { isSpeakingTimeout = false; };
                window.speechSynthesis.speak(utterance);
            }
            playNextChunk();
        }

        function toggleLanguage() {
            if (isAnimating) return; 
            currentLang = currentLang === 'it' ? 'en' : 'it';
            sessionStorage.setItem('savedLang', currentLang);
            salvaLingua(currentLang);
            if (menuData[currentIndex]) {
                sessionStorage.setItem('savedDate', menuData[currentIndex].date);
                sessionStorage.setItem('savedType', menuData[currentIndex].type);
            }
            sessionStorage.setItem('justToggled', 'true');
            window.location.href = window.location.pathname + '?v=' + new Date().getTime();
        }

        function renderMeal(index, animType) {
            if (!menuData || menuData.length === 0) return;
            const contentWrapper = document.getElementById('content-wrapper');
            const contentDiv = document.getElementById('menu-content');
            
            if (!animType && isAnimating) {
                isAnimating = false;
                const existingClone = document.getElementById('anim-clone');
                if (existingClone) existingClone.remove();
            }
            if (isAnimating && animType) return;
            
            if (window.speechSynthesis && window.speechSynthesis.speaking) window.speechSynthesis.cancel();
            if (typeof speakTimeout !== 'undefined') { clearTimeout(speakTimeout); isSpeakingTimeout = false; }
            
            if (animType) {
                isAnimating = true;
                const clone = contentDiv.cloneNode(true);
                clone.id = 'anim-clone';
                clone.querySelectorAll('[id]').forEach(element => element.removeAttribute('id'));
                clone.style.position = 'absolute'; clone.style.top = '0'; clone.style.left = '0'; clone.style.width = '100%';
                clone.style.zIndex = '1'; clone.style.animation = 'none'; clone.style.transform = 'none'; clone.style.pointerEvents = 'none'; 
                contentWrapper.appendChild(clone);
                setTimeout(() => { if (clone.parentNode) clone.parentNode.removeChild(clone); isAnimating = false; }, 1000); 
            }

            currentIndex = index;
            const meal = menuData[currentIndex];
            const isIt = currentLang === 'it';

            const titleType = isIt ? meal.meal_type_it : meal.meal_type_en;
            document.getElementById('meal-type').innerText = `IMT - ${titleType}`;
            document.getElementById('meal-date').innerText = isIt ? meal.date_it : meal.date_en;
            document.getElementById('title-primi').innerText = isIt ? "Primi" : "First Courses";
            document.getElementById('title-secondi').innerText = isIt ? "Secondi" : "Main Courses";
            document.getElementById('title-contorno').innerText = isIt ? "Contorni" : "Side Dishes";
            document.getElementById('title-frutta').innerText = isIt ? "Frutta / Dessert" : "Fruit & Dessert";
            
            const header = document.getElementById('main-header');
            if (meal.type.toLowerCase() === 'pranzo') header.className = 'header header-pranzo';
            else header.className = 'header header-cena';

            const updateList = (id, items_it, items_en) => {
                const card = document.getElementById('card-' + id);
                const ul = document.getElementById('list-' + id);
                const items = isIt ? items_it : items_en;
                if (items && items.length > 0) {
                    ul.innerHTML = items.map(i => `<li>${i}</li>`).join('');
                    card.classList.remove('hidden');
                } else card.classList.add('hidden');
            };

            updateList('primi', meal.Primi_it, meal.Primi_en);
            updateList('secondi', meal.Secondi_it, meal.Secondi_en);
            updateList('contorno', meal.Contorno_it, meal.Contorno_en);
            updateList('frutta', meal.Frutta_it, meal.Frutta_en);

            document.getElementById('btn-prev').disabled = (currentIndex === 0);
            document.getElementById('btn-next').disabled = (currentIndex === menuData.length - 1);

            contentDiv.classList.remove('anim-next', 'anim-prev', 'anim-lang');
            void contentDiv.offsetWidth; 
            if (animType) contentDiv.classList.add('anim-' + animType);
        }

        function navigate(direction) {
            const newIndex = currentIndex + direction;
            if (newIndex >= 0 && newIndex < menuData.length) {
                let animType = isAnimating ? null : (direction > 0 ? 'next' : 'prev');
                renderMeal(newIndex, animType);
            }
        }

        
        function goToToday() {
            if (isAnimating) return;
            const index = getInitialMealIndex();
            renderMeal(index, null);
        }

        window.addEventListener('keydown', function(e) {
            if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;
            if (document.querySelector('.share-overlay:not(.hidden)')) { if (e.key === 'Escape') { chiudiCondivisione(); chiudiUtenti(); } return; }
            if (e.key === 'ArrowLeft') document.getElementById('btn-prev').click();
            else if (e.key === 'ArrowRight') document.getElementById('btn-next').click();
        });

        let touchstartX = 0; let touchstartY = 0; let touchendX = 0; let touchendY = 0; let startScrollY = 0;
        const thresholdX = 50; const thresholdY = 60; 

        document.addEventListener('touchstart', e => {
            touchstartX = e.changedTouches[0].screenX; touchstartY = e.changedTouches[0].screenY; startScrollY = window.scrollY; 
        }, { passive: true });

        document.addEventListener('touchend', e => {
            if (isAnimating) return;
            if (document.querySelector('.share-overlay:not(.hidden)')) return;
            touchendX = e.changedTouches[0].screenX; touchendY = e.changedTouches[0].screenY;
            const diffX = touchendX - touchstartX; const diffY = Math.abs(touchendY - touchstartY); const rawDiffY = touchendY - touchstartY; 
            if (diffY < thresholdY) {
                if (diffX <= -thresholdX && !document.getElementById('btn-next').disabled) document.getElementById('btn-next').click();
                else if (diffX >= thresholdX && !document.getElementById('btn-prev').disabled) document.getElementById('btn-prev').click();
            } else if (rawDiffY > 100 && Math.abs(diffX) < thresholdX && startScrollY <= 0) {
                sessionStorage.setItem('savedLang', currentLang);
                if (menuData[currentIndex]) {
                    sessionStorage.setItem('savedDate', menuData[currentIndex].date);
                    sessionStorage.setItem('savedType', menuData[currentIndex].type);
                }
                window.location.href = window.location.pathname + '?v=' + new Date().getTime();
            }
        }, { passive: true });

        function getInitialMealIndex() {
            if (!menuData || menuData.length === 0) return 0;
            const now = new Date();
            const currentDateString = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
            let targetType = (now.getHours() > 15 || (now.getHours() === 15 && now.getMinutes() > 0)) ? "Cena" : "Pranzo";
            let foundIndex = menuData.findIndex(m => m.date === currentDateString && m.type.toLowerCase() === targetType.toLowerCase());
            if (foundIndex === -1) foundIndex = menuData.findIndex(m => m.date === currentDateString);
            if (foundIndex === -1) foundIndex = menuData.findIndex(m => m.date > currentDateString);
            if (foundIndex === -1) foundIndex = menuData.length - 1;
            return Math.max(0, foundIndex);
        }

        // ---- Contatore utenti (Firebase Realtime Database via REST) ----
        // Ogni dispositivo riceve un codice univoco nascosto, salvato nel browser.
        // utenti/<codice> = primo accesso; totale = numero di dispositivi registrati;
        // online/<codice> = ultimo segnale (ogni 5 s, solo con la pagina visibile).
        const CONTATORE_URL = "__CONTATORE_URL__";
        const CONTATORE_INTERVALLO = 5000;     // controllo ogni 5 secondi
        const CONTATORE_ATTIVO_MS = 15000;     // "collegato adesso" = segnale negli ultimi 15 secondi
        const CONTATORE_PULIZIA_MS = 600000;   // segnali più vecchi di 10 minuti vengono cancellati
        let contatoreId = null, contatoreRegistrato = false, contatoreInCorso = false;
        let contatoreScarto = 0;   // differenza tra orologio del server e del dispositivo

        function contatoreCodice() {
            try {
                let id = localStorage.getItem('imt-id-dispositivo');
                if (!id) {
                    id = (window.crypto && crypto.randomUUID) ? crypto.randomUUID()
                        : Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 12) + Math.random().toString(36).slice(2, 12);
                    localStorage.setItem('imt-id-dispositivo', id);
                }
                contatoreRegistrato = localStorage.getItem('imt-id-registrato') === id;
                return id;
            } catch (e) { return null; }
        }

        async function contatoreFb(percorso, metodo, dati) {
            const opzioni = { method: metodo || 'GET', cache: 'no-store' };
            if (dati !== undefined) opzioni.body = JSON.stringify(dati);
            const r = await fetch(CONTATORE_URL + '/' + percorso + '.json', opzioni);
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        }

        function contatoreMostra(n, t) {
            const el = document.getElementById('contatore-utenti');
            const f = x => x.toLocaleString(currentLang === 'it' ? 'it-IT' : 'en-GB');
            el.innerHTML = currentLang === 'it'
                ? `<b>${f(n)}</b> ${n === 1 ? 'utente collegato' : 'utenti collegati'} adesso su <b>${f(t)}</b>`
                : `<b>${f(n)}</b> ${n === 1 ? 'user' : 'users'} online now out of <b>${f(t)}</b>`;
            el.classList.remove('hidden');
        }

        async function contatoreCiclo() {
            if (contatoreInCorso || document.visibilityState === 'hidden') return;
            contatoreInCorso = true;
            try {
                if (!contatoreRegistrato) {
                    const esiste = await contatoreFb('utenti/' + contatoreId);
                    if (esiste === null) {
                        // registrazione e incremento del totale in un'unica operazione atomica
                        await contatoreFb('', 'PATCH', {
                            ['utenti/' + contatoreId]: { '.sv': 'timestamp' },
                            'totale': { '.sv': { 'increment': 1 } }
                        });
                    }
                    contatoreRegistrato = true;
                    try { localStorage.setItem('imt-id-registrato', contatoreId); } catch (e) {}
                }
                const adesso = await contatoreFb('online/' + contatoreId, 'PUT', { '.sv': 'timestamp' });
                contatoreScarto = adesso - Date.now();
                // ogni 5 secondi comunica la lingua in uso su questo dispositivo
                contatoreFb('lingua/' + contatoreId, 'PUT', currentLang).catch(() => {});
                salvaLingua(currentLang);
                const [online, totale] = await Promise.all([contatoreFb('online'), contatoreFb('totale')]);
                let n = 0; const vecchi = {};
                for (const [codice, t] of Object.entries(online || {})) {
                    if (typeof t !== 'number') continue;
                    if (t >= adesso - CONTATORE_ATTIVO_MS) n++;
                    else if (t < adesso - CONTATORE_PULIZIA_MS) vecchi[codice] = null;
                }
                if (Object.keys(vecchi).length) contatoreFb('online', 'PATCH', vecchi).catch(() => {});
                n = Math.max(n, 1);
                contatoreMostra(n, Math.max(Number(totale) || 0, n));
                if (!document.getElementById('utenti-overlay').classList.contains('hidden')) aggiornaUtenti();
            } catch (e) {
                document.getElementById('contatore-utenti').classList.add('hidden');
            } finally {
                contatoreInCorso = false;
            }
        }

        function contatoreAvvia() {
            if (!CONTATORE_URL || !window.fetch) return;
            contatoreId = contatoreCodice();
            if (!contatoreId) return;
            recuperaLinguaArchivio().then(contatoreCiclo);
            setInterval(contatoreCiclo, CONTATORE_INTERVALLO);
            document.addEventListener('visibilitychange', () => {
                if (document.visibilityState === 'visible') contatoreCiclo();
                else fetch(CONTATORE_URL + '/online/' + contatoreId + '.json', { method: 'DELETE', keepalive: true }).catch(() => {});
            });
        }

        // ---- Condivisione e salvataggio sulla Home ----
        const PAGINA_URL = "__PAGINA_URL__";
        let promptInstallazione = null;
        window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); promptInstallazione = e; });
        window.addEventListener('appinstalled', () => { promptInstallazione = null; mostraMsgCondivisione(testiCondivisione().installata); });

        const ISTRUZIONI_HOME = {
            it: {
                ios: '<b>iPhone / iPad</b>: apri la pagina in <b>Safari</b>, tocca il pulsante <b>Condividi</b> (il quadrato con la freccia in su) e scegli <b>Aggiungi alla schermata Home</b>, poi <b>Aggiungi</b>. Se non vedi la voce, scorri l’elenco verso il basso.',
                android: '<b>Android</b>: in <b>Chrome</b> tocca il menu <b>⋮</b> in alto a destra e scegli <b>Aggiungi a schermata Home</b> (o <b>Installa app</b>), poi conferma. In <b>Samsung Internet</b>: menu <b>≡</b> → <b>Aggiungi pagina a</b> → <b>Schermata Home</b>.',
                mac: '<b>Mac</b>: in <b>Safari</b> menu <b>File</b> → <b>Aggiungi al Dock</b>. In <b>Chrome</b> menu <b>⋮</b> → <b>Trasmetti, salva e condividi</b> → <b>Installa pagina come app</b>.',
                pc: '<b>PC Windows</b>: in <b>Edge</b> menu <b>…</b> → <b>App</b> → <b>Installa questo sito come app</b>. In <b>Chrome</b> menu <b>⋮</b> → <b>Trasmetti, salva e condividi</b> → <b>Installa pagina come app</b> (oppure <b>Crea scorciatoia</b>). L’app si può poi aggiungere alla barra delle applicazioni o al menu Start.'
            },
            en: {
                ios: '<b>iPhone / iPad</b>: open the page in <b>Safari</b>, tap the <b>Share</b> button (the square with the up arrow) and choose <b>Add to Home Screen</b>, then <b>Add</b>. If you don’t see it, scroll down the list.',
                android: '<b>Android</b>: in <b>Chrome</b> tap the <b>⋮</b> menu at the top right and choose <b>Add to Home screen</b> (or <b>Install app</b>), then confirm. In <b>Samsung Internet</b>: menu <b>≡</b> → <b>Add page to</b> → <b>Home screen</b>.',
                mac: '<b>Mac</b>: in <b>Safari</b> choose <b>File</b> → <b>Add to Dock</b>. In <b>Chrome</b> menu <b>⋮</b> → <b>Cast, save and share</b> → <b>Install page as app</b>.',
                pc: '<b>Windows PC</b>: in <b>Edge</b> menu <b>…</b> → <b>Apps</b> → <b>Install this site as an app</b>. In <b>Chrome</b> menu <b>⋮</b> → <b>Cast, save and share</b> → <b>Install page as app</b> (or <b>Create shortcut</b>). You can then pin it to the taskbar or Start menu.'
            }
        };

        function testiCondivisione() {
            return currentLang === 'it' ? {
                titolo: 'Condividi o salva sulla Home', condividi: 'Condividi il link', copia: 'Copia il link',
                home: 'Aggiungi alla schermata Home', copiato: 'Link copiato', nonCopiato: 'Copia non riuscita: ',
                tutti: 'Istruzioni per tutti i dispositivi', giaApp: 'Il menu è già aperto come app.',
                installata: 'Menu installato', testo: 'Menu della mensa IMT - Pranzo e Cena'
            } : {
                titolo: 'Share or save to Home screen', condividi: 'Share the link', copia: 'Copy the link',
                home: 'Add to Home screen', copiato: 'Link copied', nonCopiato: 'Copy failed: ',
                tutti: 'Instructions for all devices', giaApp: 'The menu is already open as an app.',
                installata: 'Menu installed', testo: 'IMT canteen menu - Lunch and Dinner'
            };
        }

        function piattaforma() {
            const ua = navigator.userAgent;
            if (/iPhone|iPad|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) return 'ios';
            if (/Android/.test(ua)) return 'android';
            if (/Macintosh|Mac OS X/.test(ua)) return 'mac';
            return 'pc';
        }

        function isApp() {
            return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
        }

        function mostraMsgCondivisione(testo) {
            const el = document.getElementById('share-msg');
            el.textContent = testo;
            clearTimeout(mostraMsgCondivisione.t);
            mostraMsgCondivisione.t = setTimeout(() => { el.textContent = ''; }, 4000);
        }

        function apriCondivisione() {
            const t = testiCondivisione();
            document.getElementById('share-title').textContent = t.titolo;
            const btnLink = document.getElementById('share-link');
            btnLink.textContent = t.condividi;
            btnLink.classList.toggle('hidden', !navigator.share);
            document.getElementById('share-copy').textContent = t.copia;
            document.getElementById('share-install').textContent = t.home;
            document.getElementById('share-msg').textContent = '';
            document.getElementById('share-help').innerHTML = '';
            document.getElementById('share-all-title').textContent = t.tutti;
            const ist = ISTRUZIONI_HOME[currentLang];
            document.getElementById('share-all').innerHTML = ['ios', 'android', 'mac', 'pc'].map(p => '<p>' + ist[p] + '</p>').join('');
            if (window.speechSynthesis && window.speechSynthesis.speaking) window.speechSynthesis.cancel();
            document.getElementById('share-overlay').classList.remove('hidden');
        }

        // ---- Lingua ricordata tra un avvio e l'altro ----
        function leggiLingua() {
            try { return localStorage.getItem('imt-lingua'); } catch (e) { return null; }
        }

        function salvaLingua(lingua) {
            try { localStorage.setItem('imt-lingua', lingua); } catch (e) {}
        }

        // Se il dispositivo non ha la lingua salvata (es. prima di questo aggiornamento),
        // la recupera dall'archivio online e passa subito a quella lingua.
        async function recuperaLinguaArchivio() {
            if (leggiLingua() || sessionStorage.getItem('savedLang')) return;
            try {
                const l = await contatoreFb('lingua/' + contatoreId);
                if ((l === 'it' || l === 'en') && !leggiLingua()) {
                    salvaLingua(l);
                    if (l !== currentLang) { currentLang = l; renderMeal(currentIndex); aggiornaBandiere(); }
                }
            } catch (e) {}
        }

        // ---- Bandierine della lingua ----
        function scegliLingua(lingua) {
            if (lingua !== currentLang) toggleLanguage();
        }

        function aggiornaBandiere() {
            ['it', 'en'].forEach(l => document.getElementById('bandiera-' + l).classList.toggle('attiva', l === currentLang));
        }

        // ---- Tabella dei dispositivi registrati ----
        function apriUtenti() {
            if (!contatoreId) return;
            document.getElementById('utenti-title').textContent = currentLang === 'it' ? 'Dispositivi registrati' : 'Registered devices';
            document.getElementById('utenti-overlay').classList.remove('hidden');
            aggiornaUtenti();
        }

        function chiudiUtenti() {
            utentiInModifica = false;
            document.getElementById('utenti-overlay').classList.add('hidden');
        }

        let utentiInModifica = false;   // true mentre si scrive il nome: la tabella non si ridisegna
        const escHtml = x => String(x).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

        async function aggiornaUtenti() {
            if (utentiInModifica) return;
            const it = currentLang === 'it';
            const legenda = document.getElementById('utenti-legenda');
            const tabella = document.getElementById('utenti-tabella');
            try {
                const [utenti, online, nomi, lingue] = await Promise.all([contatoreFb('utenti'), contatoreFb('online'), contatoreFb('nomi'), contatoreFb('lingua')]);
                if (utentiInModifica) return;
                const adesso = Date.now() + contatoreScarto;
                const collegato = codice => {
                    const t = (online || {})[codice];
                    return typeof t === 'number' && t >= adesso - CONTATORE_ATTIVO_MS;
                };
                // prima i collegati, poi gli altri; in ogni gruppo dal più recente
                const righe = Object.entries(utenti || {})
                    .filter(([codice, t]) => typeof t === 'number')
                    .map(([codice, t]) => ({ codice, t, on: collegato(codice) || codice === contatoreId }))
                    .sort((a, b) => (b.on - a.on) || (b.t - a.t));
                document.getElementById('utenti-title').textContent = (it ? 'Dispositivi registrati: ' : 'Registered devices: ') + righe.length.toLocaleString(it ? 'it-IT' : 'en-GB');
                const GS = it ? ['Do', 'Lu', 'Ma', 'Me', 'Gi', 'Ve', 'Sa'] : ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
                const due = x => String(x).padStart(2, '0');
                const quando = t => {   // GS GG/MM/AAAA HH:MM
                    const d = new Date(t);
                    return GS[d.getDay()] + ' ' + due(d.getDate()) + '/' + due(d.getMonth() + 1) + '/' + d.getFullYear() + ' ' + due(d.getHours()) + ':' + due(d.getMinutes());
                };
                // lingua (IT / EN) solo per i dispositivi collegati adesso
                const cellaLingua = r => {
                    let l = r.codice === contatoreId ? currentLang : (lingue || {})[r.codice];
                    l = (l === 'it' || l === 'en') && r.on ? l.toUpperCase() : '';
                    return '<td class="lingua">' + (l ? '<span>' + l + '</span>' : '') + '</td>';
                };
                let n = 0;
                const corpo = righe.map(r => {
                    if (r.on) n++;
                    const nome = (nomi || {})[r.codice];
                    const classe = r.on ? 'online' : 'offline';
                    if (r.codice === contatoreId) {
                        const testo = nome ? escHtml(nome) : '<i>' + (it ? 'tocca per dare un nome' : 'tap to set a name') + '</i>';
                        return '<tr class="' + classe + ' mio" onclick="modificaNome()" title="' + (it ? 'Questo dispositivo: tocca per cambiare il nome' : 'This device: tap to change the name') + '">'
                            + '<td>' + quando(r.t) + '</td><td class="nome" id="nome-mio" data-nome="' + escHtml(nome || '') + '">' + testo + ' ✎</td>' + cellaLingua(r) + '</tr>';
                    }
                    return '<tr class="' + classe + '"><td>' + quando(r.t) + '</td><td class="nome">' + (nome ? escHtml(nome) : '') + '</td>' + cellaLingua(r) + '</tr>';
                }).join('');
                tabella.innerHTML = '<thead><tr><th>' + (it ? 'Data e ora' : 'Date and time') + '</th><th>' + (it ? 'Nome' : 'Name') + '</th><th class="lingua"></th></tr></thead><tbody>' + corpo + '</tbody>';
                legenda.innerHTML = it
                    ? '<span class="online">● collegati adesso: ' + n + '</span> &nbsp; <span class="offline">● non collegati: ' + (righe.length - n) + '</span>'
                    : '<span class="online">● online now: ' + n + '</span> &nbsp; <span class="offline">● offline: ' + (righe.length - n) + '</span>';
            } catch (e) {
                legenda.textContent = it ? 'Elenco non disponibile in questo momento.' : 'List not available right now.';
            }
        }

        function modificaNome() {
            if (utentiInModifica) return;
            const cella = document.getElementById('nome-mio');
            if (!cella) return;
            utentiInModifica = true;
            const it = currentLang === 'it';
            cella.innerHTML = '<div class="nome-modifica"><input id="nome-input" class="nome-input" maxlength="30" placeholder="' + (it ? 'Il tuo nome' : 'Your name') + '">'
                + '<button class="nome-ok" onclick="event.stopPropagation(); salvaNome()">OK</button></div>';
            const campo = document.getElementById('nome-input');
            campo.value = cella.dataset.nome || '';
            campo.addEventListener('click', e => e.stopPropagation());
            campo.addEventListener('keydown', e => {
                e.stopPropagation();
                if (e.key === 'Enter') { e.preventDefault(); salvaNome(); }
                else if (e.key === 'Escape') { utentiInModifica = false; aggiornaUtenti(); }
            });
            campo.focus();
        }

        async function salvaNome() {
            const campo = document.getElementById('nome-input');
            if (!campo) return;
            const nome = campo.value.trim().slice(0, 30);
            try {
                if (nome) await contatoreFb('nomi/' + contatoreId, 'PUT', nome);
                else await contatoreFb('nomi/' + contatoreId, 'DELETE');
            } catch (e) {
                document.getElementById('utenti-legenda').textContent = currentLang === 'it' ? 'Salvataggio del nome non riuscito.' : 'Could not save the name.';
            }
            utentiInModifica = false;
            aggiornaUtenti();
        }

        function chiudiCondivisione() {
            document.getElementById('share-overlay').classList.add('hidden');
        }

        async function condividiLink() {
            try {
                await navigator.share({ title: 'IMT - Menu', text: testiCondivisione().testo, url: PAGINA_URL });
            } catch (e) {
                if (e && e.name !== 'AbortError') copiaLink();
            }
        }

        async function copiaLink() {
            const t = testiCondivisione();
            try {
                await navigator.clipboard.writeText(PAGINA_URL);
                mostraMsgCondivisione(t.copiato);
            } catch (e) {
                const campo = document.createElement('textarea');
                campo.value = PAGINA_URL; campo.setAttribute('readonly', ''); campo.style.position = 'fixed'; campo.style.opacity = '0';
                document.body.appendChild(campo); campo.select();
                let ok = false;
                try { ok = document.execCommand('copy'); } catch (e2) {}
                campo.remove();
                mostraMsgCondivisione(ok ? t.copiato : t.nonCopiato + PAGINA_URL);
            }
        }

        async function aggiungiHome() {
            const t = testiCondivisione();
            if (isApp()) { document.getElementById('share-help').textContent = t.giaApp; return; }
            if (promptInstallazione) {
                const p = promptInstallazione;
                promptInstallazione = null;
                p.prompt();
                try { const scelta = await p.userChoice; if (scelta.outcome === 'accepted') mostraMsgCondivisione(t.installata); } catch (e) {}
                return;
            }
            document.getElementById('share-help').innerHTML = ISTRUZIONI_HOME[currentLang][piattaforma()];
        }

        window.onload = () => {
            // lingua: quella della sessione, altrimenti quella usata l'ultima volta su questo dispositivo
            const linguaIniziale = sessionStorage.getItem('savedLang') || leggiLingua();
            if (linguaIniziale === 'it' || linguaIniziale === 'en') currentLang = linguaIniziale;
            let animToPlay = null;
            if (sessionStorage.getItem('justToggled')) { animToPlay = 'lang'; sessionStorage.removeItem('justToggled'); }
            let startIdx = getInitialMealIndex();
            const savedDate = sessionStorage.getItem('savedDate'); const savedType = sessionStorage.getItem('savedType');
            if (savedDate && savedType) {
                let foundIndex = menuData.findIndex(m => m.date === savedDate && m.type === savedType);
                if (foundIndex !== -1) startIdx = foundIndex;
                sessionStorage.removeItem('savedDate'); sessionStorage.removeItem('savedType');
            }
            currentIndex = startIdx; renderMeal(currentIndex, animToPlay);
            aggiornaBandiere();
            contatoreAvvia();
            if ('serviceWorker' in navigator && location.protocol === 'https:') {
                navigator.serviceWorker.register('sw.js').catch(() => {});
            }
        };
    </script>
</body>
</html>
"""

    contatore_url = CONTATORE_URL.strip().rstrip('/')
    html_code = (html_template.replace('__CONTATORE_URL__', contatore_url)
                 .replace('__PAGINA_URL__', PAGINA_URL)
                 .replace('__CARTELLA_URL__', CARTELLA_URL)
                 .replace('__JSON_DATA__', json.dumps(blocks)))

    with open(file_output, 'w', encoding='utf-8') as f:
        f.write(html_code)

    prepara_icone(base)
    scrivi_file_app(base, datetime.now().strftime('%Y%m%d%H%M%S'))

    print(f"Generati {len(blocks)} menu per {len(pasti_per_data)} giorni: {file_output.name}, {file_siri.name}, manifest.webmanifest, sw.js.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Genera HTML e JSON Siri dai menu Excel')
    parser.add_argument('--input', help='File Excel da utilizzare')
    parser.add_argument('--traduci', action='store_true', help='Traduci online i nuovi piatti mancanti dal dizionario')
    args = parser.parse_args()
    genera_html(args.input, args.traduci)
