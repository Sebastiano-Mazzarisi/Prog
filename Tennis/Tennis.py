# Tennis.py
# Genera Tennis.html con i dati aggiornati e lo pusha su GitHub Pages.
# Viene lanciato automaticamente ogni 30 minuti da Lanciatore.py.
# Su iPhone: apri il link GitHub Pages e aggiungi a Home (icona pallina 🎾).
#
# Configurazione in Lanciatore.txt:
# [Tennis]
# comando        = python.exe "C:\Dropbox\Prog\Tennis\Tennis.py"
# cartella       = C:\Dropbox\Prog\Tennis
# intervallo_min = 30
# prima_esec     = si
# silenzioso     = si
# attivo         = si

import subprocess, os, json, base64, webbrowser
from datetime import datetime

DIR     = os.path.dirname(os.path.abspath(__file__))
F_HTML  = os.path.join(DIR, "Tennis.html")
F_TXT   = os.path.join(DIR, "Tennis.txt")
F_ICON  = os.path.join(DIR, "tennis_icon.png")

ORA_AGG   = datetime.now().strftime("%H:%M del %d/%m/%Y")
DATA_FINE = "17/05/2026"

# ── DATI — aggiornati da Claude su richiesta ──────────────────────────────────
# stato: "live" | "next" | "ok" | "elim"
DATA = [
  {
    "nome": "SINNER", "stato": "next",
    "live": None,
    "prossimo": {"orario": "non prima delle 19:00", "data": "09/05", "avv": "OFNER"},
    "storico": [],
  },
  {
    "nome": "COCCIARETTO", "stato": "next",
    "live": None,
    "prossimo": {"orario": "da definire", "data": "09/05", "avv": "SWIATEK"},
    "storico": [
      {"data": "08/05", "esito": "W", "avv": "NAVARRO",  "score": "6-3 6-3"},
      {"data": "06/05", "esito": "W", "avv": "KRAUS",    "score": "6-2 6-4"},
    ],
  },
  {
    "nome": "PAOLINI", "stato": "next",
    "live": None,
    "prossimo": {"orario": "da definire", "data": "09/05", "avv": "MERTENS"},
    "storico": [
      {"data": "07/05", "esito": "W", "avv": "JEANJEAN", "score": "6-7 6-2 6-4"},
    ],
  },
  {
    "nome": "ARNALDI", "stato": "next",
    "live": None,
    "prossimo": {"orario": "da definire", "data": "09/05", "avv": "JODAR"},
    "storico": [
      {"data": "08/05", "esito": "W", "avv": "DE MINAUR", "score": "4-6 7-6 6-4"},
      {"data": "06/05", "esito": "W", "avv": "MUNAR",     "score": "6-3 3-6 6-3"},
    ],
  },
  {
    "nome": "COBOLLI", "stato": "next",
    "live": None,
    "prossimo": {"orario": "da definire", "data": "09/05", "avv": "ATMANE"},
    "storico": [],
  },
  {
    "nome": "BELLUCCI", "stato": "next",
    "live": None,
    "prossimo": {"orario": "da definire", "data": "09/05", "avv": "ETCHEVERRY"},
    "storico": [
      {"data": "07/05", "esito": "W", "avv": "BURRUCHAGA", "score": "6-4 6-4"},
    ],
  },
  {
    "nome": "PELLEGRINO", "stato": "next",
    "live": None,
    "prossimo": {"orario": "da definire", "data": "09/05", "avv": "FILS"},
    "storico": [
      {"data": "07/05", "esito": "W", "avv": "NARDI", "score": "4-6 6-3 6-3"},
    ],
  },
  {
    "nome": "MUSETTI", "stato": "ok",
    "live": None,
    "prossimo": {"orario": "da definire", "data": "10/05", "avv": "CERUNDOLO"},
    "storico": [
      {"data": "08/05", "esito": "W", "avv": "MPETSHI PERRICARD", "score": "6-4 6-4"},
    ],
  },
  {
    "nome": "DARDERI", "stato": "ok",
    "live": None,
    "prossimo": {"orario": "da definire", "data": "10/05", "avv": "PAUL"},
    "storico": [
      {"data": "08/05", "esito": "W", "avv": "HANFMANN", "score": "6-4 6-4"},
    ],
  },
  {
    "nome": "BERRETTINI", "stato": "elim", "live": None, "prossimo": None,
    "storico": [{"data": "07/05", "esito": "L", "avv": "POPYRIN", "score": "2-6 3-6"}],
  },
  {
    "nome": "SONEGO", "stato": "elim", "live": None, "prossimo": None,
    "storico": [{"data": "07/05", "esito": "L", "avv": "BUSE", "score": "3-6 3-6"}],
  },
  {
    "nome": "GRANT", "stato": "elim", "live": None, "prossimo": None,
    "storico": [{"data": "08/05", "esito": "L", "avv": "BARTUNKOVA", "score": "6-4 3-6 4-6"}],
  },
  {
    "nome": "BASILETTI", "stato": "elim", "live": None, "prossimo": None,
    "storico": [{"data": "08/05", "esito": "L", "avv": "SVITOLINA", "score": "1-6 3-6"}],
  },
]
# ─────────────────────────────────────────────────────────────────────────────

