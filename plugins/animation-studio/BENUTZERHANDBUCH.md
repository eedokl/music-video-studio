# animation-studio – Benutzerhandbuch

Dieses Handbuch beschreibt das Claude-Code-Plugin **animation-studio** (Version 0.5.4) aus Sicht der Person, die
damit Filme machen will. Sie sprechen mit Claude auf Deutsch, Claude führt alle Skripte selbst aus. Sie müssen
also keine Befehle tippen. Wichtig ist, dass Sie wissen,

- was Sie verlangen können,
- was Claude Sie fragen wird,
- wo Sie zwischendurch entscheiden und steuern,
- welche Dateien am Ende herauskommen.

Die technischen Details (Skripte, Optionen, Dateiformate) stehen in `README.md`, `TOOLS.md`, den
`skills/*/SKILL.md` und den Bausteinbeschreibungen `skills/*/BLOCK.md` im Plugin-Ordner. Dieses Handbuch nennt
Dateinamen und Schlüssel nur dort, wo sie Ihnen beim Steuern helfen.

## Inhalt

1. Überblick
2. Installation und erster Start
3. Die Filmarten im Einzelnen
   - 3.1 Zeichentrick-Musikvideo (`animated-music-video`)
   - 3.2 Brickfilm-Musikvideo (`bricks-music-video`)
   - 3.3 3D-Figurenfilm (`animated-3d-film`)
   - 3.4 Lyric-Video (`lyric-music-video`)
   - 3.5 Claudia-Musikvideo (`claudia-music-video`)
   - 3.6 Animierte Präsentationsfiguren (`animated-powerpoint`)
   - 3.7 Sprechende Figuren (`talking-character`)
   - 3.8 Kurze 2D-Szenen und Übungen (`animated-short`)
   - 3.9 Schnelle Nachbearbeitung (`film-tools`)
   - 3.10 Versionen vergleichen (`video-review`)
4. Gemeinsame Konzepte
5. Tipps und Grenzen
6. FAQ und Problemlösung

---

## 1. Überblick

animation-studio macht auf Ihrem eigenen Rechner Musikvideos und kurze Animationsfilme: klassische
2D-Zeichentrickfilme, in denen Figuren wirklich singen, Brickfilme aus Klemmbausteinen, 3D-Figurenfilme im Look
einer hochwertigen Werbung, typografische Lyric-Videos, fotorealistische KI-Sängerinnen-Videos mit Claudia,
lebendig gewordene Präsentationsfiguren, sprechende Figuren und kurze 2D-Szenen.

Jede Filmart ist ein eigener **Skill**. Sie müssen den Skill nicht beim Namen nennen: Wenn Sie sagen „Mach daraus
ein Zeichentrick-Musikvideo“ oder „Claudia soll diesen Song singen“, wählt Claude den passenden Skill selbst.
Was zwei Filmarten gemeinsam brauchen (Song-Analyse, Lippensynchronität, Stimmen, Schnitt, Film-Look), liegt
einmal in einem **Baustein** und wird von allen Skills genutzt.

### Die Filmarten auf einen Blick

| Skill | Was herauskommt | Typische Länge / Aufwand | Grafikkarte nötig? |
|---|---|---|---|
| `animated-music-video` | 2D-Zeichentrick-Musikvideo: Tim, Lia und der Computer (oder eigene Figuren) singen den Song, mit Lippensynchronität, Tanz im Takt, Gesten, Gags, Liedtext, Geräuschen und Übergängen; jede Szene als bearbeitbare Synfig-Datei | Standard ist ein Refrain als Pilot; ein ganzer Song bedeutet Stunden an Iterationen | Nein (Whisper und Demucs laufen auf der GPU schneller, haben aber CPU-Ausweichwege); nur für gemalte KI-Hintergründe ja |
| `bricks-music-video` | Brickfilm (Stop-Motion mit Minifiguren) aus der LDraw-Bibliothek in Blender, mit Lippensynchronität, Gesten, Bausteineffekten und Comic-Schrift | Abschnitt oder ganzer Song; Rendern mit EEVEE ca. 0,4–0,6 s pro Bild | Empfohlen (Blender rendert auf der GPU) |
| `animated-3d-film` | 3D-Film mit weichen Spielzeugfiguren (Bär, Katze, Hase oder eigene Figuren), die spielen und sprechen; echtes Licht, Nahaufnahmen, Kino-Look | 30–90 s sind eine gute Größe; Vorschau ca. 1 Stunde für 4 Minuten Film, Filmqualität etwa fünfmal so lang | Praktisch ja (Cycles auf der GPU; die CPU geht, ist aber langsam) |
| `lyric-music-video` | Typografie-Video: jeder Buchstabe landet genau, wenn er gesungen wird; jede Zeile bekommt eine eigene Bildidee, jedes Video eine neue visuelle Identität | Ganzer Song; Endrender ca. 6–10 min für 3–4 min Song | Optional |
| `claudia-music-video` | Fotorealistisches KI-Musikvideo mit der Sängerin Claudia, als Studio-/Story-Video oder als Live-Konzertvideo | Ganzer Song oder Pilot; ein 3-Minuten-Song braucht ca. 4–7 Stunden Nachtlauf | Ja (ComfyUI mit lokalen KI-Modellen; gemessen auf 16 GB Grafikspeicher) |
| `animated-powerpoint` | Figuren aus Folien steigen aus der Folie, landen, gestikulieren und sprechen; Clips, die nahtlos zurück in die Präsentation passen | 8-s-Clip ca. 1,5 min Bauzeit; 25-s-Clip mit vier Figuren ca. 25 min | Optional (Hochskalieren mit Real-ESRGAN nutzt die GPU, sonst Lanczos) |
| `talking-character` | Dialogszene im Zeichentrickstil: Text oder Aufnahme wird zu Stimmen mit Lippensynchronität, Blicken, Gesten, Untertiteln | Standard 15–20 s | Empfohlen für die Qwen3-TTS-Stimmen; ohne GPU sprechen Piper oder die Windows-Stimme |
| `animated-short` | Kurze 2D-Szene ohne Song: hüpfender Ball, Mehlsack, Take, Pip findet eine Blume, Fips-Gag, Multiplane-Flug, Comic-Flug | 3–10 s (Standard ca. 6 s) | Nein |
| `film-tools` | Schnelle Arbeiten an fertigen Videos: Film-Look, kleine Versionen für Upload und E-Mail, Kontaktabzug, Decodier-Prüfung, Clips zu einem Film schneiden | Minuten | Nein |
| `video-review` | Mehrere Versionen desselben Films Schnitt für Schnitt vergleichen und aus den besten Einstellungen eine neue Version schneiden, ohne neu zu rendern | Minuten | Nein |

### Wie ein Film entsteht (gemeinsames Muster)

Alle Skills folgen demselben Ablauf:

1. **Interview**: Claude stellt eine Runde Fragen zu dem, was noch fehlt (Song, Liedtext, Stems, welcher Teil,
   Besetzung, Zweck, Ihre Ideen).
2. **Hören oder Lesen**: Claude analysiert den Song (oder liest das Skript, die Präsentation).
3. **Kreatives Briefing**: Claude erfindet Ideen zu *diesem* Song oder Text und zeigt Ihnen einen kurzen Plan.
   Ihre Ideen gehen immer vor.
4. **Bauen**: Abschnitt für Abschnitt oder Einstellung für Einstellung. Claude schaut sich Kontaktabzüge selbst an,
   bevor es Ihnen etwas zeigt.
5. **Prüfpunkte**: Sie entscheiden – wer welche Zeile singt, Startbilder, Standbilder, Vorschauen. Ihr Ohr und Ihr
   Auge gewinnen immer.
6. **Fertigstellen**: Schnitt, Film-Look und Ausgabeversionen, jede auf Decodierfehler geprüft. Mit `video-review`
   lassen sich Versionen vergleichen.

---

## 2. Installation und erster Start

### 2.1 Plugin installieren

Das GitHub-Repository enthält einen Marketplace. In einem Terminal:

```
claude plugin marketplace add eedokl/music-video-studio
claude plugin install animation-studio@music-video-studio
```

Alternativ aus einer lokalen Kopie: den Ordner mit `.claude-plugin/marketplace.json` als Marketplace hinzufügen
(`claude plugin marketplace add <Ordner>`) und dann genauso installieren. Ein lokaler Marketplace lädt das Plugin
direkt aus dem Ordner; Änderungen wirken nach `/reload-plugins`.

Updates: Installierte Nutzer bekommen ein Update nur, wenn sich die Versionsnummer des Plugins ändert.

### 2.2 Erster Start: die Werkzeugprüfung

Sagen Sie Claude einmal pro Rechner:

```
Richte animation-studio ein.
```

Claude startet dann die Werkzeugprüfung von studio-core (`check_tools.py --setup`). Sie müssen nicht wissen, wo der
Plugin-Ordner liegt. Die Prüfung

- sucht die installierten Programme (im PATH und in den üblichen Installationsordnern),
- schreibt das Ergebnis nach `~/.animation-studio/config.json`, also außerhalb des Plugins, damit es Updates
  übersteht,
- listet fehlende Werkzeuge mit Installationshinweisen auf.

**Claude installiert nichts, ohne zu fragen.** Es zeigt Ihnen, was fehlt und wofür es gebraucht wird, und fragt.
Fehlt nur ein optionales Werkzeug, sagt Claude das in einem Satz (zum Beispiel: ohne earshot keine
Mann/Frau-Erkennung und keine Geräuscheffekte) und arbeitet weiter.

Programmpfade lassen sich auch von Hand setzen (Claude macht das mit `check_tools.py --set schlüssel=wert`) oder
über Umgebungsvariablen der Form `ANIMATION_STUDIO_<SCHLÜSSEL>`. Auf Linux und macOS durchsucht die automatische
Suche nur den PATH; dort setzt Claude die Pfade bei Bedarf von Hand.

### 2.3 Benötigte Programme

Die vollständige Liste mit Versionen steht in `TOOLS.md`. Kurzfassung:

| Programm | Wofür | Status |
|---|---|---|
| uv | startet jedes Skript in seiner eigenen Python-Umgebung und lädt Python-Pakete bei Bedarf | erforderlich |
| ffmpeg mit libx264 | Decodieren, Schneiden, Mischen, Kodieren, Prüfen | erforderlich |
| Rhubarb Lip Sync | Mundformen aus Gesang oder Sprache, sprachunabhängig | erforderlich für alle singenden und sprechenden Figuren |
| Synfig Studio (synfig-CLI) | 2D-Szenen als bearbeitbare `.sif`-Dateien | erforderlich für die 2D-Skills |
| Inkscape | SVG-Figuren in Pfade für das Synfig-Rig umwandeln | erforderlich für die 2D-Skills |
| Blender (getestet 5.2 LTS, auch 5.3) | Brickfilme (EEVEE), 3D-Figurenfilme (Cycles) | erforderlich für Brick- und 3D-Filme |
| LDraw-Teilebibliothek | Bausteingeometrie (ca. 150 MB, nicht im Plugin enthalten) | erforderlich für Brickfilme |
| Node.js 20+ mit npm, headless Chrome/Edge | Lyric-Videos (three.js), Multiplane-Kamera, Comic-Flug, Folienbühne | erforderlich für diese Teile |
| earshot | wer singt (Mann/Frau), Lautheits- und Zeitachsenprüfung, Bank mit 252 Geräuscheffekten | empfohlen |
| ComfyUI | führt die lokalen Bild- und Videomodelle aus | erforderlich für KI-Video (Claudia) |
| Microsoft PowerPoint oder PyMuPDF | Präsentationen importieren | empfohlen für `.pptx` |
| Krita | gemalte Hintergründe als `.kra` zum Übermalen | optional |
| Kdenlive mit melt + OpenTimelineIO | Übergabe des fertigen Schnitts zur Handbearbeitung | optional |
| Real-ESRGAN, RIFE | Hochskalieren, 48-fps-Fassung | optional |

### 2.4 Grafikkarte und KI-Modelle – was Sie wissen sollten

- **Alles läuft lokal.** Die KI-Modelle (Whisper für Wörter, Demucs für Gesangstrennung, FLUX für Bilder,
  Qwen-Image-Edit für Claudia-Startbilder, LTX-2.3 und andere für Video, Qwen3-TTS für Stimmen, Depth Anything für
  Tiefenkarten) laufen auf Ihrem Rechner. Die meisten Bild- und Videomodelle laufen über ComfyUI.
