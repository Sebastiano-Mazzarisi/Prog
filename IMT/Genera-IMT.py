# Nome.py: GeneraMenu.py
# Data e ora ultima modifica: 07/09/2026 09:30
# Descrizione: Legge menu-giornaliero-completo-estate-2026.xlsx e genera Menu-IMT.html.
#              Aggiunte le animazioni CSS per il cambio pagina (scorrimento orizzontale) e 
#              per il cambio lingua (discesa dall'alto).
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

        display_title_it = f"{pasto_val.upper()}: {formatted_date_it}"
        display_title_en = f"{'LUNCH' if pasto_val.lower() == 'pranzo' else 'DINNER'}: {formatted_date_en}"
            
        block = {
            'type': pasto_val,
            'date': iso_date,
            'displayTitle_it': display_title_it,
            'displayTitle_en': display_title_en,
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
            padding: 8px 10px;
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
        
        .header button {
            border: none;
            font-size: 18px;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            transition: background-color 0.3s ease, color 0.3s ease;
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
        }
        .header-top {
            font-size: 1.3rem; 
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 2px;
        }
        .header h1 {
            margin: 0;
            font-size: 0.85rem; 
            text-align: center;
            font-weight: 500;
        }
        .content {
            cursor: pointer;
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

        /* --- ANIMAZIONI CSS --- */
        .anim-next {
            animation: slideInRight 0.3s ease-out forwards;
        }
        .anim-prev {
            animation: slideInLeft 0.3s ease-out forwards;
        }
        .anim-lang {
            animation: dropDown 0.4s cubic-bezier(0.25, 1, 0.5, 1) forwards;
        }

        @keyframes slideInRight {
            0% { transform: translateX(100%); opacity: 0; }
            100% { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideInLeft {
            0% { transform: translateX(-100%); opacity: 0; }
            100% { transform: translateX(0); opacity: 1; }
        }
        @keyframes dropDown {
            0% { transform: translateY(-30px); opacity: 0; }
            100% { transform: translateY(0); opacity: 1; }
        }
    </style>
</head>
<body>

    <div class="app-container">
        <div class="header" id="main-header">
            <button id="btn-prev" onclick="navigate(-1)">&#9664;</button>
            <div class="header-center" onclick="goToToday()" title="Torna a Oggi / Go to Today">
                <div class="header-top">IMT - Menu</div>
                <h1 id="meal-title">Caricamento...</h1>
            </div>
            <button id="btn-next" onclick="navigate(1)">&#9654;</button>
        </div>
        
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

    <script>
        const menuData = __JSON_DATA__;
        let currentIndex = 0;
        let currentLang = 'it'; 

        function toggleLanguage() {
            currentLang = currentLang === 'it' ? 'en' : 'it';
            renderMeal(currentIndex, 'lang');
        }

        // Aggiunto il parametro animType per gestire le animazioni ('next', 'prev', 'lang')
        function renderMeal(index, animType) {
            if (!menuData || menuData.length === 0) {
                document.getElementById('meal-title').innerText = currentLang === 'it' ? "Nessun menu disponibile" : "No menu available";
                return;
            }
            
            currentIndex = index;
            const meal = menuData[currentIndex];
            const isIt = currentLang === 'it';
            
            // Gestione animazione del contenitore
            const contentDiv = document.getElementById('menu-content');
            contentDiv.classList.remove('anim-next', 'anim-prev', 'anim-lang');
            // Questo comando forza il browser a resettare l'animazione precedente
            void contentDiv.offsetWidth; 
            if (animType) {
                contentDiv.classList.add('anim-' + animType);
            }

            document.getElementById('meal-title').innerText = isIt ? meal.displayTitle_it : meal.displayTitle_en;
            
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
            document.getElementById('btn-next').disabled = (currentIndex === menuData.length - 1);
        }

        function navigate(direction) {
            const newIndex = currentIndex + direction;
            if (newIndex >= 0 && newIndex < menuData.length) {
                // Passa 'next' o 'prev' a seconda della direzione per avviare l'animazione corretta
                renderMeal(newIndex, direction > 0 ? 'next' : 'prev');
            }
        }
        
        function goToToday() {
            const index = getInitialMealIndex();
            // Per il ritorno a "Oggi", l'animazione a discesa è l'effetto visivo migliore
            renderMeal(index, 'lang'); 
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
            // Al primo caricamento nessuna animazione
            renderMeal(currentIndex); 
        };
    </script>
</body>
</html>
"""

    html_code = html_template.replace('__JSON_DATA__', json.dumps(blocks))

    with open(file_output, 'w', encoding='utf-8') as f:
        f.write(html_code)

    print(f"File {file_output} generato con successo! Animazioni di transizione (swipe e lingua) attivate.")

if __name__ == "__main__":
    genera_html()