ICON_B64 = ""
if os.path.exists(F_ICON):
    with open(F_ICON, "rb") as f:
        ICON_B64 = base64.b64encode(f.read()).decode()

def genera_html():
    data_json = json.dumps(DATA, ensure_ascii=False)
    icon_tag  = f'<link rel="apple-touch-icon" href="data:image/png;base64,{ICON_B64}">' if ICON_B64 else ""
    return """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Tennis Roma">
""" + icon_tag + """
<title>🎾 Tennis Roma</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Barlow+Condensed:wght@400;600;700;800&display=swap');
  :root{--clay:#C1440E;--clay2:#E8622A;--dark:#111009;--card:#1A1814;--line:#2E2B24;--text:#F0EBE0;--muted:#7A7060;--win:#5DBB7A;--lose:#E05555;--next:#F0C040}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--dark);color:var(--text);font-family:'Barlow Condensed',sans-serif;min-height:100vh;padding-bottom:40px}
  .header{background:linear-gradient(135deg,var(--clay) 0%,var(--clay2) 60%,#F07840 100%);padding:20px 16px 16px;position:relative;overflow:hidden}
  .header::before{content:'';position:absolute;top:-30px;right:-30px;width:140px;height:140px;border-radius:50%;background:rgba(255,255,255,0.07)}
  .header::after{content:'🎾';position:absolute;font-size:80px;right:8px;top:-10px;opacity:0.18;transform:rotate(20deg)}
  .header h1{font-size:28px;font-weight:800;letter-spacing:.02em;text-transform:uppercase;line-height:1;text-shadow:0 2px 8px rgba(0,0,0,.3)}
  .header .subtitle{font-size:14px;opacity:.85;margin-top:4px;font-family:'DM Mono',monospace}
  .header .finale{display:inline-block;margin-top:8px;background:rgba(0,0,0,.25);border-radius:4px;padding:3px 10px;font-size:12px;font-family:'DM Mono',monospace}
  .agg{background:var(--card);border-bottom:1px solid var(--line);padding:8px 16px;font-size:11px;font-family:'DM Mono',monospace;color:var(--muted);display:flex;align-items:center;gap:6px}
  .dot{width:6px;height:6px;border-radius:50%;background:var(--win);animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
  .section-label{padding:14px 16px 6px;font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--clay2);font-family:'DM Mono',monospace}
  .card{margin:0 12px 8px;background:var(--card);border-radius:10px;border:1px solid var(--line);overflow:hidden}
  .card.live{border-color:var(--clay2);box-shadow:0 0 0 1px var(--clay2),0 4px 20px rgba(194,68,14,.2)}
  .card.eliminato{opacity:.45;border-color:#222}
  .card-head{display:flex;align-items:center;justify-content:space-between;padding:10px 14px 8px;border-bottom:1px solid var(--line)}
  .nome{font-size:22px;font-weight:800;letter-spacing:.03em;text-transform:uppercase}
  .badge{font-size:10px;font-weight:700;letter-spacing:.08em;padding:3px 8px;border-radius:20px;text-transform:uppercase;font-family:'DM Mono',monospace}
  .badge.live{background:var(--clay);color:#fff;animation:pulse 1.5s infinite}
  .badge.next{background:rgba(240,192,64,.15);color:var(--next);border:1px solid rgba(240,192,64,.3)}
  .badge.elim{background:rgba(224,85,85,.1);color:var(--lose);border:1px solid rgba(224,85,85,.2)}
  .badge.ok{background:rgba(93,187,122,.1);color:var(--win);border:1px solid rgba(93,187,122,.2)}
  .card-body{padding:10px 14px 12px}
  .match-row{display:flex;align-items:baseline;gap:8px;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.04)}
  .match-row:last-child{border-bottom:none}
  .match-date{color:var(--muted);font-family:'DM Mono',monospace;font-size:12px;min-width:38px}
  .match-esito{font-size:16px;min-width:18px}
  .match-avv{flex:1;font-weight:600;font-size:15px}
  .match-score{color:var(--muted);font-family:'DM Mono',monospace;font-size:12px}
  .prossimo{margin-top:8px;background:rgba(240,192,64,.07);border-radius:6px;padding:8px 10px;border-left:3px solid var(--next)}
  .prossimo .vs{font-size:17px;font-weight:700}
  .prossimo .orario{font-family:'DM Mono',monospace;font-size:12px;color:var(--next);margin-top:2px}
  .live-score{margin-top:8px;background:rgba(194,68,14,.1);border-radius:6px;padding:8px 10px;border-left:3px solid var(--clay2)}
  .live-score .vs{font-size:17px;font-weight:700}
  .live-score .score{font-family:'DM Mono',monospace;font-size:20px;font-weight:500;color:var(--clay2);margin-top:2px}
  .install-bar{background:#1A1814;border:1px solid #2E2B24;border-radius:10px;margin:12px;padding:12px 14px;display:flex;align-items:center;gap:10px}
  .install-bar span{flex:1;color:#7A7060;font-size:13px;line-height:1.4}
  .install-bar strong{color:#F0EBE0}
</style>
</head>
<body>
<div class="header">
  <h1>Internazionali d'Italia</h1>
  <div class="subtitle">Roma 2026 — Italiani</div>
  <div class="finale">Finale: """ + DATA_FINE + """</div>
</div>
<div class="agg"><div class="dot"></div><span>aggiornato alle """ + ORA_AGG + """</span></div>
<div class="install-bar" id="ibar">
  <span>📲 <strong>iPhone:</strong> tocca Condividi → "Aggiungi a Home" per l'icona 🎾</span>
  <button onclick="document.getElementById('ibar').style.display='none'"
    style="background:none;border:none;color:#7A7060;font-size:20px;cursor:pointer;padding:0">✕</button>
</div>
<div id="container"></div>
<script>
const DATA=""" + data_json + """;
function renderCard(g){
  const isLive=g.stato==="live",isElim=g.stato==="elim";
  let badge="";
  if(isLive)badge='<span class="badge live">● LIVE</span>';
  else if(isElim)badge='<span class="badge elim">ELIMINATO</span>';
  else if(g.prossimo)badge='<span class="badge next">PROSSIMO: '+g.prossimo.data+'</span>';
  else badge='<span class="badge ok">✓ AVANZA</span>';
  let body="";
  if(isLive&&g.live)body+='<div class="live-score"><div class="vs">vs '+g.live.avv+'</div><div class="score">'+g.live.score+'</div></div>';
  (g.storico||[]).forEach(m=>{
    const sym=m.esito==="W"?"✓":"✗",col=m.esito==="W"?"var(--win)":"var(--lose)";
    body+='<div class="match-row"><span class="match-date">'+m.data+'</span><span class="match-esito" style="color:'+col+'">'+sym+'</span><span class="match-avv">'+m.avv+'</span><span class="match-score">'+m.score+'</span></div>';
  });
  if(g.prossimo&&!isElim)body+='<div class="prossimo"><div class="vs">vs '+g.prossimo.avv+'</div><div class="orario">'+g.prossimo.orario+' · '+g.prossimo.data+'</div></div>';
  if(!body)body='<div style="font-size:14px;color:var(--lose);font-family:DM Mono,monospace;padding:4px 0">Eliminato</div>';
  return '<div class="card'+(isLive?' live':'')+(isElim?' eliminato':'')+'"><div class="card-head"><div class="nome">'+g.nome+'</div>'+badge+'</div><div class="card-body">'+body+'</div></div>';
}
function render(){
  const groups=[["● In corso","live"],["Oggi in campo","next"],["Avanzano — prossimo turno","ok"],["Eliminati","elim"]];
  let html="";
  groups.forEach(([label,stato])=>{
    const items=DATA.filter(g=>g.stato===stato);
    if(items.length){html+='<div class="section-label">'+label+'</div>';items.forEach(g=>html+=renderCard(g));}
  });
  document.getElementById("container").innerHTML=html;
}
render();
</script>
</body>
</html>"""