- **Ein KI-Modell zur Zeit.** Alle Skills teilen sich eine GPU-Sperre. Auf dem Referenzrechner (16 GB
  Grafikspeicher, 48 GB Arbeitsspeicher) passen zwei große Modelle nicht gleichzeitig hinein. Startet ein zweiter KI-Job, wartet er, bis
  der erste fertig ist. Claude löscht nie die Sperre eines anderen Jobs.
- **Modelle sind groß** (5–25 GB je Modell) und nicht im Plugin enthalten. Claude kann den Modell-Cache auf ein
  Laufwerk mit genug Platz legen (Schlüssel `hf_home` / `torch_home`). Heruntergeladen wird nur mit Ihrer
  Zustimmung.
- **Vor einem langen KI-Lauf prüft Claude ComfyUI** (Preflight): Fehlen Knoten, Modelldateien oder Optionen, sagt
  es genau, was fehlt, statt nach Stunden abzubrechen. Heißen Ihre Modelldateien anders als auf dem Referenzrechner,
  legt Claude eine kleine Override-Datei an (Schlüssel `comfy_models`), statt Plugin-Dateien zu ändern.
- **Python-Pakete** lädt uv beim ersten Lauf eines Skripts einmal in seinen Cache. Danach geht es offline.
- **Zeitangaben** in diesem Handbuch stammen vom Referenzrechner (Windows 11, RTX 5060 Ti mit 16 GB Grafikspeicher, 48 GB Arbeitsspeicher). Auf
  anderer Hardware kann es deutlich schneller oder langsamer gehen.

### 2.5 Was nur unter Windows geht

Fast alles läuft auch unter Linux und macOS, wenn uv, ffmpeg und die Programme dort laufen. Nur unter Windows:

| Funktion | Ersatz auf anderen Systemen |
|---|---|
| Folienexport aus `.pptx` über PowerPoint | Präsentation als PDF oder PNG exportieren und diese importieren |
| Windows-Sprachausgabe als Stimme | Qwen3-TTS oder Piper |
| automatische Programmsuche von `check_tools.py --setup` | Pfade von Hand setzen |
| `.cmd`-/`.bat`-Starter (earshot, ComfyUI-Startskript) | Shell-Skript oder Programmdatei angeben |
| Windows-Schriften (Impact, Segoe Print, Consolas) | macOS-Schriften oder DejaVu; die Schrift sieht dann anders aus |

---

## 3. Die Filmarten im Einzelnen

### 3.1 Zeichentrick-Musikvideo (`animated-music-video`)

**Wann:** Sie haben einen Song und möchten, dass Zeichentrickfiguren ihn singen – Tim, Lia und der Computer oder
Ihre eigenen Figuren. Auch zum Weiterbauen oder Reparieren eines solchen Videos.

**Was Sie mitbringen:**

- den **Song** (wav oder mp3),
- den **Liedtext**, am besten mit Abschnittsmarken wie `[Chorus]`, `[Verse 1 - Tim, male lead]`,
  `[Spoken - narrator]`,
- **Suno-Stems** (Vocals und Backing Vocals), falls der Song von Suno stammt – sie verbessern Lippen und
  Ruf-und-Antwort-Stellen deutlich,
- **welcher Teil**: Standard ist ein Refrain als Pilot, denn ein ganzer Song bedeutet Stunden an Iterationen,
- die **Besetzung**: Tim, Lia, Computer oder eigene Figuren als Inkscape-SVG (nach der Rig-Konvention, siehe 3.7),
- worum es im Song geht und Ihre Ideen.

**Ablauf aus Ihrer Sicht:**

1. *Interview*: eine Fragerunde.
2. *Hören*: Claude legt ein Song-Projekt an und analysiert Takt, Wörter, Mundformen und Stimmlage. Ergebnis ist ein
   Songblatt (`analysis/song_sheet.png`).
3. **Prüfpunkt „Wer singt was“**: Claude zeigt Ihnen `analysis/lines.csv` – welche Figur welche Zeile singt – und
   bittet Sie, reinzuhören. Ihr Ohr gewinnt: Korrekturen landen in `corrections.json` und überstehen jeden
   weiteren Lauf.
4. *Kreatives Briefing*: Claude liest den Text Zeile für Zeile und erfindet Bilder, Requisiten, Gags und
   Reaktionen für genau diesen Song. Es zeigt Ihnen einen kurzen Plan (pro Abschnitt eine Zeile: Kulisse, wer,
   2–3 Ideen) und macht weiter, wenn Sie nicht mitreden wollen.
5. *Bauen*: Szene pro Abschnitt, dann Text-Overlays, dann Geräusche. Claude schaut sich zuerst selbst einen
   Kontaktabzug an (Figuren im Bild, Münder offen beim Singen, Gags lesbar, nichts wiederholt sich mechanisch).
6. **Prüfpunkt Vorschau**: eine Vorschau des Abschnitts (`preview/<abschnitt>.mp4`), danach der ganze Film.

**Was Sie steuern können** (einfach in Worten sagen, Claude trägt es in `project.json` ein):

| Bereich | Möglichkeiten |
|---|---|
| Kulissen | `stage` (Bühne, Bildschirm hinten), `room` (nächtliches Zimmer mit Schreibtisch und Monitor), eine einfarbige Fläche, eigene gemalte Kulissen (Krita oder FLUX) |
| Tanz | im Refrain, immer oder nie; Tanzstil pro Figur (Arme, Wippen, Schritt, Drehung) |
| Gesten auf Wörtern | erschrecken, jubeln, zeigen, kratzen, nicken, traurig |
| Gesichtsausdrücke | Grinsen, skeptisch, Schock, wütend, traurig – auf einem Wort, einer Zeile oder einer Zeitspanne |
| Acting | Zuhörer drehen sich zum Sänger, nicken, Brauen springen bei Gags; ideal für Strophen und dialogartige Songs |
| Gags | kurze Ausrufe (Comic-Schrift) oder Bildsymbole (Geld, Chip, Kuss, Herz, Pfeil, Stern, Blitz, eigenes Bild) auf einem Wort |
| Computer-Bildschirm | Text statt Gesicht (Terminalzeilen, Preise, Warnungen), Einfärben (z. B. rot ab einem Wort), Abzeichen in der Ecke (FREE → PRO), Verbrauchsbalken, aufpoppende App-Fenster |
| Aktionen | tippen, Luftgitarre – beim Zuhören, beim Singen oder auf einer Zeile |
| Licht | Spotlight, Disco, Nacht (Raum wird dunkel) |
| Weiteres | Requisiten auf einem Wort, Silhouetten im Fenster, rundes Einblendfenster mit einer Figur, Herzschlag-Kamera, Dampf aus dem Kopf, Comic-Seite mit Panels, Nahaufnahme des Bildschirms |
| Übergänge | Zoom durch Fenster/Tür/Bildschirm, warmes Licht, Kamerafahrt in den Bildschirm, Iris, weißer Blitz, kurze Schwarzblende |
| Liedtext | Zeile unten im Bild, Stile `script`, `caps`, `pop`, `rock`, `whisper`; einzelne Zeilen auslassen oder anders gestalten |
| Titel | Text, Position, Größe, Pop-Animation, Ausblenden |

Wortauslöser funktionieren standardmäßig als Wortanfang („token“ trifft „Tokens!“). Für genaue Treffer gibt es
`"=pro"` (nur genau dieses Wort) und reguläre Ausdrücke.

**Optionale Zusatzfassungen:**

- **48-fps-Film** (braucht RIFE; Claude fragt vor der Installation),
- **Pop-up-Video** mit Making-of-Karten im Stil der 80er-„Pop-up Videos“,
- **Abspann** mit Gags, Filmausschnitten, Outtakes und einer Szene nach dem Abspann,
- **zweite Tonspur** in einer anderen Sprache (eine andere Fassung des Songs, mit einem einzigen Zeitversatz),
- **Untertitel** als SRT/VTT oder eingebrannt,
- **Übergabe an Kdenlive** (`film.otio`, `film.mlt`) für den Handschnitt.

**Ergebnisse:**

- `film.mp4` (volle Qualität), `film_small.mp4` (unter 30 MB), `film_mail.mp4` (ca. 12 MB),
- `preview/<abschnitt>.mp4` pro Abschnitt,
- je nach Wunsch `film_48fps.mp4`, `film_popup.mp4`, `credits.mp4`, `film_with_credits.mp4`, `film_en.mp4`,
- jede Szene als `.sif`, die sich in Synfig Studio von Hand weiteranimieren lässt.

**Nachträglich ändern:** Alles hängt an den Sekunden des Songs, daher lässt sich jeder Abschnitt einzeln neu bauen.
Sagen Sie einfach, was anders sein soll; Claude baut nur den betroffenen Teil neu. Steht ein Wort zur falschen Zeit
im Bild, ergänzt Claude den fehlenden Ruf im Liedtext und analysiert neu oder korrigiert die Zeit von Hand. Die
Münder kommen aus dem Gesang und ändern sich dabei nicht. Ein **neuer Seed** ergibt eine neue Variante (anderer
Tanzstil, andere Blinkzeiten usw.), derselbe Seed denselben Film.

**Typische Probleme:**

- Ein Ausschnitt des Songs braucht einen auf die gesungenen Zeilen gekürzten Liedtext, sonst stimmen die Wortzeiten
  nicht (Claude kürzt ihn und das Skript warnt).
- Kurze Rufe hört Whisper schlecht. Mit Stems kommen ihre Zeiten aus dem Backing-Vocals-Track.
- Geflüsterte Zeilen lassen sich nicht automatisch Mann oder Frau zuordnen; dort entscheidet die Abschnittsmarke
  im Liedtext.
- Suno-Songs halten sich nicht zuverlässig an Regieanweisungen im Liedtext – deshalb entscheidet der Klang, wer
  singt, und Ihr Ohr korrigiert.
- Lücken zwischen Abschnitten werden schwarz – Abschnitte sollen sich berühren.
- Projekte von vor Version 0.4.19 tanzen beim Neurendern anders (seitdem wählt der Seed einen Tanzstil pro Figur
  für den ganzen Film). Soll ein alter Film bleiben, wie er war, lässt Claude die alten Tanzstile festschreiben.

**Beispiel-Prompts:**

```
Mach aus song.wav mit lyrics.txt ein Zeichentrick-Musikvideo mit Tim und Lia, nur den ersten Refrain als Pilot.
```

```
Hier sind noch die Suno-Stems vocals.wav und backing.wav – nimm die für die Lippen und die Rufe.
```

```
Die Zeile „Nur noch mehr“ singt Lia, nicht Tim. Und die Rufe in Klammern soll der Computer übernehmen.
```

```
Im Refrain soll Lia auf das Wort „Prompts“ zeigen, und bei „GPU“ soll der Bildschirm des Computers rot werden
und „GPU 100 %“ anzeigen.
```

```
Die erste Strophe soll im Zimmer bei Nacht spielen, mit Acting: Tim tippt beim Zuhören, und beim Wechsel in den
Refrain zoomen wir durchs Fenster auf die Bühne. Im letzten Refrain Disco-Licht mit Konfetti.
```

```
Jetzt bitte den ganzen Song. Dazu einen Abspann mit Outtakes, eine 48-fps-Fassung und die englische Version
english.wav als zweite Tonspur.
```

---

### 3.2 Brickfilm-Musikvideo (`bricks-music-video`)

**Wann:** Sie möchten einen Song (oder einen Teil davon) als Stop-Motion-Film mit Minifiguren aus Klemmbausteinen.
Die Figuren singen mit Lippensynchronität, gestikulieren auf Wörtern und wippen im Takt. Es werden nur eigene
Figuren verwendet, und der Film heißt nie „LEGO“-Film; die LDraw-Noppen tragen kein Logo.

**Was Sie mitbringen:** Song (plus Liedtext und Stems, falls vorhanden), welchen Teil (ganzer Song oder Ausschnitt
als Pilot), wer die Figuren sind (Tim und Lia als Standard oder eigene: Shirtfarbe, Haare, Brille …) und was Sie
sich schon vorstellen. Eine Abschnittsmarke wie `[Verse 3 - Tim, male lead]` über den Zeilen hilft bei der
Zuordnung, wer singt.

**Einmal pro Rechner:** Blender und die LDraw-Bibliothek (kostenlos, ca. 150 MB). Claude prüft beides vor dem
ersten Film; den Download der Bibliothek erledigen Sie oder Claude nach Ihrer Zustimmung.

