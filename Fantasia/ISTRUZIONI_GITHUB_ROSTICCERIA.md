# Rosticcerie su iPhone con GitHub

Questo progetto e' pronto per funzionare anche con il PC spento usando GitHub Actions.

## Cosa fa

- Ogni 30 minuti tra le 10:00 e le 12:00, ora italiana, GitHub avvia `Rosticceria.py`.
- Lo script estrae la prima foto da:
  - Rosticceria Fantasia
  - Cibaria
- Le immagini vengono salvate in `output/rosticceria_ios`.
- GitHub Pages pubblica una pagina apribile da iPhone.

## File preparati

- `Rosticceria.py`: script di estrazione.
- `.github/workflows/rosticceria-ios.yml`: automazione GitHub Actions.
- `requirements.txt`: librerie Python richieste.
- `.gitignore`: evita di caricare i cookie locali.
- `output/rosticceria_ios/index.html`: pagina per iPhone.

## Cosa devi fare su GitHub

### 1. Carica questa cartella in un repository GitHub

Puoi usare GitHub Desktop oppure il sito GitHub.

### 2. Aggiungi il Secret dei cookie Facebook

Nel repository GitHub:

1. Apri `Settings`.
2. Apri `Secrets and variables`.
3. Apri `Actions`.
4. Crea un nuovo `Repository secret`.
5. Nome:

```text
FACEBOOK_COOKIES
```

6. Valore: incolla il contenuto del file locale `cookies.txt`.

Importante: non caricare `cookies.txt` nel repository pubblico.

### 3. Attiva GitHub Pages

Nel repository GitHub:

1. Apri `Settings`.
2. Apri `Pages`.
3. In `Build and deployment`, scegli `GitHub Actions`.

### 4. Prova manualmente

Nel repository GitHub:

1. Apri `Actions`.
2. Scegli `Rosticcerie iOS`.
3. Premi `Run workflow`.

Quando finisce, la pagina sara' raggiungibile da un indirizzo simile a:

```text
https://TUO_UTENTE.github.io/NOME_REPOSITORY/
```

## Orari

Il workflow e' programmato su GitHub ogni 30 minuti nella fascia UTC utile.
Poi controlla l'ora italiana vera, quindi funziona sia con ora legale sia con ora solare.

Esegue nella finestra:

```text
10:00, 10:30, 11:00, 11:30, 12:00
```

