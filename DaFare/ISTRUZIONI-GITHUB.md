# Cose da fare - configurazione GitHub

## Obiettivo

Il programma deve funzionare anche con il PC spento e deve sincronizzare PC e iPhone tramite GitHub.

L'utente finale non deve vedere campi tecnici: vede solo l'app.

Per massima semplicità e PC spento:

- GitHub conserva il file dati.
- Cloudflare Worker custodisce il token GitHub.
- `todo-priorita.html` parla solo con il Worker.
- L'utente non vede GitHub, token o configurazioni.

## File da mettere nel repository

- `todo-priorita.html`
- `todo-priorita-dati.json`

## Passi su GitHub

1. Accedi a GitHub.
2. Crea un nuovo repository, per esempio `da-fare`.
3. Scegli se renderlo privato o pubblico.
4. Carica nel repository questi due file:
   - `todo-priorita.html`
   - `todo-priorita-dati.json`
5. Crea un token GitHub fine-grained con accesso solo a quel repository.
6. Dai al token il permesso `Contents: Read and write`.
7. Non mettere il token nel file HTML.

## Passi su Cloudflare Worker

1. Accedi a Cloudflare.
2. Apri `Workers & Pages`.
3. Crea un Worker, per esempio `da-fare-sync`.
4. Incolla il contenuto del file `github-sync-worker.js`.
5. In `Settings` -> `Variables` aggiungi:
   - `GITHUB_OWNER` = `Sebastiano-Mazzarisi`
   - `GITHUB_REPO` = `Prog`
   - `GITHUB_BRANCH` = `main`
   - `GITHUB_PATH` = `DaFare/todo-priorita-dati.json`
6. In `Settings` -> `Variables` -> `Secrets` aggiungi:
   - `GITHUB_TOKEN` = il token GitHub
7. Salva e deploya.
8. Copia l'URL del Worker, per esempio:
   `https://da-fare-sync.NOME.workers.dev`

## Configurazione del file HTML

Nel file `todo-priorita.html`, cerca `builtInSyncConfig` e imposta:

```js
apiUrl: "https://da-fare-sync.NOME.workers.dev"
```

Lascia:

```js
token: ""
```

## GitHub Pages

Per aprire l'app da iPhone senza Dropbox:

1. Vai nel repository su GitHub.
2. Apri `Settings`.
3. Apri `Pages`.
4. In `Build and deployment`, scegli `Deploy from a branch`.
5. Scegli branch `main` e cartella `/root`.
6. Salva.
7. GitHub mostrerà un indirizzo tipo:
   `https://UTENTE.github.io/REPOSITORY/todo-priorita.html`

## Nota di sicurezza

Il token non deve stare nel file HTML.

Il token deve stare solo nel Worker come secret.