**Ablauf aus Ihrer Sicht:**

1. *Interview* (kurz).
2. *Song-Analyse* und **Prüfpunkt „Wer singt was“** (`analysis/lines.csv`, Korrekturen in `corrections.json`).
3. *Kreatives Briefing*: Claude erfindet Bilder aus diesem Song und schreibt sie ins Projekt, unter anderem:
   - **Kulisse pro Abschnitt**: Zimmer, Bühne, Dach, Haus (Nachtansicht mit Kameraflug durch den Garten ins
     Fenster), Arena (Siegerpodest, Tribünen, Chip-Berg), Wolke (Auktion über den Wolken),
   - **Gesten auf Wörtern**, zum Beispiel auf die Brust, Arme öffnen, zeigen, in die Kamera zeigen, greifen,
     Schultern zucken, jubeln, Faust, Kopfschütteln, tippen, lachen, erschrecken, schauen, zusammensacken,
     Kusshand, winken, kratzen, nicken, springen, Marionette und Puppenspieler,
   - **Requisiten und Bausteineffekte**: Cameo-Figur am Fenster (etwa eine anonyme Silhouette mit weißem Grinsen),
     wachsender Münzstapel, fliegende Haare, abspringender Kopf, Licht aus, ein Wort aus fliegenden Steinen, das
     später zusammenfällt, Konfetti, wachsender Turm, Figur fällt auseinander oder baut sich zusammen, Dampf aus dem
     Kopf, Marionettenfäden, verschwindende Münzen,
   - **Namensschilder** auf Robotern (neutrale Schrift, nie Logos),
   - **Kulissenwechsel**: Kulisse baut sich aus fliegenden Steinen auf oder fliegt auseinander,
   - **Monitorbildschirme** (Text, Terminal, Herz, Code, Balken) und **Comic-Schrift** auf Schlüsselwörtern,
   - ein **Schlussbild** für den letzten Abschnitt.
4. **Prüfpunkt Standbilder**: Vor dem Rendern zeigt Claude Ihnen einige Standbilder des Abschnitts: Bildausschnitt,
   scharfe Gesichter, nichts weiß überstrahlt, Cameo sichtbar, Münzen und Bildschirm richtig.
5. *Rendern* in Blender (mit GPU-Sperre); für Entwürfe auch mit halber Auflösung und wenigen Samples.
6. **Prüfpunkt Vorschau**: Sie sehen die Abschnittsvorschau, danach den ganzen Film.

Kamerastil (`calm` oder `lively`), Farbpalette und wer wo steht lassen sich ebenfalls vorgeben. Schnitte landen auf
Beats nahe an Zeilenanfängen, Einstellungen dauern 1–3 s, große Bewegungen bekommen eine Nahaufnahme von unten.

**Ergebnisse:** `film.mp4`, `film_small.mp4` (unter 30 MB), `film_mail.mp4`, dazu der Einstellungsplan pro
Abschnitt (`bricks/<abschnitt>.json`), der sich auch von Hand bearbeiten lässt.

**Nachträglich ändern:** Wünsche in Worten nennen; Claude ändert das Projekt und plant neu, oder es ändert den
Einstellungsplan direkt und rendert ihn unverändert. Neuer Seed = neue Variante.

**Typische Probleme:** Gesichter überstrahlt (zu nahes Licht), Figuren unscharf (die Schärfentiefe wird über die
Blende geregelt), Schrift über einem Gesicht. Claude prüft das auf der Liste: Lippen passen zur Stimme (Mund
geschlossen in Pausen), Schnitte auf dem Beat, Sänger im Bild, Cameo lesbar, Filmlänge gleich Abschnittslänge.

**Beispiel-Prompts:**

```
Mach aus dem zweiten Refrain von song.wav einen Brickfilm. Liedtext liegt in lyrics.txt.
```

```
Tim soll ein grünes Shirt, braune Haare und eine Brille haben, Lia bleibt wie sie ist.
```

```
Zeig mir erst ein paar Standbilder vom Refrain, bevor du alles renderst.
```

```
Die Strophe soll auf dem Dach spielen, der Refrain in der Arena. Am Ende der Strophe fliegt die Kulisse
auseinander und die Arena baut sich aus fliegenden Steinen auf.
```

```
Bei „Haare“ sollen im zweiten Refrain die Haare fliegen, im dritten springt der Kopf ab. Und bei „Ultra“
verschwinden die Münzen eine nach der anderen im Takt.
```

---

### 3.3 3D-Figurenfilm (`animated-3d-film`)

**Wann:** Sie möchten eine Geschichte, ein Erklärstück oder ein Skript als 3D-Film mit Spielzeugfiguren erzählen,
im Look einer hochwertigen Animationswerbung – oder einen bestehenden 2D-Film als 3D-Remake. Alles ist als
Python-Szene geschrieben: nichts wird von Hand modelliert, alles lässt sich ändern und neu rendern.

**Was Sie mitbringen bzw. was Claude fragt:**

- **Was ist der Film?** Ein Skript oder eine Geschichte, ein Remake (dann kann dessen Tonspur und Timing
  übernommen werden) oder „überrasch mich“. Wie lang? 30–90 s sind eine gute Größe, Minuten bedeuten einen großen
  Render.
- **Wer spielt?** Die mitgelieferten Figuren Bär, Katze, Hase (Farben, Brille, Größe frei) oder eine eigene
  Besetzung, die wiedererkennbar bleiben muss. Die Figuren gibt es in sieben Macharten: Filzspielzeug (Standard),
  genähte **Stoffpuppen** (Leinen, Nähte, Knopfaugen), **Handpuppen** für eine Puppenshow (Fleece, Klappmaul,
  Führungsstäbe; sie spielen hinter einer Spielleiste) oder düstere **Stop-Motion-Puppen** (dünne Glieder, riesige
  Augen, Knet-Haut, Streifen; braucht einen dunklen, kalt beleuchteten Film), dazu bunte **Knetfiguren**,
  gefaltete **Papierfiguren** (mit Falzlinien und Klebelaschen) und hölzerne **Marionetten** an Fäden – sagen Sie
  z. B. „als Stoffpuppen“, „als Puppenshow“, „als Stop-Motion-Puppen“, „aus Knete“, „aus Papier“ oder
  „als Marionetten“.
  Oder **echte Darsteller in einer echten Welt**: Rigify-Figuren (z. B. Tim und Claudia aus dem
  3D-Figuren-Baukasten) spielen dieselben Szenen, sprechen mit Gesichtsreglern und Mundformen, stehen mit den
  Füßen auf dem Boden (mit Schritten beim Gehen und Drehen) und greifen nicht durch Tische – sagen Sie z. B.
  „mit Tim und Claudia als echten Figuren“. Die Figuren liegen als `<Name>/figur.blend` im Projektordner
  `actors/` oder in dem Ordner, den die Einstellung `actors3d` nennt.
  Raumwechsel können als **Theater-Umbau vor Publikum** geschehen statt als Schnitt (Wände fliegen hoch, Möbel
  rollen weg, eine Showbühne rollt aus, Bühnenarbeiter laufen durchs Bild, ein Verfolger-Spot bleibt auf der
  Figur), dazu ein Vorhang und als Finale eine **Lichtshow** mit Moving Heads im Bühnennebel – sagen Sie z. B.
  „der Raumwechsel als Theater-Umbau“. Für Gags im Stil von „Die nackte Kanone“ (todernst gespielt, sehr dicht,
  Running Gags) kennt der Skill eine eigene Anleitung.
  Ein **Abspann wie im Kinofilm** gehört dazu, wenn Sie möchten: Rolltitel in Blöcken, dazwischen Extra-Szenen,
  daneben **Outtakes vom Dreh** (Filmklappe, eine Einstellung geht schief, die Figuren lachen und schauen in die
  Kamera) und eine Szene nach dem Abspann – sagen Sie z. B. „mit Abspann und Outtakes“.
  Nach einer Korrektur (ein Arm im Tisch, ein späterer Gag, ein neuer Satz) rendert der Skill **nur die Bilder neu,
  die sich wirklich ändern** – nicht den ganzen Clip. Nach einem Plugin-Update sagen Sie „rendere nach, was sich
  geändert hat“. Während des Renderns geht der PC nicht in den Ruhezustand (der Bildschirm darf aus).
  Ein fertiger Film lässt sich ohne Änderung der Szenen in einer anderen Machart neu rendern.
- **Ton?** Gesprochene Zeilen (Stimmen-Baustein), eigene Aufnahmen, eine fertige Tonspur, Musik.
- **Look?** Standard: elfenbeinfarbene Wände, dunkles Nussholz, ein korallenroter Akzent, tiefes goldenes Licht und
  das dunklere „Kino“-Finish. Andere Paletten (`petrol`, `forest` oder eigene Farben) und ein helles „Werbe“-Finish
  auf Wunsch.
- **Schnell oder Detail?** Claude nennt Ihnen vorher die Kosten: Die schnelle Vorschau (ca. 1 Stunde für
  4 Minuten Film auf einer RTX 5060 Ti) zeigt Timing, Spiel, Lippen und Schnitte; die Filmqualität dauert etwa
  fünfmal so lang. Standard: erst Vorschau, dann entscheiden.

**Ablauf aus Ihrer Sicht:**

1. *Kreatives Briefing*: Claude legt das Projekt mit Seed an, erfindet pro Szene eine Idee, ein wiederkehrendes
   Detail, das letzte Bild und eine Körpersprache für jede Figur. Es plant einen **Lichtbogen** (Tageszeit pro
   Clip: golden, Dämmerung, Nacht, Morgen, Tag) und wenige, lange Einstellungen mit echten Nahaufnahmen.
2. **Prüfpunkt Clipliste**: Name, Länge, was passiert, gesprochene Zeilen – in einem kurzen Block.
3. *Zeilen und Ton*: Die Stimmen werden erzeugt und mit Whisper geprüft; eigene Aufnahmen werden nur vorbereitet.
   Eine Erzählerstimme ohne sichtbare Figur ist möglich.
4. *Szenen bauen*, bei eigener Besetzung zuerst ein Posenblatt jeder Figur.
5. **Prüfpunkt Kontaktabzug pro Clip**: Claude prüft jede Kachel (Bildausschnitt, verdeckte Gesichter, Weiß auf
   Weiß, schwebende Requisiten, Münder, Belichtung – zu hell und zu gleichmäßig ist der häufigste Fehler).
6. **Prüfpunkt Vorschau des ganzen Films** (`preview/film_draft.mp4`, mit Ton und Look): Claude fragt Sie, ob erst
   Änderungen kommen oder in Filmqualität gerendert wird.
7. *Filmrender* (Stunden, jederzeit unterbrechbar und fortsetzbar). Währenddessen kann Claude schon fertige Clips
   zusammenschneiden, damit Sie den Fortschritt sehen.

**Ergebnisse:** `film.mp4`, `film_small.mp4` (unter 30 MB), `film_mail.mp4`, jeweils geprüft; dazu der
Projektordner (jede Szene ist bearbeitbarer Code), Seed und Ideen. Claude sagt Ihnen offen, was es nur auf
Standbildern und was es in Bewegung geprüft hat.

**Nachträglich ändern:** Ein Clip, dessen Szene, Projekteinstellungen oder Zeilen sich geändert haben, wird beim
nächsten Lauf automatisch neu gerendert; die anderen bleiben. Nach einer späten Änderung kann Claude auch nur
einen Bildbereich neu rendern. Pro Clip gibt es Feinschliff (Abblenden, Weißblende, Sättigung), Überblendungen
zwischen Clips und die Wahl des Looks (`cinema`, `ad`, `standard`, `none`). Ein geänderter Text wird neu
gesprochen; bei eigenen Aufnahmen kommt nur eine Warnung (neu aufnehmen).

**Typische Probleme:**

- Bilder zu hell und flach – lieber Lichter herunterregeln.
- Lippensynchronität ist mit englischem Dialog am besten; andere Sprachen ergeben trotzdem brauchbare
  Öffnen/Schließen-Formen.
- Ohne Grafikkarte rendert Cycles auf der CPU, das ist sehr langsam.

**Beispiel-Prompts:**

```
Erzähl dieses Skript als 3D-Film mit Spielzeugfiguren, wie eine hochwertige Werbung. Etwa 60 Sekunden.
```

```
Besetzung: Mo als Bär und Kit als Katze mit Brille. Überrasch mich mit der Geschichte, Thema Teamarbeit.
```