def genera_txt():
    righe = ["-"*40, "Internazionali d'Italia - Roma", f"Finale: {DATA_FINE}", "-"*40]
    for g in DATA:
        if g["stato"] == "elim":
            continue
        if g.get("live"):
            righe += [f"{g['nome']} - {g['live']['avv']}", f">>> IN CORSO  {g['live']['score']}"]
        elif g.get("prossimo"):
            righe += [f"{g['nome']} - {g['prossimo']['avv']}", f"{g['prossimo']['orario']} - {g['prossimo']['data']}"]
        for m in (g.get("storico") or []):
            righe.append(f"  {m['data']}  {'V' if m['esito']=='W' else 'X'}  {m['avv']}  {m['score']}")
        righe.append("-"*40)
    righe += ["Dati aggiornati alle ore", ORA_AGG]
    return "\n".join(righe)

def trova_git():
    import shutil
    git = shutil.which("git")
    if git:
        return git
    candidati = [
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
        os.path.join(os.environ.get("LOCALAPPDATA",""), "Programs", "Git", "bin", "git.exe"),
    ]
    for c in candidati:
        if os.path.exists(c):
            return c
    return None

def git_push():
    git = trova_git()
    if not git:
        return
    try:
        cmds = [
            f'"{git}" -C "{DIR}" add Tennis.html Tennis.txt',
            f'"{git}" -C "{DIR}" commit -m "Tennis: aggiorna {ORA_AGG}"',
            f'"{git}" -C "{DIR}" push',
        ]
        for cmd in cmds:
            subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError:
        pass

def main():
    with open(F_HTML, "w", encoding="utf-8") as f:
        f.write(genera_html())
    with open(F_TXT, "w", encoding="utf-8") as f:
        f.write(genera_txt() + "\n")
    git_push()
    # Apre nel browser solo se lanciato manualmente (non da Lanciatore)
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--apri":
        import webbrowser
        webbrowser.open(f"file:///{F_HTML.replace(os.sep, '/')}")

if __name__ == "__main__":
    main()
