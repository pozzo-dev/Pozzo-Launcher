# Temi e plugin di Pozzo Launcher

Pozzo Launcher si personalizza in tre modi:

| | Per chi | Cosa cambia | Linguaggio |
|---|---|---|---|
| **Tema** | Chiunque | Colori dell'interfaccia | Solo CSS |
| **Profilo di esperienza** | Chi vuole cambiare l'interfaccia desktop | Struttura, navigazione, Home e presentazione del dettaglio | JavaScript |
| **Plugin** | Chi programma | Nuove funzioni: pulsanti, pagine, store, fonti di dati, reazioni agli eventi | JavaScript e/o Python |

Le cartelle si trovano accanto a `config.toml`:

```
PozzoLauncher/
  config.toml
  themes/<id-tema>/
  plugins/<id-plugin>/
```

Temi e plugin si attivano da **Impostazioni › Aspetto**. Dopo aver aggiunto o abilitato un plugin, riavvia l'app.

---

## Temi

```
themes/mio-tema/
  theme.json
  theme.css          # vista normale
  bigpicture.css     # facoltativo: modalità Big Picture (se manca, usa "desktop")
```

**theme.json**
```json
{
  "name": "Il mio tema",
  "description": "Verde scuro",
  "author": "Io",
  "preview": "#0f1f14",
  "desktop": "theme.css",
  "bigpicture": "bigpicture.css"
}
```

**theme.css**: ridefinisci le variabili di colore per mantenere il tema combinabile con tutti i profili di esperienza.
```css
:root {
  --bg: #0b140e;        /* sfondo */
  --bg-2: #102016;      /* barra laterale, campi */
  --bg-3: #183024;      /* elementi in rilievo */
  --panel: #0f1d14;     /* pannello dettaglio, finestre */
  --line: #24442f;      /* bordi */
  --text: #e9f5ec;
  --muted: #8fb39a;
  --accent: #3ddc84;    /* colore principale (selezione, pulsanti) */
  --accent-2: #00b894;  /* secondo colore dei gradienti */
  --fav: #ffd54a;
}
```

Un tema può tecnicamente contenere regole CSS arbitrarie. Per non legarlo a una sola esperienza, limita i temi ai colori e usa un profilo di esperienza per cambiare layout o struttura; le regole CSS mirate a `.tile`, `#sidebar` o `.detail` possono sovrascrivere l'aspetto scelto dall'esperienza.

Sulla pagina sono disponibili due attributi utili:

| Attributo | Valori |
|---|---|
| `<html data-mode>` | `desktop` / `bigpicture` |
| `<html data-theme>` | id del tema attivo |

I temi inclusi (`pozzo/app/themes/`: OLED, Chiaro, Retrò, Notte blu) sono buoni esempi da copiare.

In **Impostazioni › Aspetto** si sceglie il tema e si vede l'anteprima del colore di ciascuno:

![Impostazioni › Aspetto: scelta del tema e plugin installati](images/impostazioni-aspetto.jpg)

### Galleria dei 4 temi inclusi

Ecco come appare Pozzo Launcher con i quattro temi forniti di serie:

#### 1. Tema OLED (Nero assoluto)
Sfondo nero puro (`#000000`), contrasto massimo, perfetto per schermi OLED e per non affaticare la vista nelle sessioni notturne.

![Tema OLED: neri assoluti e accenti vivaci ad altissimo contrasto](images/tema-oled.jpg)

#### 2. Tema Notte Blu
Toni indaco e blu notte rilassanti con accenti azzurri, ideale per l'uso serale quotidiano su qualsiasi monitor.

![Tema Notte Blu: palette fredda riposante per lunghe sessioni](images/tema-notte-blu.jpg)

#### 3. Tema Retrò
Caldo e nostalgico, con colori crema, marrone e arancio ispirati all'hardware e alle sale giochi arcade anni '80 e '90.

![Tema Retrò: look vintage caldo e accogliente](images/tema-retro.jpg)

#### 4. Tema Chiaro
Look moderno e pulito, a sfondo chiaro con testi scuri ad altissima leggibilità in uffici o stanze molto illuminate.

![Tema Chiaro: interfaccia luminosa moderna e pulita](images/tema-chiaro.jpg)

---

## Profili di esperienza

Il tema e il profilo di esperienza sono preferenze distinte: il tema applica la pelle visiva (CSS),
mentre l'esperienza sceglie alcuni comportamenti e la disposizione dell'interfaccia **desktop**.
Si selezionano separatamente in **Impostazioni › Aspetto** e si possono combinare liberamente.
Cambiare tema non cambia esperienza e viceversa. I temi continuano ad applicarsi anche in Big Picture;
il contratto delle esperienze descritto qui è caricato solo nell'interfaccia desktop.

Le esperienze incluse nell'app sono nel percorso:

```
pozzo/app/static/experiences/<id>/
  experience.js      # obbligatorio per registrare il profilo
  style.css          # facoltativo: stile aggiuntivo per quel profilo
```