```
Die Vorschau gefällt mir. Clip c03 soll aber nachts spielen statt in der Dämmerung, und Kit soll skeptischer
gucken, wenn Mo von seinem Plan erzählt. Danach bitte in Filmqualität rendern.
```

```
Nimm statt der Kino-Optik das helle Werbe-Finish und die Palette „petrol“. Zwischen c01 und c02 eine weiche
Überblendung.
```

```
Mach aus unserem 2D-Film ein 3D-Remake. Die Tonspur film_ton.wav soll bleiben, jeder Clip genauso lang wie sein
Stück der Tonspur.
```

---

### 3.4 Lyric-Video (`lyric-music-video`)

**Wann:** Sie möchten ein Typografie-Video zu einem Song: Teamsong, Firmensong, ein Song, der Inhalte präsentiert
(eine Seite, Rollen, ein Produkt, Folien). Jeder Buchstabe landet genau, wenn er gesungen wird. Nicht für singende
Figuren, Brickfilme oder KI-Sänger.

**Was Sie mitbringen:**

- **Song** (wav/mp3) – erforderlich. Liegt eine passende Datei gerade in Ihren Downloads, fragt Claude vielleicht,
  ob es diese ist.
- **Suno-Stems** (Lead und Backing), falls vorhanden – sie müssen aus **derselben Fassung** stammen wie der Mix.
- **Liedtext** mit `[Abschnitt]`-Überschriften.
- **Kontext**: Worum geht es, wer schaut zu? **Quellmaterial**, das präsentiert werden soll (HTML-Seite, Dokument,
  Rollen- oder Produktliste, Bilder).
- **Stilwünsche**: Genre, Stimmung, Farben, Marke, Vorbilder, was vermieden werden soll. Ein genanntes Vorbild
  liefert Ideen, nie den Look.
- **Sprache(n)** – gemischt Deutsch/Englisch geht.

**Ablauf aus Ihrer Sicht:**

1. *Kreatives Briefing*: Claude liest den Katalog aller bisherigen Videos und würfelt mit dem Seed sechs
   „Würfel“ (Texteinstieg, Schnittstil, Palettenstrategie, Schriftpaarung, Raum, Ende). Daraus entsteht eine
   **visuelle Identität** in 2–3 Zeilen, die sich von allen früheren unterscheidet, und **eine Szene pro
   Textidee**. Ein neuer Seed ergibt eine neue Variante.
2. **Prüfpunkt Plan**: Identität plus eine Zeile pro Szene. Sie können reagieren oder Claude macht weiter.
3. *Analyse* (läuft im Hintergrund): Wörter werden auf den echten Stimmeinsatz geschoben, gehaltene Töne erkannt,
   Riff-Hits und Beat-Raster gefunden. Nicht gehörte Zeilen holt Claude mit zusätzlichen Whisper-Durchgängen nach.
4. **Gehaltene Töne** („aaaall“, „riiiight“) werden automatisch auf den 2–4 wichtigsten Wörtern gedehnt, wie sie
   gesungen werden.
5. **Prüfpunkt Vorschau**: 1-fps-Render des ganzen Songs mit Kontaktabzügen alle 6 s; zeitkritische Stellen als
   10-fps-Clip.
6. *Endrender*: 1080p mit 30 fps, ca. 6–10 min für 3–4 min Song auf einer GPU.

**Ergebnisse** (Standard im Ordner `out/` des Projekts, auf Wunsch woanders hin kopiert):

| Datei | Inhalt |
|---|---|
| `<Titel>.mp4` | volle Qualität (1080p30) |
| `<Titel>_compressed.mp4` | stärker komprimiert |
| `<Titel>_small.mp4` | unter 30 MB, 720p |
| `<Titel>_mail.mp4` | ca. 12 MB, 540p |

Dazu das Projekt (ohne `node_modules`) und eine Beschreibung, was jede Szene zeigt.

**Nachträglich ändern:**

- Zeilen als „geschätzt“ markiert (nicht gehört): Claude schreibt den Liedtext so um, wie er gesungen wird
  (Wiederholungen ausgeschrieben, Rufe als eigene Zeile), und analysiert neu.
- Ein einzelnes Wort zur falschen Zeit: Claude korrigiert die Zeit von Hand.
- Der ganze Text zu früh oder zu spät: eine Vorlaufkonstante verschiebt allen Text.
- Gehaltene Töne: ausschalten, Anzahl begrenzen oder Stil wechseln (`vowels`, `stretch`, `auto`), oder einzelne
  Wörter von Hand wählen.

**Typische Probleme:**

- **Text driftet zunehmend** gegen die Stimme: Stems und Mix stammen nicht aus derselben Fassung.
- **Schriften** werden bei jedem Render von Google Fonts geladen (eine Anfrage an Google; offline erscheinen
  Ersatzschriften). Für private oder Offline-Renders kann Claude die Schriftdateien ins Projekt legen – das
  Herunterladen erfolgt nur nach Rückfrage.
- **Browser startet nicht**: Auf dem Referenzrechner beendete sich Edge im Headless-Modus sofort; dann wird
  chrome-headless-shell gebraucht (Download nur mit Ihrer Zustimmung).
- **Sehr große Dateien** entstehen durch Filmkorn, das sich jedes Bild ändert.
- **Lange Pfade** unter Windows: Projektordner kurz halten.
- Ist die Ausgabedatei gerade in einem Player geöffnet, bekommt die neue Datei einen neuen Namen (Claude sagt das).

Was bisher gut ankam und was nicht, steht im Szenenkatalog: gelobt wurden genau synchroner Text, eine Szene pro
Textidee, Beat-Akzente und besondere Enden; abgelehnt wurden farbige Markierungskästen hinter gesungenen Wörtern,
nachlaufender Text, riesige Dateien und alles, was nach Kopie eines Vorbilds aussieht.

**Beispiel-Prompts:**

```
Mach ein Lyric-Video zu teamsong.mp3, der Text liegt in lyrics.txt.
```

```
Ein Lyric-Video für unseren Teamsong, das die Rollen von dieser Seite vorstellt: team.html. Jede Rolle soll genau
dann erscheinen, wenn ihr Name gesungen wird. Farben aus unserem Logo, eher Stadion als Büro.
```

```
Hier sind die Suno-Stems lead.wav und backing.wav von derselben Fassung – nimm die fürs Timing.
```

```
Gefällt mir noch nicht – würfel eine neue Identität, aber behalte die Idee mit der Abfahrtstafel im Refrain.
```

```
Bei 1:28 bis 1:38 kommt der Text zu spät. Und das gedehnte „aaaall“ im letzten Refrain bitte als ein Vokal,
der breiter wird.
```

---

### 3.5 Claudia-Musikvideo (`claudia-music-video`)

**Wann:** Claudia soll einen Song singen – als fotorealistisches KI-Musikvideo, lokal über Nacht gerechnet und auf
den Song geschnitten. Zwei Fassungen:

- **studio**: Story-Video an echten Orten, die aus dem Liedtext kommen, mit B-Roll-Bildern zu den Motiven des Songs,
- **live**: Konzertbühne mit Band-Silhouetten, Publikum von hinten, Lichtshow.

**Wer ist Claudia?** Eine offene Figur („Claudia by anabology“): schwarzer Bob mit schweren Ponyfransen, **genau
eine** tonorange Strähne auf ihrer rechten Seite, eine kleine orange Sternspange, **genau ein** dünnes beiges
Headset-Mikrofon an ihrer rechten Wange (im Bild links), Ende zwanzig, trocken-ruhige Ausstrahlung, immer
fotografisch. Der vollständige Kanon steht im Plugin unter `characters/references/claudia.md`, und Claude hält sich
streng daran (zum Beispiel steht in Prompts nie „young“, sondern „28-year-old“).

**Was Sie mitbringen:**

- **Song**, **Liedtext**, **Stems** falls vorhanden (Lead und Backing; sie verbessern die Lippenmessung),
- **Fassung**: studio oder live,
- ganzer Song oder **Ausschnitt** als Pilot; Nachtlauf heute Nacht oder ein paar Einstellungen sofort,
- Feststehendes: Orte, Kleidung, Personen (nur anonym oder von hinten), was nicht vorkommen darf,
- **zwei Referenzbilder von Claudia** – das Plugin liefert keine mit: ihr Gesicht mit Mikrofon und Spange, plus
  eine Nahaufnahme mit der einen Strähne und der Spange. Das können eigene Bilder sein, Bögen von claudia.gallery
  (Download nur mit Ihrem OK) oder Standbilder aus einem früheren Claudia-Film.

**Wichtig bei den Referenzbildern:** Der Mikrofonbügel muss an **ihrer rechten Wange** (im Bild links, auf der
Seite der Strähne) liegen. Das Modell kopiert das Mikrofon aus Bild 1; ein Referenzbild mit dem Mikrofon auf der
falschen Seite ergibt falsche Mikrofone in den meisten Startbildern.

**Ablauf aus Ihrer Sicht:**

1. *Interview* – kurz, eine Frage nach der anderen, jeweils mit Vorschlag.
2. *Song-Analyse*: Die gesungenen Zeilen müssen auf dem Gesang sitzen; sie werden zu Schnitten und zur
   Lippenkurve.
3. *Einstellungsplan und kreatives Briefing*: eine Einstellung pro gesungener Zeile, auf dem Beat. Claude erfindet
   ein Konzept, eine Garderobe für genau diesen Song, Looks für die Orte und pro Einstellung eine konkrete
   Bildidee: was Claudia tut, wo, wie sie singt (zum Beispiel „softly“, „with energy“).
4. **Prüfpunkt Einstellungsliste** (Zeit, Zeile, Technik, Idee) – Claude fragt nach Änderungen, **bevor**
   GPU-Zeit verbraucht wird, und zeigt Ihnen die geschätzte Laufzeit.
5. *Nachtlauf*: FLUX-Standbilder → Startbilder mit Claudias Gesicht → Kanonprüfung → Tiefenkarten →
   Lippensync-Clips und bewegte B-Roll. Ungefähre Kosten: ca. 10 min Laden, pro Gesangseinstellung 2 Seeds à ca.
   2,5 min, pro B-Roll ca. 2,5 min; ein 3-Minuten-Song ca. 4–7 Stunden. Andere große Programme sollten geschlossen
   sein (LTX braucht in der Spitze fast 45 GB Arbeitsspeicher).
6. *Auswahl nach Messung*: Für jeden Seed wird die Lippensynchronität gemessen; Clips mit geschlossenem Mund,
   verstecktem Szenenschnitt oder Standbildstrecken fallen heraus. Startbilder mit falschem Mikrofon werden
   automatisch repariert.
7. **Prüfpunkt Takes-Seite** (empfohlen, ohne GPU): Claude öffnet eine lokale Seite im Browser. Links die
   Einstellungsliste, rechts die Takes einer Einstellung nebeneinander mit Lippenwert, Bewegung und Warnungen.
   Tasten 1–9 wählen, Pfeil hoch/runter wechselt die Einstellung, Leertaste spielt alle Takes zusammen. Jede
   Einstellung bietet auch ihr **Standbild** (mit Tiefen-Kamerafahrt) statt eines Clips an. Die Schaltfläche
   **„Build cut“** (Schnitt bauen) rendert die geänderten Einstellungen neu, schneidet den Film und zeigt ihn auf
   der Seite. Claude wählt hier nicht für Sie vor: In Tests bevorzugte das Auge oft natürliche Bewegung vor dem
   höchsten Messwert.
8. *Schnitt*: Liedtext-Overlay, KI-Kennzeichnung in den letzten 3 Sekunden, Ausgabeversionen.
9. **Prüfpunkt V1**: Sie schauen die erste Fassung. Danach hilft `video-review` beim Vergleich mit einer V2.

**Techniken pro Einstellung** (Claude schlägt sie vor, Sie können sie verlangen):

