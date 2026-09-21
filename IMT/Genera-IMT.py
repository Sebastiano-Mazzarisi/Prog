# Nome.py: GeneraMenu.py
# Ultimo aggiornamento: 21/09/2026
# Descrizione: Legge menu-giornaliero-completo-autunno-2026.xlsx e genera Menu-IMT.html.
#              Generazione del file menu_siri.json con date multi-formato per evitare 
#              qualsiasi formattazione lato iOS Shortcuts.
# File di input: menu-giornaliero-completo-autunno-2026.xlsx
# File di output: Menu-IMT.html, menu_siri.json
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
    <link rel="apple-touch-icon" href="IMT.jpg">
    <link rel="icon" href="IMT.jpg" type="image/jpeg">
    <meta property="og:title" content="IMT - Menu">
    <meta property="og:description" content="Menu giornaliero Pranzo e Cena">
    <meta property="og:type" content="website">
    <meta property="og:image" content="https://sebastiano-mazzarisi.github.io/Prog/IMT/IMT.jpg">
    <meta property="og:image:secure_url" content="https://sebastiano-mazzarisi.github.io/Prog/IMT/IMT.jpg">
    <meta property="og:image:type" content="image/jpeg">
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
        
        <div class="content-wrapper" id="content-wrapper">
            <div class="content" id="menu-content" onclick="toggleLanguage()" title="Clicca per cambiare lingua">
                <div class="course-card" id="card-primi"><h2 class="course-title" id="title-primi">Primi</h2><ul id="list-primi"></ul></div>
                <div class="course-card" id="card-secondi"><h2 class="course-title" id="title-secondi">Secondi</h2><ul id="list-secondi"></ul></div>
                <div class="course-card" id="card-contorno"><h2 class="course-title" id="title-contorno">Contorni</h2><ul id="list-contorno"></ul></div>
                <div class="course-card" id="card-frutta"><h2 class="course-title" id="title-frutta">Frutta / Dessert</h2><ul id="list-frutta"></ul></div>
            </div>
        </div>
        <details class="source-note"><summary>Fonti e note / Sources and notes</summary>
            <p>Piatti del giorno in grassetto; alternative fisse in carattere normale. I riferimenti agli allergeni sono disponibili nei PDF originali.</p>
            <p>Daily dishes in bold; fixed alternatives in regular type. Allergen references are available in the original PDFs.</p>
            <p><a href="Autunno/MENU_IMT_PRANZO_AUTUNNO_2026.pdf">PDF pranzo / Lunch</a> · <a href="Autunno/MENU_IMT_CENA_AUTUNNO_2026.pdf">PDF cena / Dinner</a> · <a href="menu-giornaliero-completo-autunno-2026.xlsx">Excel completo</a></p>
            <p>Alternative: pagina 5 dei PDF autunnali. La sezione Frutta / Dessert riporta le alternative indicate. I refusi 2025 nelle date sono ricondotti alla decorrenza 2026.</p>
        </details>
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

        window.onload = () => {
            if (sessionStorage.getItem('savedLang')) currentLang = sessionStorage.getItem('savedLang');
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
        };
    </script>
</body>
</html>
"""

    html_code = html_template.replace('__JSON_DATA__', json.dumps(blocks))

    with open(file_output, 'w', encoding='utf-8') as f:
        f.write(html_code)

    print(f"Generati {len(blocks)} menu per {len(pasti_per_data)} giorni: {file_output.name}, {file_siri.name}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Genera HTML e JSON Siri dai menu Excel')
    parser.add_argument('--input', help='File Excel da utilizzare')
    parser.add_argument('--traduci', action='store_true', help='Traduci online i nuovi piatti mancanti dal dizionario')
    args = parser.parse_args()
    genera_html(args.input, args.traduci)