Il motore cerca cartelle incluse sotto `pozzo/app/static/experiences/` con un ID in minuscolo
(lettera iniziale, poi lettere, numeri, `_` o `-`); non segue cartelle che risolvono fuori da quella
radice. Per i file serve solo `experience.js` e, se presente, `style.css`. Non è un formato di plugin:
lo Store estensioni non installa esperienze di terzi. Per aggiungerne una occorre includerne i file
nell'applicazione distribuita. Il codice JavaScript caricato è codice dell'app e non un'esperienza di
terzi isolata in un sandbox.

`experience.js` è un modulo JavaScript che registra il profilo con `GS.registerExperience(...)`;
non serve un export predefinito:

```js
GS.registerExperience({
  id: "mia-esperienza",            // deve corrispondere al nome della cartella
  name: "La mia esperienza",       // obbligatorio
  description: "Una Home semplice.",
  nav: "sidebar",                  // "sidebar", "top" oppure "none"
  detail: "panel",                 // "panel", "page" oppure "modal"
  home: (element) => { element.textContent = "La mia Home"; },
  card: null,
  onFocus: (game) => console.log("Tessera attiva:", game.title),
});
```

Campi e callback supportati:

| Campo | Contratto effettivo |
|---|---|
| `id` | Obbligatorio; formato `[a-z][a-z0-9_-]*` e deve coincidere con l'ID della cartella caricata. |
| `name` | Obbligatorio, stringa. `description` è facoltativa; se omessa diventa vuota. |
| `nav` | Obbligatorio: `sidebar` mantiene la barra laterale; `top` mostra la navigazione superiore con le voci Home, Libreria, Preferiti e Store, più il pulsante che apre il cassetto laterale; `none` nasconde la barra dell'esperienza e la barra laterale. Le voci non sono configurabili dal profilo. |
| `detail` | Obbligatorio: `panel` presenta il dettaglio nel pannello laterale; `page` lo presenta a schermo intero e porta il focus al dettaglio; `modal` lo presenta come sovrapposizione centrata con ruolo `dialog` e `aria-modal="true"`, portando il focus sul pulsante di chiusura. `panel` non riceve un ruolo ARIA specifico dal motore. Sono modalità di presentazione del dettaglio esistente, non renderer personalizzati. |
| `home(element, context)` | Facoltativa; chiamata per disegnare la Home nel nodo DOM. `context` contiene `renderShelvesHome`, `state` (stato dell'interfaccia) e `setView`. È invocata sincronicamente: il motore non attende una Promise restituita dal callback. Se il profilo ha `home`, viene selezionata la Home all'avvio senza una vista già salvata e quando lo si sceglie nel selettore. Se il callback genera un'eccezione, la Home mostra un messaggio di indisponibilità e l'errore va in console. |
| `card(game, markup, context)` | Facoltativa; chiamata sincronicamente per ogni scheda, con il gioco, il markup HTML predefinito e `{ experience, state }`. Una stringa sostituisce il markup; un `Element` sostituisce i figli della scheda; altri valori non lo modificano. Un'eccezione viene registrata in console e la scheda standard resta disponibile. |
| `onFocus(game)` | Facoltativa; chiamata quando il focus passa a una tessera di gioco, con l'oggetto gioco corrispondente. Non è un evento di focus della finestra; può essere usata, per esempio, per aggiornare un contenuto in primo piano. Un'eccezione viene registrata in console. |

Il motore verifica i campi obbligatori, i valori di `nav`/`detail`, i tipi dei callback e la corrispondenza dell'ID. Se lo script non registra il profilo previsto o fallisce, il selettore lo disabilita e mostra l'errore. `style.css`, se presente, viene caricato solo per l'esperienza selezionata; gli asset arbitrari non sono esposti dalla rotta delle esperienze. Non esiste un callback per definire una barra di navigazione personalizzata o un nuovo tipo di dettaglio.

Le esperienze incluse sono:

| Esperienza | Interfaccia e navigazione | Dettaglio |
|---|---|---|
| **Originale** (`original`) | Interfaccia originale legacy, barra laterale. | Pannello laterale. |
| **Catalogo** (`catalog`) | Catalogo classico, barra laterale. | Pannello laterale. |
| **Scaffali** (`shelves`) | Home con suggerimenti e scaffali orizzontali; navigazione superiore e cassetto laterale. | Pannello laterale. |
| **Console** (`console`) | Schermata immersiva senza navigazione generale; spostare il focus tra le tessere aggiorna il gioco in primo piano. | Schermo intero. |
| **Dashboard** (`dashboard`) | Home dashboard con gioco in evidenza, sezioni recenti/preferiti/raccolta e guida rapida; navigazione superiore. | Pannello laterale. |
| **Cinema** (`cinema`) | Home cinematografica con banner e righe orizzontali di giochi; navigazione superiore. | Sovrapposizione modale. |
| **Vetrina** (`storefront`) | Home vetrina con gioco in evidenza, raccolta e filtri per piattaforma; navigazione superiore. | Schermo intero. |

### Galleria visiva dei 6 profili di esperienza

Ogni profilo di esperienza trasforma l'organizzazione dei contenuti del launcher:

#### Scaffali (`shelves`)
La Home moderna con scaffali tematici orizzontali in stile streaming per riprendere subito a giocare, scoprire saghe e continuare i titoli in corso.

![Esperienza Scaffali: layout a righe orizzontali stile Netflix](images/esp-scaffali.jpg)

#### Cinema (`cinema`)
Esperienza ad alto impatto visivo con banner a tutto schermo, sfondi cinematografici e dettaglio aperto in sovrapposizione modale.

![Esperienza Cinema: grafica immersiva con sfondi spettacolari](images/esp-cinema.jpg)

#### Console (`console`)
Interfaccia pulita e minimale a tutto schermo, perfetta per chi usa mouse o controller come se fosse su una console da gioco da salotto.

![Esperienza Console: navigazione fluida e focus immediato sul gioco](images/esp-console.jpg)

#### Dashboard (`dashboard`)
Panoramica completa con gioco in evidenza, sezioni recenti, preferiti, statistiche e scorciatoie di avvio rapido in un unico colpo d'occhio.

![Esperienza Dashboard: centro di comando ricco di widget e informazioni](images/esp-dashboard.jpg)

#### Vetrina (`storefront`)
Layout elegante che valorizza le copertine dei tuoi titoli di punta, con filtri rapidi per piattaforma e dettaglio a schermo intero.

![Esperienza Vetrina: copertine grandi in primo piano e catalogazione elegante](images/esp-vetrina.jpg)

#### Catalogo (`catalog`)
La vista classica per veri collezionisti: griglia densa di copertine con barra laterale fissa per accedere a tutte le console e collezioni.

![Esperienza Catalogo: griglia classica completa con barra laterale](images/esp-catalogo.jpg)

Il selettore mostra anteprime schematiche, non screenshot generati dal profilo: sono previste varianti distinte per **Console**, **Dashboard**, **Cinema**, **Vetrina**, **Originale**, **Catalogo** e **Scaffali**. **Originale** è il preset legacy e conserva il selettore CSS storico della vista Catalogo; resta una scelta distinta nel selettore. Le anteprime illustrano la disposizione, non garantiscono l'aspetto finale del JavaScript o CSS. Anche i temi restano selezionabili indipendentemente nella propria sezione del selettore, con la loro anteprima colore.

La scelta dell'esperienza è salvata globalmente in `settings.json` (`app.experience`), per l'installazione e non per il singolo profilo utente; un ID non più disponibile ricade su **Catalogo**. La scelta del tema è salvata separatamente (`app.theme`). **Scaffali** è un esempio di Home personalizzata con suggerimenti e scaffali orizzontali; **Catalogo** e **Originale** mantengono la navigazione laterale.

Per l'ispirazione visiva, non usare nomi ufficiali, loghi o artwork di altre piattaforme.

---

## Plugin

```
plugins/mio-plugin/
  plugin.toml      # obbligatorio
  frontend.js      # facoltativo: interfaccia
  style.css        # facoltativo
  backend.py       # facoltativo: Python, lato server
```

**plugin.toml**
```toml
[plugin]
name = "Il mio plugin"
version = "1.0"
author = "Io"
description = "Cosa fa"
api = 1
```

Chiavi facoltative di `[plugin]`:

- `permissions = [...]`: i permessi che l'estensione usa, come stringhe di un elenco chiuso (con un eventuale suffisso `:dettaglio`):
  `"rete:<host>"` (accesso a un host, es. `"rete:api.rawg.io"`), `"rete:*"` (qualsiasi sito scelto dall'utente, es.
  feed o pagine aggiunti a mano), `"libreria:lettura"`, `"libreria:scrittura"`,
  `"file:lettura"`, `"file:scrittura"`, `"impostazioni"`, `"notifiche"`, `"avvio"` (può avviare giochi o programmi).
  Lo store li mostra prima dell'installazione (scritture, file, avvio e `rete:*` evidenziati come sensibili); in un
  aggiornamento chiede conferma solo per i permessi nuovi rispetto alla versione installata (`installed_permissions`).
  Un permesso non riconosciuto viene mantenuto ma segnalato come tale;
  se la chiave manca del tutto, lo store indica che i permessi non sono dichiarati (`permissions_unknown`).

### Interfaccia (frontend.js)

È un modulo JavaScript che esporta una funzione. Riceve `gs`, l'API dell'app, che funziona sia nella vista normale sia nella Big Picture:

```js
export default function (gs, ctx) {
  // pulsante nel dettaglio di ogni gioco
  gs.addGameAction({
    id: "wiki", label: "Wiki", icon: "📖",
    when: (game) => !game.store,          // facoltativo: solo per alcuni giochi
    run: (game) => gs.api("/api/open", { body: { url: "https://it.wikipedia.org/wiki/" + encodeURIComponent(game.title) } }),
  });

  // sezione nel dettaglio (HTML o Element, anche asincrona)
  gs.addDetailSection({ id: "note", title: "Le mie note", render: async (game) => `<p>${gs.esc(game.title)}</p>` });

  // etichetta sulle copertine
  gs.addTileBadge({ id: "retro", render: (g) => (g.year && g.year < 1990 ? "RETRÒ" : null) });

  // voce nella barra laterale che apre una pagina
  gs.addSidebarItem({ id: "mia", label: "La mia pagina", icon: "✨", view: "mia-pagina" });
  gs.registerView("mia-pagina", { title: "La mia pagina", render: (el) => { el.innerHTML = "<h2>Ciao!</h2>"; } });

  // sottopagina nelle impostazioni, sotto «Streaming»
  gs.addSettingsTab({ id: "mio", label: "Mio plugin", category: "streaming",
    render: (el) => { el.innerHTML = "…"; } });

  // eventi dell'interfaccia
  gs.on("gameOpened", (game) => console.log("aperto", game.title));
}
```

`category` è facoltativo. Se omesso, la sottopagina compare sotto **Estensioni**. I valori disponibili sono
`generale`, `aspetto`, `libreria`, `fonti`, `store`, `emulatori`, `controller`, `streaming`, `integrazioni`,
`estensioni`, `dati` e `sistema`. Le categorie si possono aprire direttamente con link come `#settings/streaming`.

**Eventi dell'interfaccia**:
- `libraryLoaded`: libreria caricata o ricaricata;
- `viewChanged`: cambio di vista;
- `gameOpened`: dettaglio di un gioco aperto;
- `uiChanged`: un plugin ha aggiunto elementi;
- `extensionsLoaded`: temi e plugin caricati.

**Funzioni utili**:

| Funzione | Cosa fa |
|---|---|
| `gs.api(path, {body, method})` | Chiama le API dell'app o del tuo backend |
| `gs.library()` | Libreria in memoria (`games`, `plats`, `colls`, …) |
| `gs.openGame(id)` | Apre il dettaglio di un gioco |
| `gs.currentGame()` | Gioco aperto in questo momento |
| `gs.toast(msg, errore)` | Mostra una notifica |
| `gs.esc(testo)` | Rende sicuro un testo da inserire nell'HTML |
| `gs.mode` | `"desktop"` o `"bigpicture"` |

`ctx.settings` contiene le impostazioni salvate dal backend del plugin. `ctx.t` e `ctx.lang` servono per i testi tradotti (vedi sotto).

Altre funzioni dell'interfaccia:

| Funzione | Cosa fa |
|---|---|
| `gs.addShelf({id, title, why?, games(lib)})` | Scaffale nella home a scaffali. `games` riceve la libreria e restituisce i giochi da mostrare (anche con una Promise); se è vuoto lo scaffale non compare |
| `gs.ui.registerWidget({id, title, defaultSpan, render})` | Riquadro della home **Dashboard** |
| `gs.addTutorial({...})` | Tutorial dell'estensione (vedi sotto) |
| `gs.hints.register({id, target, text})` | Suggerimento breve accanto a un elemento, mostrato una volta |
| `gs.redraw()`, `gs.refresh()` | Ridisegna la vista corrente; ricarica la libreria |

`addDetailSection` accetta anche `when(game)`: la sezione compare solo quando restituisce `true`.

#### Testi e traduzioni

L'app è in 6 lingue (italiano, inglese, tedesco, spagnolo, francese, portoghese brasiliano) e le estensioni devono
seguire quella scelta dall'utente. Niente testi scritti nel codice: vanno in un file **`locales.json`** accanto a
`plugin.toml`. È un file solo perché lo store installa soltanto i file in cima alla cartella.

```json
{
  "it": { "pagina": "Anniversari", "anni": "{n} anni", "plugin.name": "Anniversari retro" },
  "en": { "pagina": "Anniversaries", "anni": "{n} years", "plugin.name": "Retro anniversaries" },
  "de": { "…": "…" }
}
```

```js
export default function (gs, ctx) {
  const { t, lang } = ctx;
  gs.addSidebarItem({ id: "anniversari", label: t("pagina"), icon: "◷", view: "anniversari" });
  const quando = new Date().toLocaleDateString(lang, { day: "numeric", month: "long" });  // mai "it" fisso
  gs.toast(t("anni", { n: 30 }));
}
```

- Se manca un testo nella lingua scelta si usa l'inglese, poi l'italiano, poi la chiave stessa.
- I `{segnaposto}` si scrivono come nei cataloghi dell'app.
- Le chiavi `plugin.name`, `plugin.description`, `plugin.long_description`, `plugin.how_it_works` e `plugin.features`
  (una riga per voce) traducono la scheda nello store. Se mancano, lo store usa i testi di `plugin.toml`.
- Lato server `gs.t("chiave", n=3)` fa lo stesso: usa la lingua della richiesta oppure, nei lavori periodici e negli
  eventi, quella dell'ultima richiesta dell'interfaccia. `lang="en"` la forza.
- `python scripts/i18n_check.py` controlla che ogni chiave dell'italiano ci sia in tutte le lingue, con gli stessi segnaposto.

#### Tutorial

Un'estensione può spiegarsi da sola con un tutorial di pochi passi. Il tutorial è facoltativo: se non lo registri,
l'estensione funziona lo stesso.

```js
gs.addTutorial({
  id: ctx.id,                 // uno per estensione: lo store lo trova con l'id dell'estensione
  view: "anniversari",        // parte da solo la prima volta che si apre questa pagina…
  section: "anniversari-sec", // …oppure questa sezione del dettaglio gioco (facoltativo)
  steps: [
    { title: t("tut.1.t"), text: t("tut.1.x") },                         // senza sel: scheda al centro
    { title: t("tut.2.t"), text: t("tut.2.x"), sel: ".ann-lane" },       // indica un elemento della pagina
    { title: t("tut.3.t"), text: t("tut.3.x"), sel: [".badge.ext", "#grid"] }, // il primo selettore che trova
  ],
});
```

- Parte **da solo una volta sola**: la prima volta che l'utente apre la pagina (`view`) o la sezione (`section`).
  Aspetta se è già in corso il tour dell'app o se è aperta una finestra.
- Si rivede quando si vuole: dal pulsante **«?»** nell'intestazione creata da `gs.ui.page` e dal pulsante
  **Tutorial** nella scheda dell'estensione installata nello store. Lo store apre prima la pagina dell'estensione.
- **Impostazioni › Generale › «Rivedi tutti i suggerimenti»** azzera anche i tutorial delle estensioni.
- I passi il cui elemento non c'è vengono saltati. Usa selettori di elementi che esistono anche con la pagina vuota.
- Tienilo corto: 3–5 passi, una frase ciascuno, cosa fa e dove cliccare. I testi vanno in `locales.json`.

#### Componenti dell'interfaccia (`gs.ui`)

Per avere lo stesso aspetto del resto dell'app, usa questi mattoni invece di scrivere stili a mano:

| Funzione | Cosa fa |
|---|---|
| `gs.ui.page(el, {title, subtitle, actions, tutorial})` | Intestazione della pagina con titolo (solo in Big Picture: nella vista normale c'è già nella barra in alto), sottotitolo, pulsanti (`actions`, HTML) e il «?» del tutorial (`tutorial`: id). Restituisce il contenitore del corpo. Le copertine di `gameCard` dentro la pagina aprono il gioco |
| `gs.ui.gameCard(game)` | Copertina con titolo e console, come negli scaffali della home (HTML). Mettine più di una in un `<div class="shelf-lane">` |
| `gs.ui.cover(id, w)` | Indirizzo della copertina di un gioco, larga `w` pixel |
| `gs.ui.empty({icon, title, text, action})` | Stato vuoto (Element): dice cosa manca e cosa fare, con un pulsante facoltativo `{label, run}` |

Classi già pronte: `btn`, `btn primary`, `icon-btn`, `chip`, `badge`, `muted`, `row`, `field`, `shelf-lane`,
`shelf-section`. Per colori, spazi e angoli usa i token del tema (`var(--accent)`, `var(--panel)`, `var(--line)`,
`var(--space-3)`, `var(--radius)`, …) così l'estensione segue temi chiari, scuri e personalizzati. Niente `style="…"`
nell'HTML: le regole vanno in `style.css`, con un prefisso proprio per le classi (es. `ann-`).

#### Linee guida

Prima di pubblicare un'estensione controlla che:

1. **abbia uno scopo che si dice in una frase**, e che non rifaccia qualcosa che l'app fa già (statistiche, lista dei
   desideri, voti, quiz «A cosa vuoi giocare?», note del gioco);
2. **mostri qualcosa, non solo link**: copertine, date, numeri, azioni. Un elenco di collegamenti a siti esterni non è un'estensione;
3. **abbia uno stato vuoto utile**: se non c'è nulla da mostrare, dice perché e cosa fare (`gs.ui.empty`);
4. **funzioni senza chiavi**, oppure spieghi in una riga dove prenderle, con il collegamento giusto;
5. **sia tradotta** (`locales.json`, `ctx.t`, date con `ctx.lang`) e **senza stili in linea**;
6. **abbia un tutorial** di 3–5 passi se non si capisce al primo sguardo.


### Server (backend.py)

```python
def register(gs):
    # endpoint: GET /plugin-api/<id-plugin>/ciao
    @gs.route("ciao")
    def ciao():
        return {"messaggio": "ciao", "impostazioni": gs.settings}

    # eventi: game_started, game_stopped, library_built, scrape_finished, stores_refreshed
    gs.on("game_stopped", lambda info: gs.log(f"{info['title']}: {info.get('played', 0):.0f} secondi"))

    # impostazioni persistenti (in settings.json)
    gs.save_settings({"ultimo_avvio": "oggi"})
```

`gs` mette a disposizione:

| Membro | Cosa fa |
|---|---|
| `gs.route(path, methods=("GET",))` | Espone una funzione su `/plugin-api/<id>/<path>` (FastAPI) |
| `gs.add_store(ClasseStore)` | Aggiunge un **fornitore di libreria**, cioè uno store nuovo: sottoclasse di `pozzo.stores.base.StoreProvider`, con un metodo `fetch()` che restituisce `StoreGame` (installati o da installare, con `launch` e `install_uri`) |
| `gs.add_source(ClasseFonte)` | Aggiunge una **fonte di metadati** per lo scraping: sottoclasse di `pozzo.sources.base.Source`, con `lookup(game)` |
| `gs.on(evento, funzione)` | Reagisce agli eventi del server |
| `gs.job(nome, funzione, every=secondi, run_at_start=False)` | Lavoro periodico: chiama `funzione()` ogni `every` secondi su un thread a parte (vedi sotto) |
| `gs.cfg` | Configurazione (sola lettura) |
| `gs.settings`, `gs.save_settings(dict)` | Impostazioni del plugin |
| `gs.log(msg)` | Scrive nel log |
| `gs.t(chiave, lang=None, **valori)` | Testo tradotto da `locales.json` (vedi «Testi e traduzioni») |

#### Lavori periodici (`gs.job`)

```python
def register(gs):
    def controlla():
        ...  # es. scarica un feed, aggiorna una cache

    gs.job("controllo-feed", controlla, every=3600, run_at_start=True)
```

- `funzione` non riceve argomenti e gira su un thread daemon: non blocca l'avvio dell'app.
- Con `run_at_start=True` il primo giro parte subito, altrimenti dopo `every` secondi (`every` deve essere > 0).
- Un'eccezione dentro `funzione` viene scritta nel log (`Plugin <id>, lavoro <nome>: ...`) e il lavoro continua al giro dopo.
- I lavori si fermano alla chiusura dell'app. `gs.job` restituisce l'oggetto del lavoro: `.stop()` lo ferma prima.
- Nell'elenco dei plugin (`GET /api/extensions`, campo `plugins`) ogni plugin riporta `load_ms` (millisecondi spesi in `register()`) e `jobs` (nome, intervallo, giri fatti, ultimo errore).

#### Caricamento differito (`load = "lazy"`)

Di default il backend si importa e `register()` gira all'avvio dell'app (`load = "eager"`). Con `load = "lazy"` nel `[plugin]` di `plugin.toml` l'app monta solo un segnaposto su `/plugin-api/<id>/...`: al **primo accesso** a una sua route importa `backend.py`, esegue `register()` (una volta sola) e inoltra la richiesta; da lì in poi si comporta come un plugin eager. `frontend.js` e `style.css` sono file statici e si servono come sempre.

- Usalo solo se `register()` usa **soltanto `gs.route`**. `gs.on`, `gs.job`, `gs.add_store` e `gs.add_source` devono essere attivi dall'avvio: in un plugin lazy funzionano, ma solo dopo il primo uso (gli eventi prima di allora si perdono). L'app lo scrive nel log e lo segnala in `eager_needed`: in quel caso togli `load`.
- Un errore in `import`/`register()` di un plugin lazy dà una risposta 500 con il motivo solo sulle sue route (compare anche in `error`); il resto dell'app non ne risente. Il backend non viene riprovato fino al riavvio.
- In `GET /api/extensions` ogni plugin riporta anche `load` (`eager`/`lazy`), `first_use_ms` (import + `register()` al primo accesso, `null` se eager o non ancora usato) e `eager_needed`. `load_ms` per un lazy è il solo montaggio (circa 0).

### Esempio completo

Il plugin **Limite di tempo** (`extensions/limite-tempo/`) usa tutte le parti:
- un backend con endpoint, eventi (gioco avviato e chiuso) e testi tradotti con `gs.t` per le notifiche;
- un frontend con una pagina fatta con `gs.ui.page`, un tutorial di tre passi e i testi in `ctx.t`;
- un `locales.json` nelle 6 lingue, scheda dello store compresa;
- un foglio di stile che usa solo i token del tema.

Per una sezione nel dettaglio del gioco guarda **Diario** (`extensions/diario/`); per uno scaffale nella home
**Anniversari retro** (`extensions/anniversari/`).

### Store delle estensioni

L'app include un solo plugin: lo **Store estensioni** (`pozzo/app/plugins/estensioni/`). È sempre il primo
della barra laterale e di **Impostazioni › Aspetto**, e non si può disattivare. Tutte le altre estensioni si
installano da lì, nella cartella `plugins/` accanto a `config.toml`. Installazione e rimozione valgono subito, senza riavviare l'app. Restano però fino al riavvio gli handler `gs.on`, `add_store` e simili registrati dall'estensione: se qualcosa non compare o non sparisce, riavvia.

Le estensioni arrivano dalle **fonti**, elencate in *Fonti delle estensioni* in cima alla pagina:

- la prima è sempre lo **store ufficiale** ([cartella `extensions/` del repository dell'app](https://github.com/erpaffo/Pozzo-Launcher/tree/main/extensions)) e non si toglie;
- **Aggiungi** accetta il link di un repository GitHub (`https://github.com/utente/repo`, anche `/tree/<tag>`) o
  l'indirizzo https di un `index.json`. Se il link è il repository di un'estensione si aggiunge quell'estensione,
  se è un altro store si aggiunge tutto il suo elenco. L'app controlla che il link risponda e contenga estensioni;
- se la stessa estensione è in più fonti vince lo store ufficiale; quelle di altre fonti mostrano «da utente/repo».

Ogni estensione ha il suo `index.json` con l'elenco dei file e il loro sha256. Nello Store estensioni ogni estensione
mostra un'**anteprima grafica (screenshot)**, la descrizione accurata e i badge delle funzionalità principali.
Facendo clic su una card (o sul pulsante **ℹ️ Dettagli**) si apre una **scheda modale approfondita** che illustra:
- la versione dell'estensione, l'autore e la versione minima richiesta di Pozzo Launcher;
- uno screenshot ad alta risoluzione del plugin in azione nell'interfaccia;
- la descrizione completa degli scopi dell'estensione;
- la sezione **«Come funziona e dove trovarla»**, con i passaggi guidati e l'indicazione precisa di dove compaiono voci di menu, pulsanti o impostazioni;
- l'elenco puntato di tutte le caratteristiche salienti e le specifiche tecniche: file inclusi, origine e **permessi** dichiarati
  dall'estensione (per esempio accesso alla rete, lettura della libreria), con in evidenza quelli sensibili (scrittura su disco,
  accesso ai file, avvio di programmi). Un'estensione che non dichiara i permessi viene segnalata come tale.

Prima di installare l'app mostra i permessi e chiede conferma. Su un aggiornamento chiede conferma solo se la nuova versione
aggiunge permessi rispetto a quella installata (quando l'app conosce quella installata). Le card riportano il numero di permessi.

Dalla scheda dettagli è inoltre possibile installare, aggiornare o rimuovere direttamente l'estensione. L'installazione scarica i file uno per
uno e scrive su disco solo se **tutti** corrispondono. Rifiuta anche nomi di file con percorsi, sottocartelle e versioni
dell'app più vecchie di `min_app`. Lo sha256 garantisce che i file siano quelli dell'indice, non che l'estensione sia
affidabile: le estensioni di fonti di terzi eseguono codice sul PC, quindi aggiungi solo fonti di cui ti fidi.
Un'estensione collegata alla cartella di sviluppo (vedi sotto) non viene mai aggiornata né cancellata dallo store.

Per provare uno store diverso al posto di quello ufficiale, anche da disco prima del push, imposta in `settings.json`:
`"app": {"extensions_index": "C:/percorso/store/index.json"}`.

![Lo Store estensioni: le estensioni disponibili con descrizione e pulsante Installa](images/plugin-estensioni.jpg)

### Pubblicare un'estensione

Ogni estensione vive nel **proprio repository** (per esempio `pozzo-ext-diario`): in cima ci sono
`plugin.toml`, i file dell'estensione (niente sottocartelle) e `index.json`. Lo store ufficiale è un altro repository
con un solo `index.json`, che elenca i repository e la versione approvata di ciascuno:

```json
{"version": 1, "repos": [{"repo": "erpaffo/gamescraper-ext-diario", "ref": "v1.0"}]}
```

L'app legge l'`index.json` di ogni repository a quel tag. Una voce può anche indicare `"url"` al posto di
`repo`/`ref`, per un indice che non sta su GitHub.

Per pubblicare una versione:

1. In `plugin.toml` alza `version` e, se usa funzioni nuove dell'app, `min_app = "x.y.z"`.
2. Rigenera l'indice dal repository dell'estensione: `python <Pozzo Launcher>/tools/extensions.py index .`
3. Commit, tag `v<versione>` e push.
4. Nello store porta `ref` al tag nuovo (una pull request sul repository dello store). Chi ha aggiunto il repository
   dell'estensione come fonte la vede invece subito, perché quel link segue il ramo principale.

I repository hanno i fine riga fissati a LF (`.gitattributes`): lo sha256 nell'indice è quello dei file come li serve GitHub.

**Dal repository dell'app ai repository separati**: `python tools/extensions.py export <cartella> <utente>` crea in
`<cartella>` un repository pronto per ogni estensione di `extensions/` (file, `index.json`, README, licenza) e quello
dello store, che punta a `<utente>/pozzo-ext-<id>` al tag `v<versione>`.

Per provare un'estensione nell'app, `python tools/extensions.py install [<cartella>]` la **copia** nella tua cartella
`plugins/`: senza argomento quelle di `extensions/`, altrimenti quelle della cartella indicata (una cartella con i
repository clonati, oppure una sola estensione). Dopo ogni modifica va rifatto, e riavviata l'app. Non si usano
collegamenti (junction o symlink): l'app installata non attraversa quelli che puntano dentro OneDrive e
non parte (WinError 448). La release contiene solo lo store.

### Estensioni disponibili

| Plugin | Cosa fa |
|---|---|
| **Link → Store** | procedura in tre passi: incolli l'indirizzo di una pagina che raccoglie altri siti, scegli i link a gruppi e la console di ogni gruppo (proposta dal titolo) o lo store PC; con «Leggi subito» gli elenchi si scaricano appena aggiunti |
| **Store Minerva + Switch** | «Importa store» aggiunge allo Store online gli archivi di minerva-archive.org (elencati da r-roms) e gli store preimpostati Switch, Switch 2, PS4 e PS5; poi una scheda per console con icona, giochi letti e «Leggi» |
| **Anniversari retro** | badge «N ANNI» sui festeggiati di oggi, scaffale «Compiono gli anni» nella home e pagina con oggi e i prossimi 30 giorni, giorno per giorno (servono le date di uscita complete) |
| **Pulizia libreria** | riquadri con quanto c'è da sistemare (doppioni, mai avviati, fermi da anni, dati mancanti, file identici su disco), copertine da selezionare con azioni di gruppo, badge «DUP» e rimozione dei doppioni aggiunti a mano |
| **Diario di gioco** | nella scheda di ogni gioco una linea del tempo per giorno con partite, note datate, schermate e copie dei salvataggi (si affianca alla nota personale del gioco) |
| **Limite di tempo** | pagina «Tempo di gioco»: tempo di oggi su un anello, settimana in un grafico con la linea del limite, avviso 10 minuti prima e, a scelta, chiusura del gioco a tempo scaduto |
| **Obiettivi personali** | sfide proposte dalla libreria da accettare con un clic (finisci un gioco iniziato, prova una console mai usata), obiettivi con anello di avanzamento, serie di giorni e distintivi |
| **Riepilogo annuale** | «Il tuo anno»: il tuo anno di gioco come storia a schermo intero (ore, gioco dell'anno, classifica, abitudini, record) e un'immagine da condividere; i numeri completi restano in Statistiche |
| **SteamGridDB** | fonte di copertine verticali, sfondi e logo mancanti; chiave gratuita in Impostazioni › Estensioni › SteamGridDB. Alimenta anche **Immagini del gioco…** del menu del tasto destro |
| **Calendario uscite** | calendario mese per mese con le copertine dei giochi in uscita: prima la lista dei desideri, poi i tuoi generi (o tutti); aggiunta ai desideri con un clic. Usa la chiave RAWG di Impostazioni › Libreria e fonti |
| **Notizie videogiochi** | timeline di notizie da case e siti, filtro «Solo i miei giochi e console», tipi (annuncio, patch, DLC, uscita), rassegna del lunedì, giochi seguiti con patch e DLC nella scheda e in uno scaffale della home |
| **Il mio PC ce la fa?** | nella scheda del gioco un semaforo e tre indicatori (processore, scheda video, memoria) con minimo e consigliato, dai requisiti Steam o dell'emulatore, e le impostazioni consigliate |
| **Media locale** | film, serie e musica dalle cartelle del tuo computer sfogliati come una libreria multimediale: riconoscimento dei nomi, poster locali (poster.jpg, folder.jpg), ripresa della riproduzione e supporto per lettore integrato o esterno |
| **Ricette web** | cataloghi di film e podcast da siti e feed web leciti (es. Internet Archive e podcast NASA) estratti tramite ricette TOML dichiarative senza codice eseguito; cache con ETag, rispetto di robots.txt, dettaglio, episodi e riproduzione |
| **Twitch e YouTube** | nella scheda del gioco video YouTube da guardare lì e dirette Twitch in corso; senza chiavi spiega come attivarlo e offre la ricerca nel browser |
| **Media server** | le librerie del tuo Jellyfin o Plex dentro Pozzo Launcher: stessa griglia, stessa ricerca, «continua a guardare» e «visto» sincronizzati col server |

**Store Minerva + Switch** tiene i preset in `PRESETS` (`backend.py`): per aggiungerne altri basta una riga
(`{"console": ["https://…"]}`). Poiché gli elenchi della stessa console possono avere formati diversi
(`type_b`, `type_c`, `type_d`), quando una console ha più di un indirizzo il `type` fisso viene rimosso:
ogni pagina viene riconosciuta da sola da `catalog.detect_kind`.

**Link → Store** è anche un esempio di plugin che **scrive nelle impostazioni**: usa le stesse funzioni
dell'interfaccia (`config.set_setting`) e quindi le modifiche valgono subito, senza riavviare l'app.
La logica di lettura della pagina sta in `pozzo/linklist.py` (`scan_page`, `add_store`), fuori dal
plugin, così è testabile senza avviare il server.

**Media locale** e **Ricette web** sono estensioni per **Pozzo Media** (`api = 2`): operano su una propria cache separata dalla libreria dei giochi. **Media locale** richiede il permesso `media:lettura` per scansionare solo le cartelle multimediali scelte dall'utente. **Ricette web** supporta ricette dichiarative per pagine HTML, podcast RSS e API JSON, proteggendo il sistema con il divieto assoluto di codice eseguibile e limitando l'accesso di rete agli host autorizzati.

Nella vista Media il pannello **Sorgenti** raccoglie in un posto solo cartelle locali, server Jellyfin/Plex (utente e password oppure token), Kodi/Stream4me, Ricette web (con «Aggiorna catalogo») e metadati. La ricerca interroga le sorgenti insieme con un timeout di 2 secondi ciascuna: i risultati arrivano man mano, un titolo presente in più sorgenti compare una volta con più badge, e un chip per sorgente mostra se ha risposto. Il catalogo di Ricette web/Stream4me è servito dalla cache locale a pagine e si aggiorna in background o col pulsante «Aggiorna catalogo». Funzione provata solo con test automatici, da verificare a mano nel launcher.

### Sicurezza

Un plugin con `backend.py` gira con gli stessi permessi dell'app: può leggere e scrivere file e avviare programmi. Installa solo plugin di cui ti fidi e di cui puoi leggere il codice.

### Content Security Policy

L'app applica una Content Security Policy: il browser esegue solo gli script che arrivano da file e ignora i gestori inline. Per la tua estensione:

- nell'HTML generato niente `<script>` e niente `onclick=`, `onchange=`, `onerror=` e simili: usa `addEventListener` oppure la delega su un contenitore (un ascoltatore sul genitore che controlla `e.target`).
- per le immagini che possono rompersi usa `data-onerr="remove"`, `"hide"` (lascia lo spazio), `"parent"` (toglie il contenitore) o `"text"`; con `data-fb="url"` riprova una volta con un altro indirizzo.
- con `"text"` il testo va in `data-onerr-text`, il tag in `data-onerr-tag` (predefinito `span`), la classe in `data-onerr-class` e lo stile in `data-onerr-style`.
- dalla prossima versione le estensioni che usano gestori inline smettono di funzionare: aggiornale prima del rilascio.