| Technik / Engine | Wofür |
|---|---|
| `ltx` (LTX-2.3) | Standard für gesungene Zeilen, schnelle Silben, beste Bildqualität |
| `s2v` (Wan2.2-S2V) | gehaltene, emotionale Töne in Nahaufnahme (unter 4,7 s); standardmäßig für einige solche Stellen an, immer mit einem LTX-Seed als Sicherheitsnetz |
| `infinitetalk` | lange gesungene Passagen als ein Take statt mehrerer Schnitte |
| `humo` / `minimax` | Rettungsversuch für Zeilen mit vielen p/b/m, bei denen LTX scheitert |
| `ltx25` | Versuch: ein Schnitt innerhalb einer gesungenen Einstellung (6–8 s); nur auf ausdrücklichen Wunsch, braucht zusätzliche Modelldateien, die meisten Takes sind Ausschuss |
| B-Roll | bewegte Bilder zu den Motiven, Personen nur anonym oder von hinten |
| `typo` | gezeichnete Typografie ohne KI (Eilmeldung, Stempel, Abfahrtstafel, Titel) |
| `placed` | ein vorhandener Clip mit singendem Mund ohne eigenen Ton wird auf die Gesangskurve gelegt |
| Publikum | eigenes Rezept für Publikumsaufnahmen |
| eigenes Startbild | ein bestimmtes Bild statt neu erzeugter Startbilder |

**Ergebnisse:** `film.mp4`, `film_small.mp4`, `film_mail.mp4` (0 Decodierfehler), `film_sheet.png`,
`film_shots.jpg`, `review.json`; dazu `selection.json` (Ihre Auswahl), `picks.log` (Messwerte), `milestones.log`
(Protokoll des Nachtlaufs) und die Kontaktabzüge `sheet_start.jpg`, `sheet_broll.jpg`, `sheet_clips.jpg`.
Der Film hat standardmäßig keinen zusätzlichen Papier-Look, weil Korn und Vignette schon in den Einstellungen
stecken; mit dem Look `standard` kommt die Papiertextur obendrauf.

**Nachträglich ändern:**

- anderer Take oder das Standbild für eine Einstellung: auf der Takes-Seite wählen oder Claude sagen,
- schwache Lippen (Wert unter 0,2): zwei Seeds mehr mit stärkerem Mundsatz, ein anderes Startbild oder B-Roll,
- **mehr Takes später**: ein anderer Seed pro Einstellung; der alte Take bleibt erhalten,
- **mehrere Aktionen auf dem Beat** (Gesten-Listen, „Hey!“-Rufe, Refrain-Energie): eine Zeitleiste für die
  Einstellung; dann rendert sie gemischt mit dem einfachen Prompt (A) und dem Zeitleisten-Prompt (B), die
  Takes-Seite zeigt bei jedem Take, welcher Prompt es war, und Sie wählen nach Auge,
- neues Startbild für eine Einstellung: der Nachtlauf läuft nur für diese Einstellung noch einmal,
- weiche 480p-Clips (S2V, InfiniteTalk) lassen sich vor dem Schnitt mit Real-ESRGAN hochskalieren,
- ein neuer Seed im Projekt ergibt eine neue Fassung von Plan, Garderobe, Seeds und Kamerabewegungen.

**Typische Probleme:**

- **Zwei Mikrofone** oder Mikrofon auf der falschen Wange: wird meist automatisch repariert; die Messung ist aber
  nur ein Hinweis – schauen Sie sich `sheet_start.jpg` selbst an.
- S2V fügt manchmal zwischen den Bildern ein zweites Mikrofon hinzu – den ganzen Clip mit dem Auge prüfen.
- Ein Take, der auf einem nicht mehr gewählten Startbild beruht, ist auf der Takes-Seite gelb markiert.
- Haben alle bewegten Clips einer B-Roll-Einstellung einen versteckten Schnitt oder frieren ein, wählt die
  Automatik das Standbild mit Tiefen-Kamerafahrt; die Clips bleiben auf der Takes-Seite wählbar.
- Vokalisen ohne Wörter („Ooh“) und Profilansichten lassen sich nicht sinnvoll messen – mit dem Auge beurteilen.
- FLUX-Bilder können erfundene Schrift auf Bildschirmen oder Tafeln enthalten – im Kontaktabzug aussortieren.
- Real-ESRGAN glättet Sommersprossen.
- Bleibende Schwäche aller Modelle: Lippen schließen sich bei kurzen p/b/m nicht sauber.

**Beispiel-Prompts:**

```
Claudia soll song.wav singen. Studio-Version, erst mal nur den ersten Refrain als Pilot.
Die Referenzbilder liegen in refs/.
```

```
Mach eine Live-Version davon: Konzertbühne, Band als Silhouetten, Publikum von hinten. Lass es heute Nacht laufen
und sag mir vorher, wie lange es dauert.
```

```
Sie soll in diesem Video einen dunkelgrünen Mantel tragen, und keine Flugzeuge bitte.
```

```
Zeig mir die Takes-Seite.
```

```
Nimm bei s04 den zweiten Take, bei s07 lieber das Standbild, und für s12 bitte noch zwei Seeds mehr. Dann den
Schnitt neu bauen.
```

```
In s08 soll sie bei jedem „Hey“ die Faust heben und danach auf dem Beat nach vorn gehen – mach dafür eine
Zeitleiste und rendere A und B, damit ich vergleichen kann.
```

```
Vergleich V1 und V2 Einstellung für Einstellung und schneide aus beiden die beste Fassung.
```

**Andere Hauptfigur, zweite Figur (ab 0.10).** Das Video muss nicht von Claudia gesungen werden: Mit ein oder zwei
Referenzbildern und einer kurzen Beschreibung singt eine eigene Figur im selben fotografischen Stil, und Claudia kann
als Gast ohne Bühnenmikrofon dazukommen (auch beide in einem Bild).

```
Mach das Musikvideo im Claudia-Stil, aber mit Oliver als Sänger. In der Strophe mit der Tochter spielt Claudia mit.
```

**Mehr Auswahl für einzelne Einstellungen.** Wenn eine Einstellung nicht passt, lassen sich zusätzliche Fassungen
drehen, ohne die vorhandenen zu verlieren – auch von einem neuen Startbild. Auf der Vergleichsseite stehen sie dann
nebeneinander.

```
Für s05 hätte ich gern zwei zusätzliche Fassungen mit einem ruhigeren Startbild, die jetzige soll bleiben.
```

Geänderte Beschreibungen werden beim nächsten Nachtlauf von selbst neu gerechnet; die alte Datei bleibt im
Unterordner `replaced` erhalten.

---

### 3.6 Animierte Präsentationsfiguren (`animated-powerpoint`)

**Wann:** Figuren aus einer Präsentation sollen lebendig werden: Sie steigen aus der Folie in einen 2,5D-Raum,
landen, gestikulieren und sprechen. Die Figuren werden nie neu gezeichnet, sondern aus dem Originalbild in
bewegliche Teile zerlegt – jedes Pixel der Ruhepose ist das Pixel der Folie. Der Clip passt zurück in die
Präsentation: gleiche Größe, er beginnt auf der Folie und kann auf ihr enden. Alles bleibt lokal, auch bei
internen Präsentationen.

**Was Sie mitbringen bzw. was Claude fragt:**

- die Präsentation (`.pptx`, PDF oder Folienbilder) und welche Folie(n),
- welche Figuren aussteigen und welche nur zuschauen,
- wo der Clip läuft: nach der Folie (beginnt auf der Folie) oder als Schleife auf der Folie (endet wieder dort),
- Text auf den Namensschildern (Name und Rolle von der Folie),
- optional eine Erzählung als Tonaufnahme(n); dann können Schilder genau beim gesprochenen Namen aufpoppen und
  Figuren nach einem bestimmten Wort starten.

**Ablauf aus Ihrer Sicht:**

1. *Interview und Briefing*: Claude liest Folientext und Notizen und erfindet Ideen aus dieser Präsentation (eine
   Geste, die zur Rolle passt, wer auf wen reagiert, ein Ende).
2. *Import* der Folien (PowerPoint wird nur lesend geöffnet; Logo, Fußzeile und Seitenzahl des Masters werden für
   das saubere Startbild entfernt).
3. *Figuren finden* und bei Bedarf hochskalieren (`figures/contact_figures.png`).
4. *Figuren zerlegen*: Claude erzeugt einen ersten Vorschlag (Kopf, Pupillen, Körper) und verfeinert die Teile
   anhand eines Prüfbilds. Arme, Schwänze und Flügel brauchen ein von Hand gesetztes Polygon.
5. *Clip schreiben und bauen*. Ein 8-s-Clip dauert ca. 1,5 min, ein 25-s-Clip mit vier Figuren ca. 25 min.
6. **Prüfpunkt Kontaktabzug** (`contact.png`) und Prüfwerte: sauberer Start auf der Folie, bei einer Schleife
   nahtloses Ende. Claude zeigt Ihnen den Clip; Startzeiten, Gesten und Kamera lassen sich anpassen.
7. *In die Präsentation*: Clip auf der Folie (oder direkt danach) in voller Größe einfügen, „automatisch starten“;
   für eine Schleife „Wiedergabe bis zum Beenden“. Weil das erste Bild der Folie entspricht, ist der Übergang
   unsichtbar.

**Was die Figuren können:**

| Bereich | Möglichkeiten |
|---|---|
| Ausstiegsstil | `jump` (Sprung), `flutter` (für Figuren mit Flügeln), `hop` (zögerlicher Hüpfer), `stuck` (schwere Figur bleibt in der Folie stecken, kämpft und ploppt heraus) |
| Gesten | Faust, winken, nicken, nach oben schauen (mit Funkeln auf der Brille), Schwanzwedeln, Kopfschütteln, keine |
| Weiteres | Salto, Namensschild, Gruppenbild am Ende (Standard ab drei Figuren), Zuschauer-Figuren folgen mit Augen und Kopf |
| Sprechen | Mundformen werden aus der Zeichnung selbst geschnitten (offenes Grinsen, Mundlinie oder Schnabel) und lippensynchron zur Erzählung bewegt |

**Weitere Clip-Arten:**

- **Präsentations-Intro**: Titelfolie leuchtet auf, Folien blättern immer schneller, eine Wortwolke fliegt heraus,
  eine Folie tippt ihren Titel Wort für Wort mit der Stimme und blättert nahtlos zum nächsten Clip.
- **Outro**: die vorige Szene schrumpft in die Folie, Kamerafahrt auf ein Gesicht, die Figur zwinkert, Iris zu,
  Titelkarte.
- **Szenen nach dem Ausstieg**: gemalte Kulissen, Kamerafahrten, Erzählung mit Lippensynchronität. Acht fertige
  **Szenenrezepte** dienen als Startpunkt (Neuigkeit mit Reaktionen, Split-Screen, Nacht-Hologramme, Münzregen,
  Fortschrittsbalken, treibende Inseln, Finale mit Konfetti u. a.); Claude erfindet die eigenen Momente Ihrer
  Präsentation im Briefing.

**Ergebnisse** pro Clip: `<name>.mp4` (mit Look), `stage.mp4` (ohne Look), `first.png` / `last.png`, `contact.png`,
`plan.json` (Ereignis-Bilder), `check.json` (Prüfwerte), `ton.wav` und `sound.json` (Erzählung plus Effekte).

**Typische Probleme:**

- Beim ersten Bau hatte im Referenzprojekt jede Szene einen Bildausschnittfehler (Köpfe abgeschnitten, Schilder
  außerhalb) – deshalb prüft Claude immer den Kontaktabzug.
- Sichere Bewegungswinkel sind klein (Kopf etwa ±5°, Arm ±9°). Ein Arm, der in der Zeichnung ein eigenes Teil ist,
  kann stärker schwingen.
- Weiße Fransen an weichen Kanten auf farbigen Kulissen lassen sich entfernen.
- Der Folienexport aus `.pptx` braucht PowerPoint unter Windows; sonst die Folien als PDF oder PNG exportieren.

**Beispiel-Prompts:**

```
Lass die Figur auf Folie 3 von deck.pptx aus der Folie springen und winken.
```

```
Die vier Figuren auf Folie 5 sollen nacheinander aus der Folie steigen. Der Vogel flattert, der Dicke bleibt
stecken. Auf die Schilder Name und Rolle von der Folie.
```

```
Der Clip soll als Schleife auf der Folie laufen und wieder auf der Folie enden.
```

```
Hier ist die Erzählung erzaehlung.wav. Jede Figur soll erst starten, wenn ihr Name fällt, und die Eule soll den
letzten Satz selbst sprechen.
```

```
Mach noch ein Intro für die ganze Präsentation: die Folien blättern immer schneller bis zum Wort „Effizienz“,
und am Ende ein Outro, in dem die Eule zwinkert.
```

---

### 3.7 Sprechende Figuren (`talking-character`)

**Wann:** Figuren sollen *sprechen*: eine Dialogszene, ein sprechender Kopf, ein Sketch zwischen Tim, Lia und dem
Computer (oder Ihren eigenen Figuren), eine gesprochene Ansage oder Lippensynchronität zu einer Aufnahme.

