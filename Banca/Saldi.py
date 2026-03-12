#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Saldi.py
Legge Saldi.txt e genera Saldi.html con dashboard saldi bancari.
Genera anche Saldi.pdf e aggiunge nell'HTML un bottone
per aprire WhatsApp con il riepilogo saldi precompilato.

Formato Saldi.txt:
    Minimo: € 0
    Massimo: € 30.000
    Rosso: € 5.000
    Giallo: € 10.000

    Data: 08/03/26
    Nino: € 10.753; Interessi bancari
    Marica: € 4.834; Stipendio Marica
"""

import os
import sys
import re
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
# Testo copiato nel buffer con il bottone "Copia"
# (generato dinamicamente in genera_html, questa variabile non serve più)

# ── CONFIG GITHUB ─────────────────────────────────────────────────────────────
# Il token viene letto da Saldi.cfg (stesso percorso di questo script)
# così non viene perso quando si aggiorna Saldi.py
# Formato di Saldi.cfg (file di testo, una riga):
#   ghp_xxxxxxxxxxxxxxxxxxxx
GH_REPO   = "Sebastiano-Mazzarisi/Prog"
GH_FOLDER = "Banca"

# ── Percorsi (stessa cartella dello script) ───────────────────────────────────
BASE      = os.path.dirname(os.path.abspath(__file__))
FILE_TXT  = os.path.join(BASE, "Saldi.txt")
FILE_HTML = os.path.join(BASE, "Saldi.html")
FILE_PDF  = os.path.join(BASE, "Saldi.pdf")

def _leggi_token():
    cfg = os.path.join(BASE, "Saldi.cfg")
    if os.path.exists(cfg):
        token = open(cfg, encoding="utf-8").read().strip()
        if token:
            return token
    return ""

GH_TOKEN = _leggi_token()


# ── Lettura Saldi.txt ─────────────────────────────────────────────────────────
def leggi_txt(path):
    with open(path, encoding="utf-8") as f:
        testo = f.read()

    def leggi_euro(pattern):
        m = re.search(pattern, testo)
        return int(m.group(1).replace(".", "")) if m else None

    minimo  = leggi_euro(r"Minimo:\s*€\s*([\d.]+)")
    massimo = leggi_euro(r"Massimo:\s*€\s*([\d.]+)")
    rosso   = leggi_euro(r"Rosso:\s*€\s*([\d.]+)")
    giallo  = leggi_euro(r"Giallo:\s*€\s*([\d.]+)")

    if minimo is None:  minimo  = 0
    if massimo is None: massimo = 30000
    if rosso is None:   rosso   = int(massimo * 0.1667)
    if giallo is None:  giallo  = int(massimo * 0.3333)

    righe = []
    blocchi = re.split(r"\n(?=Data:)", testo)
    for b in blocchi:
        b = b.strip()
        if not b.startswith("Data:"):
            continue
        d = re.search(r"Data:\s*(\S+)", b)
        n = re.search(r"Nino:\s*€\s*([\d.]+)(?:;\s*(.+))?", b)
        m = re.search(r"Marica:\s*€\s*([\d.]+)(?:;\s*(.+))?", b)
        if not (d and n and m):
            continue
        righe.append({
            "data":        d.group(1),
            "nino":        int(n.group(1).replace(".", "")),
            "nota_nino":   n.group(2).strip() if n.group(2) else "",
            "marica":      int(m.group(1).replace(".", "")),
            "nota_marica": m.group(2).strip() if m.group(2) else "",
        })

    return minimo, massimo, rosso, giallo, righe


# ── Formattazione numero italiano ─────────────────────────────────────────────
def fmt(n):
    return f"€ {n:,.0f}".replace(",", ".")


# ── Zona gauge ────────────────────────────────────────────────────────────────
def colore_zona(totale, rosso, giallo):
    if totale < rosso:    return "ROSSO"
    elif totale < giallo: return "GIALLO"
    else:                 return "VERDE"


# ── Genera PDF riepilogativo ───────────────────────────────────────────────────
def genera_pdf(minimo, massimo, rosso, giallo, righe, output_path):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as rl_canvas
    except ImportError:
        print("⚠  reportlab non trovato. Installa con: pip install reportlab")
        return False

    W, H = A4
    c = rl_canvas.Canvas(output_path, pagesize=A4)

    primo      = righe[0]
    nino_val   = primo["nino"]
    marica_val = primo["marica"]
    totale_val = nino_val + marica_val
    data_agg   = data_lunga(primo["data"])
    zona       = colore_zona(totale_val, rosso, giallo)

    NERO        = colors.HexColor("#1a1a1a")
    GRIGIO_BG   = colors.HexColor("#cccccc")
    COL_R       = colors.HexColor("#d32f2f")
    COL_Y       = colors.HexColor("#e65100")
    COL_G       = colors.HexColor("#2e7d32")
    COL_GAUGE_R = colors.HexColor("#ef9a9a")
    COL_GAUGE_Y = colors.HexColor("#ffcc80")
    COL_GAUGE_G = colors.HexColor("#a5d6a7")
    col_totale  = {"ROSSO": COL_R, "GIALLO": COL_Y, "VERDE": COL_G}[zona]

    margin = 18*mm
    tw     = W - 2*margin

    # ── Intestazione
    c.setFillColor(NERO); c.setFont("Helvetica-Bold", 15)
    c.drawString(margin, H - 22*mm, "Situazione Saldi")
    c.setFillColor(NERO); c.setFont("Helvetica", 9)
    c.drawRightString(W - margin, H - 22*mm, f"Aggiornamento: {data_agg}")
    c.setStrokeColor(NERO); c.setLineWidth(0.4)
    c.line(margin, H - 24.5*mm, W - margin, H - 24.5*mm)

    # ── Card Nino / Marica
    gap = 5*mm
    cw  = (tw - gap) / 2
    ch  = 13*mm
    cy  = H - 43*mm

    def disegna_card(x, y, w, h, nome, valore):
        c.setFillColor(GRIGIO_BG)
        c.setStrokeColor(NERO); c.setLineWidth(0.5)
        c.roundRect(x, y, w, h, 5, fill=1, stroke=1)
        c.setFillColor(NERO); c.setFont("Helvetica", 7)
        c.drawString(x + 4*mm, y + h - 4*mm, nome.upper())
        c.setFillColor(NERO); c.setFont("Helvetica-Bold", 15)
        c.drawCentredString(x + w/2, y + h/2 - 2.5*mm, valore)

    disegna_card(margin,        cy, cw, ch, "Nino",   fmt(nino_val))
    disegna_card(margin+cw+gap, cy, cw, ch, "Marica", fmt(marica_val))

    # ── Card Totale con gauge interno
    tot_h = 30*mm
    tot_y = cy - 5*mm - tot_h

    c.setFillColor(colors.white)
    c.setStrokeColor(col_totale); c.setLineWidth(1.5)
    c.roundRect(margin, tot_y, tw, tot_h, 5, fill=1, stroke=1)

    c.setFillColor(NERO); c.setFont("Helvetica", 7.5)
    c.drawString(margin + 4*mm, tot_y + tot_h - 5*mm, "TOTALE")

    # Solo il numero grande è colorato
    c.setFillColor(col_totale); c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(W/2, tot_y + tot_h - 13*mm, fmt(totale_val))

    # ── Gauge doppia altezza con griglie verticali nere
    bx = margin + 6*mm
    bw = tw - 12*mm
    bh = 14
    gy = tot_y + 8*mm

    def pct(v):
        return max(0.0, min(1.0, (v - minimo) / (massimo - minimo)))

    pr = pct(rosso); pg = pct(giallo); pt = pct(totale_val)

    c.setFillColor(colors.HexColor("#eeeeee"))
    c.roundRect(bx, gy, bw, bh, 3, fill=1, stroke=0)
    c.setFillColor(COL_GAUGE_R)
    c.rect(bx, gy, bw*pr, bh, fill=1, stroke=0)
    c.setFillColor(COL_GAUGE_Y)
    c.rect(bx+bw*pr, gy, bw*(pg-pr), bh, fill=1, stroke=0)
    c.setFillColor(COL_GAUGE_G)
    c.rect(bx+bw*pg, gy, bw*(1-pg), bh, fill=1, stroke=0)

    # Griglie verticali nere ai confini tra colori
    c.setStrokeColor(NERO); c.setLineWidth(0.4)
    for p in [pr, pg]:
        lx = bx + bw*p
        c.line(lx, gy, lx, gy + bh)

    # Bordo esterno nero
    c.setStrokeColor(NERO); c.setLineWidth(0.4)
    c.roundRect(bx, gy, bw, bh, 3, fill=0, stroke=1)

    # Freccia indicatore nera
    ax = bx + bw*pt
    ay = gy + bh + 1
    c.setFillColor(NERO)
    path = c.beginPath()
    path.moveTo(ax, ay+6); path.lineTo(ax-4, ay+12); path.lineTo(ax+4, ay+12)
    path.close(); c.drawPath(path, fill=1, stroke=0)

    # Tick labels in nero
    tick_labels = {
        minimo:  "€ 0",
        rosso:   f"{rosso:,.0f} €".replace(",", "."),
        giallo:  f"{giallo:,.0f} €".replace(",", "."),
        massimo: f"{massimo:,.0f} €".replace(",", "."),
    }
    c.setFillColor(NERO); c.setFont("Helvetica", 6.5)
    for p, v in [(0, minimo), (pr, rosso), (pg, giallo), (1.0, massimo)]:
        lx = bx + bw*p
        c.drawCentredString(lx, gy - 4.5*mm, tick_labels[v])
        c.setStrokeColor(NERO); c.setLineWidth(0.3)
        c.line(lx, gy - 0.5, lx, gy)

    # ── Tabella storico
    tab_top = tot_y - 8*mm
    col_w   = [25*mm, 30*mm, 30*mm, 30*mm, tw - 115*mm]
    headers = ["Data", "Nino", "Marica", "Totale", "Note"]
    aligns  = ["L", "R", "R", "R", "L"]
    row_h   = 7*mm
    head_h  = 8*mm

    c.setFillColor(colors.HexColor("#cccccc")); c.setStrokeColor(NERO); c.setLineWidth(0.5)
    c.rect(margin, tab_top - head_h, tw, head_h, fill=1, stroke=1)
    c.setFillColor(NERO); c.setFont("Helvetica-Bold", 8)
    x = margin
    for i, (h, w) in enumerate(zip(headers, col_w)):
        text_y = tab_top - head_h + (head_h - 8) / 2 - 1   # centrato verticalmente
        if aligns[i] == "R":
            c.drawRightString(x + w - 2*mm, text_y, h)
        else:
            c.drawString(x + 2*mm, text_y, h)
        x += w

    for ri, r in enumerate(righe):
        ry   = tab_top - head_h - (ri+1)*row_h
        tot  = r["nino"] + r["marica"]
        nota = " / ".join(filter(None, [r["nota_nino"], r["nota_marica"]]))
        valori = [r["data"], fmt(r["nino"]), fmt(r["marica"]), fmt(tot), nota]

        c.setFillColor(colors.white if ri % 2 == 0 else colors.HexColor("#fafafa"))
        c.setStrokeColor(NERO); c.setLineWidth(0.5)
        c.rect(margin, ry, tw, row_h, fill=1, stroke=1)

        x = margin
        for i, (val, w) in enumerate(zip(valori, col_w)):
            c.setFillColor(NERO)
            c.setFont("Helvetica", 8)
            if aligns[i] == "R":
                c.drawRightString(x + w - 2*mm, ry + 2.2*mm, val)
            else:
                if i == 4:
                    while c.stringWidth(val, "Helvetica", 8) > w - 4*mm and len(val) > 3:
                        val = val[:-1]
                    if val != nota:
                        val = val.rstrip() + "…"
                c.drawString(x + 2*mm, ry + 2.2*mm, val)
            x += w

    # ── Footer
    c.setStrokeColor(NERO); c.setLineWidth(0.4)
    c.line(margin, 16*mm, W - margin, 16*mm)
    c.setFillColor(NERO); c.setFont("Helvetica", 7)
    c.drawCentredString(W/2, 12*mm,
                        f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.save()
    return True


# ── Data aggiornamento per esteso ─────────────────────────────────────────────
def data_lunga(data_str):
    try:
        d = datetime.strptime(data_str, "%d/%m/%y")
        mesi = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
                "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
        return f"{d.day} {mesi[d.month]} {d.year}"
    except Exception:
        return data_str


# ── Helper cella nota ─────────────────────────────────────────────────────────
def nota_td(testo):
    if testo:
        return f'<td class="nota">{testo}</td>'
    return '<td class="nota-vuota">—</td>'


# ── Righe tabella Nino ────────────────────────────────────────────────────────
def righe_nino(righe):
    html = ""
    for r in righe:
        html += f"""
        <tr>
          <td class="dt">{r["data"]}</td>
          <td class="num">{fmt(r["nino"])}</td>
          {nota_td(r["nota_nino"])}
        </tr>"""
    return html


# ── Righe tabella Marica ──────────────────────────────────────────────────────
def righe_marica(righe):
    html = ""
    for r in righe:
        html += f"""
        <tr>
          <td class="dt">{r["data"]}</td>
          <td class="num">{fmt(r["marica"])}</td>
          {nota_td(r["nota_marica"])}
        </tr>"""
    return html


# ── Righe tabella Totale ──────────────────────────────────────────────────────
def righe_totale(righe):
    html = ""
    for r in righe:
        tot = r["nino"] + r["marica"]
        html += f"""
        <tr>
          <td class="dt">{r["data"]}</td>
          <td class="num">{fmt(r["nino"])}</td>
          <td class="num">{fmt(r["marica"])}</td>
          <td class="tot">{fmt(tot)}</td>
        </tr>"""
    return html


# ── Posizione freccia gauge (%) ───────────────────────────────────────────────
def gauge_pct(valore, minimo, massimo):
    pct = (valore - minimo) / (massimo - minimo) * 100
    return max(0.0, min(100.0, pct))


# ── Etichetta tick gauge ──────────────────────────────────────────────────────
def tick_label(v):
    v = int(v)
    return f"{v // 1000}k" if v >= 1000 else str(v)


# ── Colore totale in base alla zona gauge ─────────────────────────────────────
def colore_totale(totale, minimo, rosso, giallo):
    if totale < rosso:
        return "#e74c3c"   # rosso
    elif totale < giallo:
        return "#d68910"   # giallo/arancio
    else:
        return "#27ae60"   # verde


# ── Generazione HTML ──────────────────────────────────────────────────────────
def genera_html(minimo, massimo, rosso, giallo, righe):
    if not righe:
        raise ValueError("Nessuna riga trovata in Saldi.txt")

    primo      = righe[0]
    nino_val   = primo["nino"]
    marica_val = primo["marica"]
    totale_val = nino_val + marica_val
    zona_val   = colore_zona(totale_val, rosso, giallo)
    icona_zona = {"ROSSO": "🔴", "GIALLO": "🟡", "VERDE": "🟢"}[zona_val]

    # Testo da copiare nel buffer al clic su "Copia"
    copia_testo = (
        f"Saldi al {data_lunga(primo['data'])}\n"
        f"{'.' * 30}\n"
        f"Nino: {fmt(nino_val)}\n"
        f"Marica: {fmt(marica_val)}\n"
        f"Totale: {fmt(totale_val)}"
    )

    pct_totale  = gauge_pct(totale_val, minimo, massimo)
    pct_rosso   = gauge_pct(rosso,  minimo, massimo)
    pct_giallo  = gauge_pct(giallo, minimo, massimo)
    pct_verde   = pct_giallo                          # verde parte da qui
    w_verde     = 100.0 - pct_verde

    col_totale  = colore_totale(totale_val, minimo, rosso, giallo)
    data_agg    = data_lunga(primo["data"])

    lbl_min    = tick_label(minimo)
    lbl_rosso  = tick_label(rosso)
    lbl_giallo = tick_label(giallo)
    lbl_max    = tick_label(massimo)

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>Saldi</title>
<meta name="apple-mobile-web-app-title" content="Saldi">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: #1a1a2e;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    padding: 24px 16px;
  }}

  h1 {{
    color: #d0d0e8;
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: .15em;
    text-transform: uppercase;
    margin-bottom: 22px;
  }}

  .wrapper {{
    display: flex;
    flex-direction: column;
    gap: 16px;
    width: 100%;
    max-width: 460px;
  }}

  .row-top {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }}

  /* ── Card Nino / Marica ── */
  .card {{
    background: #16213e;
    border: 2px solid #d0d0e8;
    border-radius: 18px;
    padding: 22px 18px 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    box-shadow: 0 4px 16px rgba(0,0,0,.4), 0 1px 4px rgba(0,0,0,.5);
    transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
    cursor: pointer;
    user-select: none;
  }}
  .card:hover {{
    transform: translateY(-5px) scale(1.02);
    box-shadow: 0 10px 32px rgba(208,208,232,.15), 0 4px 12px rgba(0,0,0,.6);
    border-color: #ffffff;
  }}
  .card.attiva {{
    border-color: #ffffff;
    box-shadow: 0 0 0 3px #d0d0e8, 0 8px 28px rgba(208,208,232,.2);
    transform: translateY(-3px) scale(1.01);
  }}
  .card-name {{
    color: #d0d0e8;
    font-size: .95rem;
    font-weight: 700;
    letter-spacing: .1em;
    text-transform: uppercase;
  }}
  .card-val {{
    color: #ffffff;
    font-size: 1.55rem;
    font-weight: 700;
    white-space: nowrap;
  }}

  /* ── Card Totale: cornice singola ── */
  .card-total {{
    background: #16213e;
    border: 2px solid {col_totale};
    border-radius: 18px;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(208,208,232,.08), 0 1px 6px rgba(0,0,0,.5);
    cursor: pointer;
    user-select: none;
    transition: border-color .2s ease, box-shadow .2s ease;
  }}
  .card-total:hover {{
    border-color: color-mix(in srgb, {col_totale} 70%, white);
    box-shadow: 0 8px 30px rgba(208,208,232,.18);
  }}
  .card-total.attiva {{
    border-color: {col_totale};
    box-shadow: 0 0 0 3px {col_totale}, 0 8px 28px rgba(208,208,232,.22);
  }}
  .total-top {{
    padding: 20px 22px 16px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }}
  .total-label {{
    color: #d0d0e8;
    font-size: 1.15rem;
    font-weight: 700;
    letter-spacing: .25em;
    text-transform: uppercase;
  }}
  .total-val {{
    color: {col_totale};
    font-size: 2.6rem;
    font-weight: 700;
    white-space: nowrap;
  }}

  /* ── Gauge ── */
  .gauge-box {{
    background: #0d0d1a;
    border-top: 2px solid #d0d0e8;
    padding: 14px 18px 18px;
  }}
  .gauge-indicator {{ position: relative; height: 14px; margin-bottom: 4px; }}
  .gauge-arrow {{
    position: absolute; top: 0;
    transform: translateX(-50%);
    left: {pct_totale:.2f}%;
    width: 0; height: 0;
    border-left: 7px solid transparent;
    border-right: 7px solid transparent;
    border-top: 12px solid #d0d0e8;
  }}
  .gauge-bar-wrap {{
    height: 13px; background: #111133;
    border-radius: 7px; overflow: hidden; position: relative;
  }}
  .gauge-seg {{ position: absolute; top: 0; bottom: 0; }}
  .seg-red    {{ left:0%;              width:{pct_rosso:.2f}%;  background:#c0392b; }}
  .seg-yellow {{ left:{pct_rosso:.2f}%; width:{pct_giallo - pct_rosso:.2f}%; background:#d68910; }}
  .seg-green  {{ left:{pct_verde:.2f}%; width:{w_verde:.2f}%;  background:#1e8449; }}
  .gauge-ticks {{ margin-top: 6px; position: relative; height: 22px; }}
  .tick {{
    display: flex; flex-direction: column; align-items: center; gap: 2px;
    position: absolute; transform: translateX(-50%);
  }}
  .tick-line  {{ width: 1px; height: 6px; background: #888; }}
  .tick-label {{ color: #aaaacc; font-size: .62rem; white-space: nowrap; }}
  .tick-0      {{ left: 0%; }}
  .tick-rosso  {{ left: {pct_rosso:.2f}%; }}
  .tick-giallo {{ left: {pct_giallo:.2f}%; }}
  .tick-max    {{ left: 100%; }}

  /* ── Hint e footer: stesso colore ── */
  .click-hint {{
    text-align: center;
    color: #aaaacc;
    font-size: .65rem;
    letter-spacing: .1em;
    margin-top: -6px;
  }}

  /* ── Pannelli ── */
  .pannello {{
    display: none;
    background: #16213e;
    border: 2px solid #aaaacc44;
    border-radius: 18px;
    overflow: hidden;
    animation: fadeSlide .25s ease;
  }}
  .pannello.aperto {{ display: block; }}
  @keyframes fadeSlide {{
    from {{ opacity: 0; transform: translateY(-8px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  .pannello-header {{
    background: #0f1f3d;
    border-bottom: 2px solid #d0d0e844;
    padding: 10px 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .pannello-title {{
    color: #d0d0e8;
    font-size: .8rem;
    font-weight: 700;
    letter-spacing: .12em;
    text-transform: uppercase;
  }}
  .btn-chiudi {{
    background: none;
    border: 1px solid #aaaacc44;
    border-radius: 8px;
    color: #aaaacc;
    font-family: inherit;
    font-size: .7rem;
    padding: 4px 10px;
    cursor: pointer;
    letter-spacing: .08em;
  }}
  .btn-chiudi:hover {{ background: #ffffff11; }}

  /* ── Tabella ── */
  table {{ width: 100%; border-collapse: collapse; font-size: .78rem; }}
  thead tr {{ background: #0f1f3d; border-bottom: 2px solid #aaaacc66; }}
  th {{
    color: #aaaacc; font-weight: 700; letter-spacing: .08em;
    text-transform: uppercase; padding: 10px 12px;
    text-align: right; border-right: 1px solid #ffffff18;
  }}
  th:first-child {{ text-align: left; }}
  th:last-child {{ border-right: none; }}
  tbody tr {{ border-top: 1px solid #ffffff18; }}
  td {{
    padding: 9px 12px; color: #d0d0e8;
    white-space: nowrap; border-right: 1px solid #ffffff18;
    vertical-align: top;
  }}
  td:last-child {{ border-right: none; }}
  td.dt   {{ color: #aaaacc; text-align: left; }}
  td.num  {{ text-align: right; }}
  td.tot  {{ color: #ffffff; font-weight: 700; text-align: right; }}
  td.nota {{
    color: #8888bb;
    font-style: normal;
    font-size: .72rem;
    white-space: normal;
    max-width: 160px;
  }}
  td.nota-vuota {{ color: #444466; font-size: .72rem; text-align: center; }}

  footer {{
    margin-top: 14px;
    color: #aaaacc;
    font-size: .7rem;
    letter-spacing: .08em;
  }}

  /* ── Bottoni azione ── */
  .azioni {{
    display: flex;
    gap: 10px;
    margin-top: 4px;
  }}
  .btn-copia, .btn-pdf {{
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 13px 10px;
    border-radius: 14px;
    font-family: inherit;
    font-size: .85rem;
    font-weight: 700;
    letter-spacing: .06em;
    cursor: pointer;
    border: none;
    text-decoration: none;
    transition: transform .15s ease, filter .15s ease;
  }}
  .btn-copia {{ background: #d0d0e8; color: #1a1a2e; }}
  .btn-pdf   {{ background: #d0d0e8; color: #1a1a2e; }}
  .btn-copia:hover, .btn-pdf:hover {{
    transform: translateY(-2px);
    filter: brightness(1.1);
  }}

  /* Toast "Copiato!" */
  #toast {{
    display: none;
    position: fixed;
    bottom: 30px;
    left: 50%;
    transform: translateX(-50%);
    background: #333;
    color: #fff;
    padding: 8px 22px;
    border-radius: 20px;
    font-size: .82rem;
    font-weight: 600;
    letter-spacing: .05em;
    z-index: 9999;
    pointer-events: none;
    animation: fadeInOut 2s ease forwards;
  }}
  @keyframes fadeInOut {{
    0%   {{ opacity: 0; }}
    10%  {{ opacity: 1; }}
    80%  {{ opacity: 1; }}
    100% {{ opacity: 0; }}
  }}
</style>
</head>
<body>

<h1>💰 Situazione Saldi</h1>

<div class="wrapper">
  <div class="row-top">

    <div class="card" id="cardNino" onclick="togglePannello('nino')">
      <div class="card-name">Nino</div>
      <div class="card-val">{fmt(nino_val)}</div>
    </div>

    <div class="card" id="cardMarica" onclick="togglePannello('marica')">
      <div class="card-name">Marica</div>
      <div class="card-val">{fmt(marica_val)}</div>
    </div>

  </div>

  <div class="card-total" id="cardTotale" onclick="togglePannello('totale')">
    <div class="total-top">
      <div class="total-label">Totale</div>
      <div class="total-val">{fmt(totale_val)}</div>
    </div>
    <div class="gauge-box">
      <div class="gauge-indicator"><div class="gauge-arrow"></div></div>
      <div class="gauge-bar-wrap">
        <div class="gauge-seg seg-red"></div>
        <div class="gauge-seg seg-yellow"></div>
        <div class="gauge-seg seg-green"></div>
      </div>
      <div class="gauge-ticks">
        <div class="tick tick-0">
          <div class="tick-line"></div><div class="tick-label">{lbl_min}</div>
        </div>
        <div class="tick tick-rosso">
          <div class="tick-line"></div><div class="tick-label">{lbl_rosso}</div>
        </div>
        <div class="tick tick-giallo">
          <div class="tick-line"></div><div class="tick-label">{lbl_giallo}</div>
        </div>
        <div class="tick tick-max">
          <div class="tick-line"></div><div class="tick-label">{lbl_max}</div>
        </div>
      </div>
    </div>
  </div>

  <div class="click-hint">▲ clicca su un box per i dettagli</div>

  <!-- Pannello NINO -->
  <div class="pannello" id="pannelloNino">
    <div class="pannello-header">
      <span class="pannello-title">📊 Nino — storico</span>
      <button class="btn-chiudi" onclick="chiudiPannello('nino')">✖ chiudi</button>
    </div>
    <table>
      <thead><tr><th>Data</th><th>Nino</th><th style="text-align:left;">Nota</th></tr></thead>
      <tbody>{righe_nino(righe)}</tbody>
    </table>
  </div>

  <!-- Pannello MARICA -->
  <div class="pannello" id="pannelloMarica">
    <div class="pannello-header">
      <span class="pannello-title">📊 Marica — storico</span>
      <button class="btn-chiudi" onclick="chiudiPannello('marica')">✖ chiudi</button>
    </div>
    <table>
      <thead><tr><th>Data</th><th>Marica</th><th style="text-align:left;">Nota</th></tr></thead>
      <tbody>{righe_marica(righe)}</tbody>
    </table>
  </div>

  <!-- Pannello TOTALE -->
  <div class="pannello" id="pannelloTotale">
    <div class="pannello-header">
      <span class="pannello-title">📊 Totale — storico</span>
      <button class="btn-chiudi" onclick="chiudiPannello('totale')">✖ chiudi</button>
    </div>
    <table>
      <thead><tr><th>Data</th><th>Nino</th><th>Marica</th><th>Totale</th></tr></thead>
      <tbody>{righe_totale(righe)}</tbody>
    </table>
  </div>

  <!-- Bottoni azione -->
  <div class="azioni">
    <button class="btn-copia" onclick="copiaTesto()">
      📋 Copia
    </button>
    <a class="btn-pdf" href="Saldi.pdf" target="_blank" rel="noopener">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm-1 1.5L18.5 9H13V3.5zM6 20V4h5v7h7v9H6zm2-5h8v1H8v-1zm0-3h8v1H8v-1z"/>
      </svg>
      Apri PDF
    </a>
  </div>

  <!-- Toast feedback -->
  <div id="toast">✅ Copiato!</div>

</div>

<footer>Aggiornamento: {data_agg}</footer>

<script>
var TESTO_COPIA = {copia_testo!r};
function copiaTesto() {{
  navigator.clipboard.writeText(TESTO_COPIA).then(function() {{
    var t = document.getElementById('toast');
    t.style.display = 'block';
    // Riavvia animazione
    t.style.animation = 'none';
    t.offsetHeight; // reflow
    t.style.animation = 'fadeInOut 2s ease forwards';
    setTimeout(function() {{ t.style.display = 'none'; }}, 2000);
  }});
}}
var PANNELLI = {{
  nino:   {{ pannello: 'pannelloNino',   card: 'cardNino'   }},
  marica: {{ pannello: 'pannelloMarica', card: 'cardMarica' }},
  totale: {{ pannello: 'pannelloTotale', card: 'cardTotale' }}
}};
var aperto = null;
function togglePannello(id) {{
  if (aperto === id) {{ chiudiPannello(id); }}
  else {{ if (aperto) chiudiPannello(aperto); apriPannello(id); }}
}}
function apriPannello(id) {{
  var cfg = PANNELLI[id];
  document.getElementById(cfg.pannello).classList.add('aperto');
  document.getElementById(cfg.card).classList.add('attiva');
  aperto = id;
}}
function chiudiPannello(id) {{
  var cfg = PANNELLI[id];
  document.getElementById(cfg.pannello).classList.remove('aperto');
  document.getElementById(cfg.card).classList.remove('attiva');
  if (aperto === id) aperto = null;
}}

// Auto-refresh: legge Saldi.txt raw da GitHub ogni 30 secondi
(function() {{
  var RAW_URL = 'https://raw.githubusercontent.com/{GH_REPO}/refs/heads/main/{GH_FOLDER}/Saldi.txt';
  var MINIMO  = {minimo};
  var MASSIMO = {massimo};
  var ROSSO   = {rosso};
  var GIALLO  = {giallo};

  function fmtEuro(n) {{
    return '\u20ac ' + n.toString().replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, '.');
  }}

  function mesiIT(m) {{
    return ['','gennaio','febbraio','marzo','aprile','maggio','giugno',
            'luglio','agosto','settembre','ottobre','novembre','dicembre'][m];
  }}

  function dataLunga(s) {{
    // formato gg/mm/aa
    var p = s.split('/');
    if (p.length !== 3) return s;
    var d = parseInt(p[0], 10);
    var m = parseInt(p[1], 10);
    var y = 2000 + parseInt(p[2], 10);
    return d + ' ' + mesiIT(m) + ' ' + y;
  }}

  function parseTxt(testo) {{
    // Cerca l'ultimo blocco Data:
    var blocchi = testo.split(/\\n(?=Data:)/);
    var ultimo = null;
    for (var i = 0; i < blocchi.length; i++) {{
      if (/^Data:/.test(blocchi[i].trim())) ultimo = blocchi[i];
    }}
    if (!ultimo) return null;
    var mD = ultimo.match(/Data:\\s*(\\S+)/);
    var mN = ultimo.match(/Nino:\\s*\\u20ac\\s*([\\d.]+)(?:;\\s*(.+))?/);
    var mM = ultimo.match(/Marica:\\s*\\u20ac\\s*([\\d.]+)(?:;\\s*(.+))?/);
    if (!mD || !mN || !mM) return null;
    return {{
      data:   mD[1],
      nino:   parseInt(mN[1].replace(/[.]/g,''), 10),
      marica: parseInt(mM[1].replace(/[.]/g,''), 10),
    }};
  }}

  function pct(v) {{
    return Math.max(0, Math.min(100, (v - MINIMO) / (MASSIMO - MINIMO) * 100));
  }}

  function colTotale(tot) {{
    if (tot < ROSSO)  return '#e74c3c';
    if (tot < GIALLO) return '#d68910';
    return '#27ae60';
  }}

  function aggiorna(r) {{
    var tot = r.nino + r.marica;
    var col = colTotale(tot);
    var pTot = pct(tot);

    // valori card
    document.querySelector('#cardNino .card-val').textContent   = fmtEuro(r.nino);
    document.querySelector('#cardMarica .card-val').textContent = fmtEuro(r.marica);
    document.querySelector('.total-val').textContent            = fmtEuro(tot);

    // colore bordo totale e valore
    var ct = document.getElementById('cardTotale');
    ct.style.borderColor = col;
    document.querySelector('.total-val').style.color = col;

    // freccia gauge
    document.querySelector('.gauge-arrow').style.left = pTot.toFixed(2) + '%';

    // footer
    var dl = dataLunga(r.data);
    var footer = document.querySelector('footer');
    if (footer) footer.textContent = 'Aggiornamento: ' + dl;
  }}

  setInterval(function() {{
    fetch(RAW_URL + '?t=' + Date.now(), {{cache: 'no-store'}})
      .then(function(res) {{ return res.text(); }})
      .then(function(testo) {{
        var r = parseTxt(testo);
        if (r) aggiorna(r);
      }})
      .catch(function() {{}});
  }}, 30000);
}})();
</script>

</body>
</html>"""

    return html


