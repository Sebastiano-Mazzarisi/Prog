# Nome.py: GeneraMenu.py
# Data e ora ultima modifica: 07/09/2026 10:35
# Descrizione: Legge menu-giornaliero-completo-estate-2026.xlsx e genera Menu-IMT.html.
#              Sintesi vocale ottimizzata: le alternative sono collegate con "e", i gruppi 
#              sono separati da 0.2s e la lettura si conclude con "Buon pranzo" o "Buona cena".
# File di input: menu-giornaliero-completo-estate-2026.xlsx
# File di output: Menu-IMT.html
# Parametri: Nessuno

import pandas as pd
import json
from datetime import datetime
import urllib.request
import urllib.parse
import os
import time

def genera_html():
    file_input = 'menu-giornaliero-completo-estate-2026.xlsx'
    file_output = 'Menu-IMT.html'
    dizionario_file = 'dizionario_menu.json'
    
    try:
        df = pd.read_excel(file_input)
    except FileNotFoundError:
        print(f"Errore: Il file {file_input} non è stato trovato.")
        return
        
    df = df.fillna('')
    
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
    
    if nuovi_termini:
        print(f"Trovati {len(nuovi_termini)} piatti da tradurre in inglese.")
        print("ATTENZIONE: Questa operazione richiederà un paio di minuti solo la prima volta...")
        
        for i, term in enumerate(nuovi_termini):
            url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=it&tl=en&dt=t&q=" + urllib.parse.quote(term)
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                response = urllib.request.urlopen(req)
                data = json.loads(response.read().decode('utf-8'))
                tradotto = data[0][0][0]
                
                if term.isupper():
                    tradotto = tradotto.upper()
                    
                dizionario[term] = tradotto
            except Exception as e:
                dizionario[term] = term 
                
            time.sleep(0.3) 
            if (i + 1) % 10 == 0:
                print(f"Tradotti {i + 1} di {len(nuovi_termini)}...")
                
        with open(dizionario_file, 'w', encoding='utf-8') as f:
            json.dump(dizionario, f, indent=4, ensure_ascii=False)
        print("Dizionario salvato con successo!")

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

    html_template = """<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Menu IMT</title>
    
    <link rel="apple-touch-icon" href="IMT.jpg">
    <link rel="icon" href="IMT.jpg" type="image/jpeg">
    <meta property="og:title" content="IMT - Menu">
    <meta property="og:description" content="Menu giornaliero Pranzo e Cena">
    <meta property="og:type" content="website">
    <meta property="og:image" content="https://sebastiano-mazzarisi.github.io/Prog/IMT/IMT.jpg">
    <meta property="og:image:secure_url" content="https://sebastiano-mazzarisi.github.io/Prog/IMT/IMT.jpg">
    <meta property="og:image:type" content="image/jpeg">
    <meta property="og:image:width" content="600">
    <meta property="og:image:height" content="600">

    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: #f2f2f7;
            margin: 0;
            padding: 6px; 
            color: #1c1c1e;
            overflow-x: hidden; 
        }
        .app-container {
            max-width: 500px;
            margin: 0 auto;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 8px; 
            position: sticky;
            top: 6px;
            z-index: 100;
            box-shadow: 0 2px 6px rgba(0,0,0,0.15);
            border-radius: 12px;
            margin-bottom: 10px;
            transition: background-color 0.3s ease, color 0.3s ease;
        }
        
        .header-pranzo {
            background-color: #007aff !important; 
            color: white !important; 
        }
        .header-cena {
            background-color: #d1b246 !important; 
            color: #1c1c1e !important;
        }
        
        .header-side {
            display: flex;
            gap: 4px; 
            align-items: center;
        }

        .header button {
            border: none;
            font-size: 14px; 
            font-weight: bold;
            width: 30px; 
            height: 30px;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            transition: background-color 0.3s ease, color 0.3s ease;
        }
        
        .header button svg {
            width: 16px;
            height: 16px;
        }
        
        .header-pranzo button {
            background: rgba(255, 255, 255, 0.2);
            color: white;
        }
        .header-cena button {
            background: rgba(0, 0, 0, 0.1);
            color: #1c1c1e;
        }
        .header button:disabled {
            opacity: 0.3;
        }
        
        .header-center {
            display: flex;
            flex-direction: column;
            align-items: center;
            flex-grow: 1;
            cursor: pointer;
            padding: 0 4px; 
        }
        .header-top {
            font-size: 1.1rem; 
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 2px;
        }
        .header h1 {
            margin: 0;
            font-size: 0.8rem; 
            text-align: center;
            font-weight: 500;
        }
        
        .content-wrapper {
            position: relative;
            overflow: hidden; 
            border-radius: 10px;
        }
        
        .content {
            cursor: pointer;
            position: relative;
            z-index: 2; 
            background-color: #f2f2f7; 
            width: 100%;
            box-sizing: border-box;
        }
        
        .course-card {
            background: white;
            border-radius: 10px;
            padding: 8px 12px; 
            margin-bottom: 8px; 
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        .course-title {
            color: #007aff;
            background-color: #e6f4ff;
            font-size: 0.95rem; 
            margin-top: 0;
            margin-bottom: 6px; 
            padding: 6px 8px; 
            border-radius: 6px;
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.5px;
            text-align: center;
        }
        ul {
            list-style-type: none;
            padding: 0;
            margin: 0;
        }
        li {
            padding: 2px 0; 
            border-bottom: 1px solid #f2f2f7;
            position: relative;
            padding-left: 12px;
            line-height: 1.15; 
            font-size: 0.9rem; 
        }
        li:last-child {
            border-bottom: none;
        }
        li::before {
            content: "•";
            color: #007aff;
            font-weight: bold;
            position: absolute;
            left: 0;
            font-size: 1.1rem;
            top: 0px; 
        }
        .hidden {
            display: none !important;
        }

        .anim-next {
            animation: slideOverRight 1s cubic-bezier(0.25, 1, 0.5, 1) forwards;
        }
        .anim-prev {
            animation: slideOverLeft 1s cubic-bezier(0.25, 1, 0.5, 1) forwards;
        }
        .anim-lang {
            animation: dropDown 1s cubic-bezier(0.25, 1, 0.5, 1) forwards;
        }

        @keyframes slideOverRight {
            0% { transform: translateX(100%); box-shadow: -15px 0 20px rgba(0,0,0,0.1); }
            100% { transform: translateX(0); box-shadow: 0 0 0 rgba(0,0,0,0); }
        }
        @keyframes slideOverLeft {
            0% { transform: translateX(-100%); box-shadow: 15px 0 20px rgba(0,0,0,0.1); }
            100% { transform: translateX(0); box-shadow: 0 0 0 rgba(0,0,0,0); }
        }
        @keyframes dropDown {
            0% { transform: translateY(-100%); box-shadow: 0 15px 20px rgba(0,0,0,0.1); opacity: 1; }
            100% { transform: translateY(0); box-shadow: 0 0 0 rgba(0,0,0,0); opacity: 1; }
        }
    </style>
</head>
<body>

    <div class="app-container">
        <div class="header" id="main-header">
            <div class="header-side">
                <button id="btn-prev" onclick="navigate(-1, true)">&#9664;</button>
                <button id="btn-prev-fast" onclick="navigate(-1, false)">&lt;&lt;</button>
                <button id="btn-speak-left" onclick="speakMenu(event)" title="Ascolta Piatti in Grassetto">
                    <svg fill="currentColor" viewBox="0 0 16 16">
                        <path d="M11.536 14.01A8.47 8.47 0 0 0 14.026 8a8.47 8.47 0 0 0-2.49-6.01l-.708.707A7.48 7.48 0 0 1 13.025 8c0 2.071-.84 3.946-2.197 5.303l.708.707z"/>
                        <path d="M10.121 12.596A6.48 6.48 0 0 0 12.025 8a6.48 6.48 0 0 0-1.904-4.596l-.707.707A5.48 5.48 0 0 1 11.025 8a5.48 5.48 0 0 1-1.61 3.89l.706.706z"/>
                        <path d="M8.707 11.182A4.5 4.5 0 0 0 10.025 8a4.5 4.5 0 0 0-1.318-3.182L8 5.525A3.5 3.5 0 0 1 9.025 8 3.5 3.5 0 0 1 8 10.475l.707.707zM6.717 3.55A.5.5 0 0 1 7 4v8a.5.5 0 0 1-.812.39L3.825 10.5H1.5A.5.5 0 0 1 1 10V6a.5.5 0 0 1 .5-.5h2.325l2.363-1.89a.5.5 0 0 1 .529-.06z"/>
                    </svg>
                </button>
            </div>
            
            <div class="header-center" onclick="goToToday()" title="Torna a Oggi / Go to Today">
                <div class="header-top" id="meal-type">IMT - Menu</div>
                <h1 id="meal-date">Caricamento...</h1>
            </div>
            
            <div class="header-side">
                <button id="btn-speak-right" onclick="speakMenu(event)" title="Ascolta Piatti in Grassetto">
                    <svg fill="currentColor" viewBox="0 0 16 16">
                        <path d="M11.536 14.01A8.47 8.47 0 0 0 14.026 8a8.47 8.47 0 0 0-2.49-6.01l-.708.707A7.48 7.48 0 0 1 13.025 8c0 2.071-.84 3.946-2.197 5.303l.708.707z"/>
                        <path d="M10.121 12.596A6.48 6.48 0 0 0 12.025 8a6.48 6.48 0 0 0-1.904-4.596l-.707.707A5.48 5.48 0 0 1 11.025 8a5.48 5.48 0 0 1-1.61 3.89l.706.706z"/>
                        <path d="M8.707 11.182A4.5 4.5 0 0 0 10.025 8a4.5 4.5 0 0 0-1.318-3.182L8 5.525A3.5 3.5 0 0 1 9.025 8 3.5 3.5 0 0 1 8 10.475l.707.707zM6.717 3.55A.5.5 0 0 1 7 4v8a.5.5 0 0 1-.812.39L3.825 10.5H1.5A.5.5 0 0 1 1 10V6a.5.5 0 0 1 .5-.5h2.325l2.363-1.89a.5.5 0 0 1 .529-.06z"/>
                    </svg>
                </button>
                <button id="btn-next-fast" onclick="navigate(1, false)">&gt;&gt;</button>
                <button id="btn-next" onclick="navigate(1, true)">&#9654;</button>
            </div>
        </div>
        
        <div class="content-wrapper" id="content-wrapper">
            <div class="content" id="menu-content" onclick="toggleLanguage()" title="Clicca per cambiare lingua / Click to change language">
                <div class="course-card" id="card-primi">
                    <h2 class="course-title" id="title-primi">Primi</h2>
                    <ul id="list-primi"></ul>
                </div>
                
                <div class="course-card" id="card-secondi">
                    <h2 class="course-title" id="title-secondi">Secondi</h2>
                    <ul id="list-secondi"></ul>
                </div>
                
                <div class="course-card" id="card-contorno">
                    <h2 class="course-title" id="title-contorno">Contorni</h2>
                    <ul id="list-contorno"></ul>
                </div>
                
                <div class="course-card" id="card-frutta">
                    <h2 class="course-title" id="title-frutta">Frutta / Dessert</h2>
                    <ul id="list-frutta"></ul>
                </div>
            </div>
        </div>
    </div>

    <script>
        const menuData = __JSON_DATA__;
        let currentIndex = 0;
        let currentLang = 'it'; 
        let isAnimating = false; 

        let speakTimeout;
        let isSpeakingTimeout = false;

        if ('speechSynthesis' in window) {
            window.speechSynthesis.onvoiceschanged = function() {
                window.speechSynthesis.getVoices();
            };
        }

        function speakMenu(event) {
            event.stopPropagation(); 
            
            if (!('speechSynthesis' in window)) {
                alert(currentLang === 'it' ? "Sintesi vocale non supportata." : "Text-to-speech not supported.");
                return;
            }

            if (window.speechSynthesis.speaking || isSpeakingTimeout) {
                window.speechSynthesis.cancel();
                clearTimeout(speakTimeout);
                isSpeakingTimeout = false;
                return;
            }

            const meal = menuData[currentIndex];
            const isIt = currentLang === 'it';
            
            let chunksToRead = [];

            // 1. Blocco Intro (Saluto, Titolo e Data)
            const dateStr = isIt ? meal.date_it : meal.date_en;
            let mealNameIt = meal.type.toLowerCase() === 'pranzo' ? 'il pranzo' : 'la cena';
            let mealNameEn = meal.type.toLowerCase() === 'pranzo' ? 'lunch' : 'dinner';
            
            let introText = isIt ? 
                `Ciao, ecco ${mealNameIt} della IMT di oggi, ${dateStr}.` : 
                `Hello, here is the IMT ${mealNameEn} for today, ${dateStr}.`;
                
            chunksToRead.push({ text: introText, delay: 200 });
            
            // 2. Funzione per creare i blocchi dei menu uniti con 'e'
            function extractCardBoldTexts(cardId, translatedTitle) {
                const card = document.getElementById(cardId);
                if (card.classList.contains('hidden')) return;
                const boldElements = card.querySelectorAll('strong');
                if (boldElements.length === 0) return;
                
                let itemsArray = [];
                boldElements.forEach(el => {
                    itemsArray.push(el.innerText);
                });
                
                let conjunction = isIt ? " e " : " and ";
                let joinedText = itemsArray.join(conjunction);
                
                chunksToRead.push({ text: translatedTitle + ". " + joinedText + ".", delay: 200 });
            }
            
            extractCardBoldTexts('card-primi', isIt ? "Primi" : "First Courses");
            extractCardBoldTexts('card-secondi', isIt ? "Secondi" : "Main Courses");
            extractCardBoldTexts('card-contorno', isIt ? "Contorni" : "Side Dishes");
            extractCardBoldTexts('card-frutta', isIt ? "Frutta e Dessert" : "Fruit and Dessert");
            
            if (chunksToRead.length === 1) { 
                chunksToRead.push({ text: isIt ? "Nessun piatto in grassetto da leggere." : "No bold items to read.", delay: 200 });
            }

            // 3. Saluto Finale
            let closingTextIt = meal.type.toLowerCase() === 'pranzo' ? "Buon pranzo!" : "Buona cena!";
            let closingTextEn = meal.type.toLowerCase() === 'pranzo' ? "Enjoy your lunch!" : "Enjoy your dinner!";
            chunksToRead.push({ text: isIt ? closingTextIt : closingTextEn, delay: 0 });

            const langCode = isIt ? 'it-IT' : 'en-US';
            const voices = window.speechSynthesis.getVoices();
            let bestVoice = voices.find(v => v.lang.replace('_', '-') === langCode && 
                                       (v.name.includes('Google') || v.name.includes('Premium') || v.name.includes('Natural') || v.name.includes('Alice')));
            if (!bestVoice) {
                bestVoice = voices.find(v => v.lang.replace('_', '-').startsWith(langCode.split('-')[0]));
            }

            let chunkIndex = 0;
            
            function playNextChunk() {
                if (chunkIndex >= chunksToRead.length) {
                    isSpeakingTimeout = false;
                    return;
                }
                
                let currentChunk = chunksToRead[chunkIndex];
                const utterance = new SpeechSynthesisUtterance(currentChunk.text);
                
                if (bestVoice) utterance.voice = bestVoice;
                else utterance.lang = langCode;
                utterance.rate = 0.9; 
                
                utterance.onend = function() {
                    chunkIndex++;
                    if (chunkIndex < chunksToRead.length) {
                        isSpeakingTimeout = true;
                        speakTimeout = setTimeout(playNextChunk, currentChunk.delay); 
                    } else {
                        isSpeakingTimeout = false;
                    }
                };
                
                utterance.onerror = function(e) {
                    isSpeakingTimeout = false;
                };
                
                window.speechSynthesis.speak(utterance);
            }
            
            playNextChunk();
        }

        function toggleLanguage() {
            if (isAnimating) return; 
            currentLang = currentLang === 'it' ? 'en' : 'it';
            renderMeal(currentIndex, 'lang');
        }

        function renderMeal(index, animType) {
            if (!menuData || menuData.length === 0) {
                document.getElementById('meal-date').innerText = currentLang === 'it' ? "Nessun menu" : "No menu";
                return;
            }
            
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
                clone.style.position = 'absolute';
                clone.style.top = '0';
                clone.style.left = '0';
                clone.style.width = '100%';
                clone.style.zIndex = '1'; 
                clone.style.animation = 'none'; 
                clone.style.transform = 'none';
                clone.style.pointerEvents = 'none'; 
                
                contentWrapper.appendChild(clone);
                
                setTimeout(() => {
                    if (clone.parentNode) clone.parentNode.removeChild(clone);
                    isAnimating = false;
                }, 1000); 
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
            if (meal.type.toLowerCase() === 'pranzo') {
                header.className = 'header header-pranzo';
            } else {
                header.className = 'header header-cena';
            }

            const updateList = (id, items_it, items_en) => {
                const card = document.getElementById('card-' + id);
                const ul = document.getElementById('list-' + id);
                const items = isIt ? items_it : items_en;
                if (items && items.length > 0) {
                    ul.innerHTML = items.map(i => `<li>${i}</li>`).join('');
                    card.classList.remove('hidden');
                } else {
                    card.classList.add('hidden');
                }
            };

            updateList('primi', meal.Primi_it, meal.Primi_en);
            updateList('secondi', meal.Secondi_it, meal.Secondi_en);
            updateList('contorno', meal.Contorno_it, meal.Contorno_en);
            updateList('frutta', meal.Frutta_it, meal.Frutta_en);

            document.getElementById('btn-prev').disabled = (currentIndex === 0);
            document.getElementById('btn-prev-fast').disabled = (currentIndex === 0);
            document.getElementById('btn-next').disabled = (currentIndex === menuData.length - 1);
            document.getElementById('btn-next-fast').disabled = (currentIndex === menuData.length - 1);

            contentDiv.classList.remove('anim-next', 'anim-prev', 'anim-lang');
            void contentDiv.offsetWidth; 
            if (animType) {
                contentDiv.classList.add('anim-' + animType);
            }
        }

        function navigate(direction, animated = true) {
            if (isAnimating && animated) return;
            const newIndex = currentIndex + direction;
            if (newIndex >= 0 && newIndex < menuData.length) {
                let animType = null;
                if (animated) {
                    animType = direction > 0 ? 'next' : 'prev';
                }
                renderMeal(newIndex, animType);
            }
        }
        
        function goToToday() {
            if (isAnimating) return;
            const index = getInitialMealIndex();
            if (index !== currentIndex) {
                renderMeal(index, 'lang');
            }
        }

        window.addEventListener('keydown', function(e) {
            if (e.key === 'ArrowLeft') {
                document.getElementById('btn-prev').click();
            } else if (e.key === 'ArrowRight') {
                document.getElementById('btn-next').click();
            }
        });

        let touchstartX = 0;
        let touchstartY = 0;
        let touchendX = 0;
        let touchendY = 0;

        const thresholdX = 50; 
        const thresholdY = 60; 

        document.addEventListener('touchstart', e => {
            touchstartX = e.changedTouches[0].screenX;
            touchstartY = e.changedTouches[0].screenY;
        }, { passive: true });

        document.addEventListener('touchend', e => {
            if (isAnimating) return;
            touchendX = e.changedTouches[0].screenX;
            touchendY = e.changedTouches[0].screenY;
            
            const diffX = touchendX - touchstartX;
            const diffY = Math.abs(touchendY - touchstartY);

            if (diffY < thresholdY) {
                if (diffX <= -thresholdX) {
                    if(!document.getElementById('btn-next').disabled) {
                        document.getElementById('btn-next').click();
                    }
                } else if (diffX >= thresholdX) {
                    if(!document.getElementById('btn-prev').disabled) {
                        document.getElementById('btn-prev').click();
                    }
                }
            }
        }, { passive: true });

        function getInitialMealIndex() {
            if (!menuData || menuData.length === 0) return 0;
            
            const now = new Date();
            const year = now.getFullYear();
            const month = String(now.getMonth() + 1).padStart(2, '0');
            const day = String(now.getDate()).padStart(2, '0');
            const currentDateString = `${year}-${month}-${day}`;
            
            const currentHour = now.getHours();
            const currentMinutes = now.getMinutes();
            let targetType = "Pranzo";
            if (currentHour > 15 || (currentHour === 15 && currentMinutes > 0)) {
                targetType = "Cena";
            }

            let foundIndex = menuData.findIndex(m => m.date === currentDateString && m.type.toLowerCase() === targetType.toLowerCase());
            
            if (foundIndex === -1) {
                foundIndex = menuData.findIndex(m => m.date === currentDateString);
            }
            if (foundIndex === -1) {
                foundIndex = menuData.findIndex(m => m.date > currentDateString);
            }
            if (foundIndex === -1) {
                foundIndex = menuData.length - 1;
            }
            
            return Math.max(0, foundIndex);
        }

        window.onload = () => {
            currentIndex = getInitialMealIndex();
            renderMeal(currentIndex, null);
        };
    </script>
</body>
</html>
"""

    html_code = html_template.replace('__JSON_DATA__', json.dumps(blocks))

    with open(file_output, 'w', encoding='utf-8') as f:
        f.write(html_code)

    print(f"File {file_output} generato con successo! Sincronizzazione vocale raffinata applicata.")

if __name__ == "__main__":
    genera_html()