**Was Claude fragt:** wer spricht, worüber, wie lang (Standard 15–20 s), welche Sprache (Standard Deutsch), ob Sie
das Skript schreiben oder Claude, ob es eine Aufnahme gibt oder Stimmen erzeugt werden, und wo es spielt (`room` =
Tims Zimmer mit Monitor, `stage`, eine Farbe oder eine Projektkulisse).

**Das Skriptformat** – Sie können es selbst schreiben oder Claude schreiben lassen:

```
Tim: (to computer) Computer, ich brauche ein Gedicht. Schnell!
Computer: (screen "REIM.EXE") Gerne, Tim. (beat) Rosen sind rot ...
Tim: (scare) Der Kuchen! (point at computer) Den hab ich vergessen!
(pause 0.8)
```

Regieanweisungen in Klammern: Pausen (`(pause 1.2)`, `(beat)`), Blickrichtung (`(to <name>)`,
`(looks up|down|away|camera)`), Tempo (`(quick)`, `(slow)`), Unterbrechen (`(interrupts)`), Bildschirmtext für den
Computer (`(screen "TEXT")`) und Gesten: cheer, point, scare, surprise, scratch, nod, sad, shrug, wave, jump, lean.
Claude schreibt den Dialog mit Regie: eine Wendung in der Mitte, eine Pointe am Ende, 2–4 Gesten auf den Wörtern,
die die Bedeutung tragen.

**Stimmen:** Jede Figur hat eine feste Stimme. Standard ist Qwen3-TTS (lokal, braucht eine GPU-Umgebung); Tim, Lia
und der Computer haben mitgelieferte Referenzstimmen, neue Figuren bekommen beim ersten Mal eine Stimme nach einer
Beschreibung entworfen (Alter, Klangfarbe, Temperament). Ausweichstimmen: Piper (CPU) und die Windows-Sprachausgabe.
ElevenLabs (Cloud) ist optional und nur nach Rückfrage: Der Zeilentext verlässt dann den Rechner und es kostet
Guthaben. **Echte Personen werden nie geklont.**

**Ablauf aus Ihrer Sicht:**

1. *Briefing und Skript*.
2. **Prüfpunkt Stimmen**: Claude erzeugt zuerst nur die Stimmen und zeigt eine Tabelle mit Zeiten und
   Whisper-Wert pro Zeile. Zeilen unter 0,8 werden korrigiert (Aussprache) oder neu aufgenommen. Sie können sich
   die Tonspur (`song.wav` im Projekt) anhören, bevor gerendert wird.
3. *Szene*: Claude schaut 3–4 Einzelbilder an (Platzierung, wer wen anschaut, Bildschirmtexte).
4. *Film* mit Untertiteln, Gestengeräuschen und Look; eine Synchronprüfung misst, ob der Mund offen ist, wenn die
   Stimme spricht (Ziel mindestens 0,85, keine stillen Lücken).

**Ergebnisse:** `film.mp4`, `film_small.mp4`, `film_mail.mp4`, `contact_sheet.png`, die bearbeitbare Szene
`scenes/dialogue.sif`; Stimmen werden in `lines/` zwischengespeichert und nur bei geändertem Text neu gesprochen.

**Nachträglich ändern:** Text einer Zeile ändern (nur diese wird neu gesprochen), Aussprache korrigieren
(`pronounce`, ohne die Untertitel zu ändern), Kamera (`auto`, `static`, `cuts`), Timing (Vorlauf, Pausen,
Unterbrechungen), Untertitel aus, Geräusche aus oder zusätzliche Geräusche auf Wörtern. Ein neuer Seed ergibt neue
Zuhörstile, Gesten, Blinkrhythmen und Kameraeinstellungen für dasselbe Skript.

**Eigene Figuren:** Inkscape-SVG nach der Rig-Konvention: jedes bewegliche Teil eine Gruppe mit sprechender ID
(`kopf`, `auge_l`/`auge_r`, `pupille_l`/`pupille_r`, `brauen`, optional `arm_l`/`arm_r`, `nase`, `wangen`), ein
kleiner Kreis `pivot_<teil>` als Drehpunkt, `pivot_mund` dort, wo der Mund hin soll (den Mund selbst weglassen), Füße
bei (200, 590) auf einer 400×600-px-Fläche. Teile, die dem Kopf nachschwingen sollen (Antenne, Ohren), lassen sich
angeben; eine Figur ohne Arme hüpft und lehnt sich statt zu gestikulieren.

**Typische Probleme:** Im Protokoll erscheinen harmlose Meldungen der Qwen3-TTS-Bibliothek („SoX could not be
found“, eine flash-attn-Warnung, unter Windows manchmal eine AutoRun-Meldung) – die Stimmen sind trotzdem in
Ordnung. Ein Projekt stoppt sofort, wenn einer Figur statt einer Stimme der Besetzung eine Rolle wie „male“
zugewiesen ist. Dieser Skill riggt nur SVG-Figuren; für Rasterfiguren aus Folien siehe 3.6.

**Beispiel-Prompts:**

```
Tim fragt den Computer, was ein Kontextfenster ist – 20 Sekunden, mit Pointe am Ende.
```

```
Hier ist mein Dialog in dialog.txt. Bitte erst nur die Stimmen machen, ich will sie vorher hören.
```

```
Der Computer spricht „Tokanami“ falsch aus – es soll wie „Tokka-nahmi“ klingen. Und Lia soll bei „Kuchen“
erschrecken.
```

```
Hier ist eine Aufnahme take.wav von mir und einem Kollegen. Mach daraus eine Szene mit Tim und Lia, Lippen
passend zur Aufnahme, ohne Untertitel.
```

```
Meine eigene Figur oma.svg soll mitspielen, mit einer warmen, leicht zittrigen Stimme einer etwa
achtzigjährigen Frau.
```

---

### 3.8 Kurze 2D-Szenen und Übungen (`animated-short`)

**Wann:** eine kurze Zeichentrickszene ohne Song (3–10 s): eine Figur will etwas, etwas passiert, sie reagiert.
Auch klassische Übungen der 12 Animationsprinzipien (hüpfender Ball, Mehlsack, Take, Antizipation,
Nachschwingen).

**Was Claude fragt** (höchstens drei Fragen, nur was fehlt):

- **Wer?** Pip (birnenförmiger Held mit Federantenne), Fips (kleiner blauer Vogel), Tim, Lia, der Computer, zwei
  davon oder Ihre eigene Figur.
- **Was passiert?** Die Situation in einem Satz, eine Übung oder „überrasch mich“.
- **Look und Länge?** Gezeichneter Hintergrund, eine Kulisse (`park`, `room`, `stage`), gemalter Wald mit
  Multiplane-Kamera, ein Flug in eine Comic-Seite oder handgezeichneter Grease-Pencil-Look; mit Ton (Standard ja,
  wenn earshot eingerichtet ist).

Ist die Anfrage vage, fragt Claude nicht weiter, sondern wählt etwas Charmantes, Einfaches und sagt, was es gewählt
hat.

**Ablauf aus Ihrer Sicht:**

1. *Idee und Prinzipien*: eine konkrete Situation mit Wunsch, Problem und Pointe; welche Prinzipien wo gezeigt
   werden. Offene Entscheidungen (etwa in welche Richtung eine Figur abgeht) trifft der Seed.
2. **Prüfpunkt Beat-Liste**: die Abschnitte mit Bildbereichen bei 24 fps (Etablieren, Bemerken, Antizipation und
   Aktion, Reaktion und Pointe).
3. *Bauen* als bearbeitbare Synfig-Szene.
4. **Prüfpunkt Kontaktabzug** der Schlüsselposen: Silhouetten lesbar, niemand abgeschnitten, Squash bei jedem
   Kontakt, keine rutschenden Füße, der Take liest sich, Pupillen führen.
5. *Fertigstellen*: Geräuscheffekte genau auf den Aktionsbildern, Standard-Look genau einmal.

**Ergebnisse:** `final/<name>.mp4`, `final/<name>.gif`, `final/contact.png` und die bearbeitbare `.sif`-Datei für
Synfig Studio. Claude sagt, welche Teile Keyframes und welche „gebacken“ (simuliert) sind, und nennt Seed und Ideen.

**Fertige Übungen und Referenzszenen:** hüpfender Ball, Mehlsack, Take, Pip und die Blume, Fips zwitschert, die
Lichtung als Multiplane-Szene, der 2,5D-Comic-Flug, Pip im Grease-Pencil-Look. Sie dienen als Technik, nicht als
Vorlage – Claude animiert sie nur nach, wenn Sie ausdrücklich eine Übung wollen.

**Beispiel-Prompts:**

```
Eine Übung: der hüpfende Ball, mit Squash und Stretch.
```

```
Pip findet eine Blume. Etwa 6 Sekunden, im Park.
```

```
Ein neuer Fips-Gag: Fips hält Pips Antennenkugel für eine Beere.
```

```
Der Take ist zu schwach – die Augen sollen größer werden und Pip soll vorher deutlicher ausholen. Ohne Film-Look
bitte, ich will ihn noch selbst bearbeiten.
```

```
Ein Multiplane-Flug durch einen gemalten Wald, an dessen Ende Fips auf einem Ast landet.
```

---

### 3.9 Schnelle Nachbearbeitung (`film-tools`)

**Wann:** kleine Arbeiten an Videos, die schon existieren – aus diesem Plugin oder von woanders. Kein Projekt nötig.
Für ganze Filme ist der passende Filmart-Skill zuständig; er ruft dieselben Werkzeuge am Ende selbst auf.

| Sie wollen | Ergebnis |
|---|---|
| den Standard-Film-Look (Papier, Korn, Vignette) | `<name>_look.mp4`; Stärke einstellbar |
| kleinere Versionen für Upload oder E-Mail | `_small` (unter 29 MB, lange Seite höchstens 1280) und `_mail` (ca. 12 MB, höchstens 960); Seitenverhältnis bleibt (Handyvideos bleiben hochkant), nie hochskaliert, nie größer als das Original |
| einen Kontaktabzug (3×3 Bilder) | ein PNG, das Claude ansieht und beschreibt |
| ein Einzelbild oder jedes Bild einer kurzen Stelle | z. B. 24 aufeinanderfolgende Bilder einer Geste oder eines Schnitts |
| einen Film „durchhören“ | Ereignisse, Abschnitte, Lautheit, Stille, Bildschnitte (mit earshot – ein maschinelles Ohr, kein Zuhörer) |
| wissen, was gesagt oder gesungen wird | jedes Wort mit Sekunde und Bildnummer (ungefähr ±0,3 s genau) |
| zwei Versionen vergleichen | Größe, Länge, MB, Bildähnlichkeit, ob der Ton identisch ist |
| eine Decodier-Prüfung | Größe, Länge und „0 decode errors“ pro Datei |
| mehrere Clips, Standbilder und Titelkarten zu einem Film schneiden | `film.mp4` mit Überblendungen, Musik und Titel, dazu kleine Versionen, Kontaktabzug und `.otio` für Kdenlive |
| einen neuen Look (anderes Papier, weicheres Korn …) | ein eigener Look-Ordner, der danach wie der Standard-Look angewendet wird (braucht Node und headless Chrome/Edge) |

**Regeln:** Die Eingabedatei wird nie überschrieben; das Ergebnis entsteht daneben mit einem Namenszusatz. Eine
schon vorhandene *Ausgabe*datei wird allerdings ohne Rückfrage überschrieben – wenn eine alte Fassung wichtig ist,
sagen Sie das, dann wählt Claude einen neuen Namen. Claude prüft das Ergebnis (Decodier-Prüfung, Kontaktabzug,
Dateigröße) und sagt, was nicht geprüft wurde (zum Beispiel, dass niemand den Ton angehört hat). Vor dem allerersten
Lauf fragt Claude, falls uv noch Pakete herunterladen muss.

**Beispiel-Prompts:**

```
Leg den Film-Look auf urlaub.mp4.
```

```
Mach urlaub.mp4 klein genug für eine E-Mail.
```

```
Prüf mal diese Datei – ist sie kaputt? Und zeig mir einen Kontaktabzug.
```

```
Vergleich film_alt.mp4 und film_neu.mp4: welcher ist besser für den Upload, und ist der Ton gleich?
```

