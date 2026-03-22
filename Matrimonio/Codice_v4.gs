const SHEET_NAME = 'Risposte';

function getSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow(['Data', 'Nome', 'Persone', 'Secondo', 'Allergie', 'Note']);
    sheet.getRange(1, 1, 1, 6).setFontWeight('bold');
  }
  return sheet;
}

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const sheet = getSheet();
    sheet.appendRow([
      new Date().toLocaleString('it-IT'),
      data.nome     || '',
      data.persone  || '',
      data.secondo  || '',
      data.allergie || '',
      data.note     || ''
    ]);
    return ContentService
      .createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch(err) {
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, error: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  try {
    const sheet = getSheet();

    // Elimina riga se richiesto
    if (e.parameter && e.parameter.elimina) {
      const riga = parseInt(e.parameter.elimina);
      if (riga >= 2 && riga <= sheet.getLastRow()) {
        sheet.deleteRow(riga);
        return ContentService
          .createTextOutput(JSON.stringify({ ok: true }))
          .setMimeType(ContentService.MimeType.JSON);
      }
    }

    // Leggi tutte le righe
    if (sheet.getLastRow() < 2) {
      return ContentService
        .createTextOutput(JSON.stringify({ ok: true, rows: [] }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    const data = sheet.getRange(2, 1, sheet.getLastRow() - 1, 6).getValues();
    const rows = data.map(r => ({
      data:     r[0] ? r[0].toLocaleString('it-IT') : '',
      nome:     r[1],
      persone:  r[2],
      secondo:  r[3],
      allergie: r[4],
      note:     r[5]
    }));
    return ContentService
      .createTextOutput(JSON.stringify({ ok: true, rows }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch(err) {
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, error: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