# ── Caricamento su GitHub ─────────────────────────────────────────────────────
def carica_su_github(file_paths):
    if not GH_TOKEN or not GH_REPO:
        print("ℹ  GitHub: token o repo non configurati, caricamento saltato.")
        return

    try:
        from github import Github, GithubException
    except ImportError:
        print("⚠  PyGithub non trovato. Installa con: pip install PyGithub")
        return

    try:
        gh   = Github(GH_TOKEN)
        repo = gh.get_repo(GH_REPO)

        for local_path in file_paths:
            nome_file  = os.path.basename(local_path)
            repo_path  = f"{GH_FOLDER}/{nome_file}" if GH_FOLDER else nome_file
            commit_msg = f"Aggiornamento {nome_file}"

            with open(local_path, "rb") as f:
                contenuto = f.read()

            # Verifica se il file esiste già (per aggiornarlo invece di crearlo)
            try:
                esistente = repo.get_contents(repo_path)
                repo.update_file(repo_path, commit_msg, contenuto, esistente.sha)
                print(f"✓ GitHub aggiornato: {repo_path}")
            except GithubException:
                repo.create_file(repo_path, commit_msg, contenuto)
                print(f"✓ GitHub creato: {repo_path}")

    except Exception as e:
        print(f"❌ Errore GitHub: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import webbrowser
    minimo, massimo, rosso, giallo, righe = leggi_txt(FILE_TXT)

    html = genera_html(minimo, massimo, rosso, giallo, righe)
    with open(FILE_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ Generato {FILE_HTML}  ({len(righe)} righe)")

    ok = genera_pdf(minimo, massimo, rosso, giallo, righe, FILE_PDF)
    if ok:
        print(f"✓ Generato {FILE_PDF}")

    carica_su_github([FILE_HTML, FILE_PDF, FILE_TXT])

    webbrowser.open(FILE_HTML)
    sys.exit(0)