```
Schneide diese fünf Clips und die zwei Fotos zu einem Film mit Titelkarte „Sommerfest“, weichen Überblendungen
und musik.wav darunter.
```

---

### 3.10 Versionen vergleichen (`video-review`)

**Wann:** Sie haben mehrere Fassungen desselben Films mit derselben Zeitachse (V1/V2, alter und neuer Render, zwei
KI-Durchgänge) und möchten pro Einstellung die bessere wählen und daraus eine neue Fassung schneiden – **ohne neu zu
rendern**. Die Bilder werden aus der gewählten Fassung kopiert, der Ton wird unverändert übernommen.

**Was Claude fragt:** welche Dateien die Fassungen sind (2–9), welcher Ton in den neuen Schnitt soll (meist die
neueste Mischung), welche Fassung Einstellungen füllt, die niemand wählt, und woher die Schnittgrenzen kommen: aus
einer Einstellungsliste, aus den Abschnitten eines Song-Projekts oder automatisch aus den Bildern erkannt.

**Ablauf aus Ihrer Sicht:**

1. Claude legt die Review an und misst pro Einstellung, wie verschieden die Fassungen sind.
2. Claude gibt Ihnen die Adresse einer **lokalen Seite** im Browser. Dort laufen alle Fassungen synchron
   nebeneinander, die aktuelle Einstellung in Schleife:
   - `1` … `9` oder Klick wählt eine Fassung,
   - `Leertaste` Wiedergabe/Pause, Pfeiltasten wechseln die Einstellung, `R` startet die Einstellung neu, `S`
     wechselt die Tonquelle,
   - „nur unterschiedliche Einstellungen“ blendet identische aus,
   - jede Wahl wird sofort gespeichert,
   - **„Cut new version“** schneidet die neue Fassung und zeigt sie unter den Playern.
3. Claude vergleicht das Schnittprotokoll mit Ihrer Wahl, schaut einen Kontaktabzug an und spielt den Schnitt einmal
   mit Ton ab.

**Ergebnisse:** `<name>.mp4`, `<name>.log` (welche Fassung pro Einstellung), auf Wunsch `<name>_small.mp4`; Ihre
Wahl in `choice.json`.

**Zusätzlich – Referenzprüfung:** Wird ein bekannter Film nachgebaut (Remake, neue Fassung, die jeden Effekt
behalten muss), erstellt Claude eine Effekt-Checkliste und dichte Vergleichsstreifen an jedem Ereignis (Referenz
oben, Nachbau unten) mit einem Bericht.

**Typische Probleme:** Die Fassungen müssen eine Zeitachse teilen. Weichen die Längen um mehr als 1 s ab, warnt
Claude – dann muss zuerst der Schnitt angeglichen werden. Der Ton kommt immer aus *einer* Fassung; zwischen Fassungen
wird nie übergeblendet. Bei 4K oder sehr hohen Bitraten erzeugt Claude leichtere Browser-Kopien.

**Beispiel-Prompts:**

```
Zeig mir V1 und V2 nebeneinander pro Einstellung.
```

```
Ich habe film_v1.mp4, film_v2.mp4 und film_v3.mp4. Ton von V3, alles was ich nicht wähle aus V2. Schnittgrenzen
aus dem Song-Projekt.
```

```
Schneide aus meiner Wahl eine V4 und mach gleich eine kleine Version unter 30 MB.
```

```
Wir haben den Film nachgebaut – prüf Effekt für Effekt gegen das Original referenz.mp4, was fehlt oder anders ist.
```

---

## 4. Gemeinsame Konzepte

### 4.1 Das Projekt und `project.json`

Jeder Film lebt in einem Projektordner. Die zentrale Datei heißt bei den Song-Filmen und beim 3D-Film
`project.json`, bei kurzen Szenen `short.json`, bei Präsentationsclips `clip.json` bzw. `scene.json`. Darin steht
alles, was den Film bestimmt: Abschnitte, Figuren, Gags, Übergänge, Look, Seed, Ideen. Sie müssen die Datei nicht
selbst bearbeiten – sagen Sie Claude, was Sie wollen.

- **Eine Zeitachse:** Bei allen Song-Filmen sind alle Zeiten Sekunden des Songs. Deshalb passen Szenen, Münder,
  Gags, Liedtext und Geräusche immer zusammen, und jeder Teil lässt sich einzeln neu bauen.
- **Projektprüfung:** Jedes Bauskript prüft die Projektdatei zuerst. Ein falscher Typ, ein unmöglicher Abschnitt
  (Anfang nach Ende, doppelter Name) oder ein unbekannter Übergang stoppt den Bau in Sekunden mit einer Meldung,
  die den Schlüssel nennt. Unbekannte Schlüssel ergeben nur eine Warnung mit Vorschlag („meinten Sie …?“).
- **Bildgröße:** `"size": [Breite, Höhe]` setzt die Bildgröße des Films (Standard 1280×720; bei den 2D-Songfilmen
  16:9 beibehalten, weil die Kulissen 16:9 sind). Das Lyric-Video rendert eigenständig in 1080p, der 3D-Film legt
  seine Größe beim Anlegen fest.

### 4.2 Seed und Ideen – jedes Mal frisch

Das Plugin soll nie zweimal dieselbe Routine abliefern. Jedes Projekt hat einen **Seed** und eine Liste von
**Ideen**:

- **Kreatives Briefing:** Vor dem Bauen liest Claude Liedtext oder Skript und erfindet Ideen, die zu *diesem* Song
  gehören – ein konkretes Bild pro Zeile, Requisiten, Gags, Reaktionen, ein Ende – und notiert sie (`by: "ai"`).
  **Ihre Ideen** werden mit `by: "user"` notiert und gewinnen immer.
- **Der Seed** variiert alles, was die Ideen offenlassen: Tanzstil pro Figur, Kamerawahl, Blinkzeiten,
  Kulissenwahl, Gestenvarianten, die „Würfel“ des Lyric-Videos.
- **Derselbe Seed = derselbe Film. Neuer Seed = eine neue Variante (ein neuer Take).**
- Die Referenzprojekte lehren Techniken, keine Vorlagen.

So steuern Sie das in der Praxis: „Gleicher Film, aber mit neuem Seed“, „Behalte alles, nur die Tanzstile neu
auswürfeln“ oder „Diese Idee ist von mir, die muss rein“.

### 4.3 Der Standard-Film-Look

Der Standard-Look besteht aus **Papiertextur, Filmkorn und Vignette**. Er wird beim Fertigstellen **genau einmal**
über den ganzen Film gelegt (nie doppelt). Varianten pro Filmart:

| Look | Wo | Wirkung |
|---|---|---|
| `standard` | 2D-Filme, Brickfilme, Kurzszenen, Präsentationsclips, Dialoge; auch auf beliebige Videos über `film-tools` | Papier + Korn + Vignette |
| `cinema` | Standard beim 3D-Film | dunkler, tiefere Schatten, warmer Lichthof, Vignette, Korn |
| `ad` | 3D-Film auf Wunsch | hell, weicher Glanz |
| `none` | z. B. Claudia-Filme (Korn und Vignette sind schon in den Einstellungen) | kein zusätzlicher Look |

Neue Looks (anderes Papier, weicheres Korn) lassen sich mit dem optionalen Shaders-Werkzeug erstellen; die
Installation (ca. 40 MB) erfolgt nur nach Ihrer Zustimmung.

### 4.4 KI-Kennzeichnung und Rechte

- **KI-Inhalte werden gekennzeichnet.** Claudia-Filme bekommen in den letzten 3 Sekunden einen Hinweis wie „Bilder
  und Video KI-generiert (…) – Claudia by anabology“. Der Abspann-Entwurf enthält ebenfalls einen
  KI-Hinweis und „Claudia by anabology“, wenn sie vorkommt.
- **Firmennamen nur als neutrale Schrift**, nie Logos; keine echten Politiker.
- Brickfilme heißen nie „LEGO“-Film.

### 4.5 Ausgabedateien

Fast alle Filmarten liefern drei Fassungen, jede auf Decodierfehler geprüft:

| Datei | Zweck |
|---|---|
| `film.mp4` | volle Qualität (zum Archivieren, Weiterbearbeiten, Vorführen) |
| `film_small.mp4` | unter 30 MB, lange Seite höchstens 1280 – für Upload und Messenger |
| `film_mail.mp4` | ca. 12 MB, 960×540 – für E-Mail-Anhänge |

Beim Lyric-Video heißen die Dateien nach dem Songtitel (`<Titel>.mp4`, `_compressed`, `_small`, `_mail`), bei kurzen
Szenen liegen MP4 und GIF in `final/`, bei Präsentationsclips heißt der Clip wie sein Ordner. Wird eine Datei gerade
von einem Player blockiert, bekommt die neue Datei einen neuen Namen – Claude sagt Ihnen das.

### 4.6 Review und Rückmeldung

- Claude schaut sich jedes Ergebnis zuerst selbst an (Kontaktabzug), bevor es Ihnen etwas zeigt.
- Claude kann nicht hören. Synchronität wird gemessen (Wortzeiten, Mund offen gegen Stimme aktiv) und mit earshot
  „abgehört“. Sagen Sie Claude bitte, wenn Ihnen beim Anhören etwas auffällt – Ihr Ohr gewinnt.
- Ihre Korrekturen werden so gespeichert, dass sie jeden weiteren automatischen Lauf überstehen (zum Beispiel
  `corrections.json` für „wer singt was“, die manuelle Auswahl in `selection.json` bei Claudia).
- Für den Vergleich zweier Fassungen gibt es `video-review` (Abschnitt 3.10).

### 4.7 Unterbrochene Renders fortsetzen

Lange Läufe sind so gebaut, dass Sie sie unterbrechen und später fortsetzen können:

- **Nachtlauf (KI-Video):** Fertige Ausgaben werden übersprungen; nach einem Absturz einfach neu starten. Ausgaben
  entstehen zuerst unter einem Zwischennamen (`.part`) und werden erst umbenannt, wenn sie vollständig sind – ein
  abgebrochener Job wird also neu gerechnet, nie fälschlich als fertig genommen. Das Protokoll steht in
  `milestones.log`; lesen Sie es am Morgen oder lassen Sie es Claude zusammenfassen.
- **3D-Film:** Vorschau und Filmrender sind fortsetzbar; es werden nur fehlende Bilder gerendert. Claude kann den
  Stand pro Clip anzeigen.
- **Allgemein:** Zwischenergebnisse werden erst nach erfolgreichem Bau als fertig vermerkt; ein unterbrochener Bau
  sieht nie „frisch“ aus.

Sagen Sie einfach: „Mach weiter, wo der Render abgebrochen ist.“

---

## 5. Tipps und Grenzen

### 5.1 Wie lange dauert was? (gemessen auf dem Referenzrechner)

| Schritt | Dauer |
|---|---|
| Wörter eines 4-Minuten-Songs (Whisper large-v3, GPU) | ca. 1,5 min |
| Gesangstrennung eines 4-Minuten-Songs (Demucs) | ca. 27 s auf der GPU, ca. 2 min auf der CPU |
| FLUX-Bild | ca. 7 s pro Bild nach dem Laden |
| Claudia-Nachtlauf für einen 3-Minuten-Song | ca. 4–7 Stunden |
| Lyric-Video Endrender (3–4 min Song) | ca. 6–10 min |
| Brickfilm mit EEVEE | ca. 0,4–0,6 s pro Bild |
| 3D-Film Vorschau | ca. 1 Stunde für 4 Minuten Film; Filmqualität etwa fünfmal so lang |
| Präsentationsclip | 8 s ca. 1,5 min; 25 s mit vier Figuren ca. 25 min |
| 2D-Zeichentrick | ein Pilot-Refrain geht zügig; ein ganzer Song bedeutet Stunden an Iterationen |

Tipp: Fangen Sie fast immer mit einem **Pilot** an (ein Refrain, ein Abschnitt, ein Clip). Dort lassen sich Stil,
Figuren und Timing billig klären, bevor der ganze Film gebaut wird.

### 5.2 Welche Schritte brauchen eine Grafikkarte?

- **Zwingend:** Claudia-Videos (ComfyUI mit großen Bild- und Videomodellen) und gemalte KI-Hintergründe, Requisiten
  oder Comic-Panels mit FLUX.
- **Praktisch nötig:** 3D-Filme (Cycles), Brickfilme (Blender).
- **Schneller mit GPU, aber mit Ausweichweg:** Whisper (sonst Whisper small auf der CPU, etwas weniger erkannte
  Wörter), Demucs, Depth Anything, Qwen3-TTS-Stimmen (sonst Piper oder Windows-Stimme), Hochskalieren (sonst
  Lanczos).
- **Ohne GPU:** Synfig-Szenen, Schnitt, Look, kleine Versionen, Review.

Immer gilt: **ein KI-Job zur Zeit.** Während ein Nachtlauf läuft, warten andere KI-Schritte.

### 5.3 Datenschutz – alles lokal

Alle Modelle laufen auf Ihrem Rechner; Songs, Präsentationen und Bilder werden nicht hochgeladen. Ausnahmen, die Sie
kennen sollten (jeweils nur nach Rückfrage):

- **ElevenLabs** (Stimmen, Musik, Geräusche) und **MiniMax Hailuo** (Cloud-Video) sind optional. Der Schlüssel kommt
  nur aus einer Umgebungsvariable, wird nie gespeichert oder angezeigt; Texte bzw. Bilder verlassen dann den
  Rechner, und es kostet Geld. MiniMax läuft standardmäßig nur als Probelauf.
- **Google Fonts** im Lyric-Video: Die Vorlage lädt die Schriften bei jedem Render von Google. Für private Renders
  können die Schriftdateien ins Projekt gelegt werden.
- **Downloads** von Programmen, Modellen, Python-Paketen (uv), npm-Paketen, der LDraw-Bibliothek, des
  chrome-headless-shell oder von Referenzbildern passieren nur mit Ihrer Zustimmung.

### 5.4 Regeln des Plugins, die Sie kennen sollten

- **Nichts wird ohne Rückfrage installiert oder heruntergeladen.**
- **Keine Stimmklone echter Personen.** Stimmen werden beschrieben (Alter, Klang, Temperament), nie von realen
  Sprechern geklont.
- **Claudia-Kanon:** genau eine Strähne, genau ein beiges Headset-Mikrofon an ihrer rechten Wange (im Bild links),
  Ende zwanzig, fotografisch, nichts Explizites. Andere Personen bleiben anonym (von hinten, als Silhouette).
- **KI-Inhalte kennzeichnen**, Firmen nur als neutrale Schrift, keine Logos, keine echten Politiker.
- **Ein KI-Modell zur Zeit** auf der GPU; die Sperre eines anderen Jobs wird nie gelöscht, andere Prozesse werden nie
  beendet.
- **Nur eine Sitzung baut die finalen Filmdateien eines Projekts.** Parallele Builds erzeugten früher kaputte MP4s.
- **Ihr Ohr und Ihr Auge gewinnen** gegen jede automatische Messung.

### 5.5 Bekannte Grenzen

- Synfig-Figuren sind Cut-out-Rigs mit flachen Farben; handgezeichnete Effekte (Freudenaugen, weiche Schattierung)
  brauchen zusätzliche Zeichnungen.
- Die automatische Zerlegung von Folienfiguren findet Kopf, Pupillen und Körper; Arme, Schwänze und Flügel brauchen
  noch ein von Hand gesetztes Polygon.
- Schrift in gemalten FLUX-Bildern wird nicht automatisch erkannt – aus dem Kontaktabzug aussortieren.
- In den Tests nicht auf der GPU durchgespielt: Wan2.2-S2V-Jobs, die Live-Bühnenfassung von Claudia,
  Cycles-Brick-Renders.
- Große Bibliotheken und Modelle (LDraw, Modellgewichte) sind nicht enthalten; die Werkzeugprüfung sagt, woher man
  sie bekommt.
- Die Standardwerte (Zeitabschätzungen, „ein Modell zur Zeit“, Modell-Dateinamen) stammen vom Referenzrechner mit
  16 GB Grafikspeicher und lassen sich für andere Hardware anpassen.

### 5.6 Gute Gewohnheiten

- Liedtext **mit Abschnittsmarken** mitgeben, und wenn möglich die **Suno-Stems** aus derselben Fassung.
- Bei einem Ausschnitt sagen, von welcher bis zu welcher Zeile (oder Sekunde).
- Beim Prüfpunkt „Wer singt was“ wirklich reinhören – das spart später viel Arbeit.
- Ideen früh nennen; sie gewinnen immer, kosten aber am Anfang am wenigsten.
- Vor langen Läufen (Nachtlauf, 3D-Filmrender) die Zeitschätzung abwarten und große Programme schließen.

---

## 6. FAQ und Problemlösung

**Muss ich die Skripte selbst ausführen?**
Nein. Claude führt alle Schritte aus. Sie beschreiben, was Sie wollen, und entscheiden an den Prüfpunkten.

**Woher weiß Claude, welche Filmart ich will?**
Aus Ihrer Formulierung („Zeichentrick“, „Brickfilm“, „Lyric-Video“, „Claudia soll singen“, „die Figuren auf Folie 5
sollen …“). Im Zweifel fragt Claude nach. Sie können den Skill auch beim Namen nennen.

**Claude meldet, dass ein Programm fehlt.**
Sagen Sie „Richte animation-studio ein“ oder lassen Sie die Werkzeugprüfung erneut laufen. Claude zeigt, was fehlt
und wofür es gebraucht wird, und fragt vor jeder Installation. Wenn ein Skript mit „'ffmpeg' not found“ stoppt, ist
die Einrichtung noch nicht gelaufen.

**Der Bau stoppt sofort mit einer Meldung zu einem Schlüssel in `project.json`.**
Das ist die Projektprüfung: Ein Wert hat den falschen Typ, Abschnitte überschneiden sich unmöglich, oder ein Übergang
ist unbekannt. Claude korrigiert den genannten Schlüssel. Unbekannte Schlüssel ergeben nur eine Warnung.

**Die falsche Figur singt eine Zeile.**
Sagen Sie Claude, welche Zeile wer singt. Die Korrektur landet in `corrections.json` und bleibt bei jedem weiteren
Lauf erhalten.

**Ein Wort erscheint zu früh oder zu spät im Bild.**
Oft fehlt ein Ruf im Liedtext („Hey!“), oder eine Zeile wird anders gesungen als geschrieben. Claude ergänzt den
Liedtext so, wie er gesungen wird, und analysiert neu – oder korrigiert die Wortzeit von Hand. Die Münder bleiben
davon unberührt.

**Der Text läuft im Lauf des Songs immer weiter weg von der Stimme.**
Stems und Mix stammen nicht aus derselben Fassung (oder haben eine andere Länge). Bei Suno zum Beispiel lag eine
„(Edit)“-Fassung 3,5–4,6 s daneben und driftete. Stems derselben Fassung verwenden.

**Ganze Zeilen wurden nicht erkannt.**
Whisper überhört gesungene Passagen manchmal. Claude startet dann automatisch weitere Durchgänge. Bleiben Zeilen
„geschätzt“, sind es oft gerufene Chants (unkritisch) oder Wiederholungen, die im Liedtext fehlen.

**Die Mundbewegung passt nicht.**
Bei 2D- und Brickfilmen kommen die Münder aus dem Gesang (Rhubarb). Mit Stems wird das deutlich besser. Bei
Claudia-Videos wählen Sie auf der Takes-Seite einen anderen Take oder lassen weitere Seeds rechnen. Bei gesprochenen
Szenen zeigt die Synchronprüfung, ob der Mund offen ist, wenn gesprochen wird.

**Bei Claudia sind zwei Mikrofone im Bild (oder das Mikrofon auf der falschen Seite).**
Das Bildmodell zeichnet in etwa der Hälfte der Varianten einen zweiten Bügel. Startbilder mit diesem Fehler werden
automatisch repariert. Prüfen Sie trotzdem `sheet_start.jpg` mit dem Auge. Ist die Ursache ein Referenzbild mit dem
Mikrofon an der falschen Wange, tauschen Sie das Referenzbild aus.

**Ein Claudia-Clip springt plötzlich in eine andere Szene oder friert ein.**
Solche Clips werden bei der Messung aussortiert. Scheitern alle Seeds einer Einstellung, ist das Standbild mit
Tiefen-Kamerafahrt der offizielle Ausweg – wählbar auf der Takes-Seite.

**In KI-Bildern steht erfundene Schrift.**
FLUX ignoriert „keine Schrift“ gelegentlich. Solche Bilder im Kontaktabzug aussortieren. Echte Schrift setzt das
Plugin immer selbst (Overlays, Typografie-Einstellungen), nie das Modell.

**Der Nachtlauf ist abgebrochen.**
Einfach neu starten lassen. Fertige Ausgaben werden übersprungen, halbfertige neu gerechnet. In `milestones.log`
steht, was passiert ist. Fehlte vor dem Start etwas in ComfyUI, stoppt der Lauf in Sekunden mit einer genauen Liste.

**Der Nachtlauf überspringt eine Phase.**
Die GPU-Sperre war zu lange von einem anderen Job belegt, oder ComfyUI antwortete 15 Minuten nicht. Der Lauf geht mit
der nächsten Phase weiter; die übersprungene lässt sich danach nachholen.

**Der Speicherplatz reicht nicht.**
Der Nachtlauf verlangt standardmäßig 20 GB freien Platz auf dem Projektlaufwerk (und auf dem ComfyUI-Laufwerk, wenn
konfiguriert) und stoppt sonst mit einer Meldung. Auf Wunsch räumt er die Dateien auf, die er selbst in ComfyUI
angelegt hat.

**Der Rechner wird sehr langsam oder ein KI-Job hängt.**
Zwei große Modelle passen nicht gleichzeitig in den Speicher; deshalb gibt es die GPU-Sperre. Schließen Sie andere
große Programme während eines Claudia-Laufs. Claude beendet nie die Prozesse anderer Jobs.

**Das Lyric-Video startet keinen Browser.**
Auf dem Referenzrechner beendete sich Edge im Headless-Modus sofort. Dann wird chrome-headless-shell gebraucht;
Claude lädt ihn nur mit Ihrer Zustimmung herunter.

**Die Ausgabedatei ist riesig.**
Meist ist sich ständig änderndes Filmkorn schuld. Für kleine Fassungen wird mit statischem oder ohne Korn
gerendert; außerdem gibt es immer die `_small`- und `_mail`-Versionen.

**Die neue Filmdatei hat einen anderen Namen als erwartet.**
Die alte Datei war in einem Player geöffnet. Statt den Build abzubrechen, schreibt das Plugin unter einem neuen Namen.
Player schließen und neu bauen lassen, wenn Sie den alten Namen brauchen.

**Ein alter Zeichentrickfilm tanzt nach dem Neurendern anders.**
Seit Version 0.4.19 wählt der Seed einen Tanzstil pro Figur für den ganzen Film. Claude kann die alten Tanzstile
festschreiben, damit der Film bleibt, wie er war.

**Im Protokoll der Stimmen stehen Warnungen („SoX could not be found“, flash-attn, AutoRun).**
Harmlos. Entscheidend ist der Whisper-Wert pro Zeile.

**Eine Stimme spricht ein Wort falsch aus.**
Claude trägt eine Aussprachehilfe ein (`pronounce`), zum Beispiel „Tokanami“ → „Tokka-nahmi“. Die Untertitel bleiben
dabei korrekt geschrieben.

**Ich möchte den Film in Kdenlive oder einem anderen Schnittprogramm weiterbearbeiten.**
Claude erzeugt `film.otio` (Import in Kdenlive 25.04+ oder DaVinci Resolve) und auf Wunsch `film.mlt`. Den Film-Look
nach dem Handschnitt nur einmal anwenden. Synfig-Szenen (`.sif`) lassen sich außerdem in Synfig Studio von Hand
weiteranimieren, gemalte Kulissen als `.kra` in Krita übermalen.

**Kann ich eigene Figuren verwenden?**
Ja: als Inkscape-SVG nach der Rig-Konvention für 2D (Musikvideo, Dialog, Kurzszene), als Beschreibung (Shirtfarbe,
Haare, Brille) für Brickfilme, als eigene Figurenklasse im 3D-Film, und als gezeichnete Figuren aus Folien bei den
Präsentationsclips. Legen Sie eigene Figuren in den Projektordner, nicht in den Plugin-Ordner.

**Wo finde ich die Fachdetails?**
Im Plugin-Ordner: `README.md` (Überblick), `TOOLS.md` (Programme und Modelle), `skills/<skill>/SKILL.md` (Ablauf
jeder Filmart), `skills/<baustein>/BLOCK.md` (Bausteine) und die `references/` der Skills (Lektionen,
Referenztests, Techniken).
