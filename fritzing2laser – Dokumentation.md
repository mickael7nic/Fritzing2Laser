# fritzing2laser – Dokumentation

Nov 28, 2026 · @Michi

## Vorstellung

**Platinen aus Fritzing direkt mit dem Laser herstellen: mit dem CO2-Laser über Ätzlack oder mit dem Faserlaser direkt ins Kupfer.**

fritzing2laser ist ein kleines Python-Programm mit grafischer Oberfläche. Es nimmt den Kupferexport und die Bohrdatei aus Fritzing und macht daraus fertige Laserdaten. Mit dem CO2-Laser entfernt man damit Ätzlack und ätzt danach; mit einem Faserlaser wie dem xTool F1 Ultra trägt man das Kupfer direkt ab, bohrt, schneidet die Platine aus und lasert den Bestückungsdruck.

Entstanden ist es aus einem praktischen Problem: Die Fritzing-SVGs lassen sich nicht einfach in die Laser-Software laden. Die Lage muss richtig gespiegelt sein, Leiterbahn-Enden ragen in die Bohrlöcher, und eine reine Flächengravur legt Spalten quer zur Scanrichtung schlecht frei. Das Programm löst das automatisch.

**Was es kann**

- **Zwei Profile:** „CO2 + Lack“ und „Faserlaser direkt“ mit passenden Abständen für den jeweiligen Spot.
- **Vektor-Modus:** füllt die Isolationsspalten mit parallelen Linien entlang der Leiterbahnen, gleich gut in jeder Richtung.
- **Isolationsbreite:** beim Faserlaser nur ein Streifen fester Breite um die Leiterbahnen; das übrige Kupfer bleibt stehen, das spart viel Laserzeit.
- **Saubere Bohrlöcher:** erkennt jedes Padloch, entfernt hineinragende Leiterbahn-Enden und setzt einen runden, mittigen Zentrierpunkt.
- **Bohren und Ausschneiden:** Bohrkreise mit Nennmaß und Platinenumriss als eigene Dateien.
- **Lötstopp und Bestückungsdruck:** Pads im Lötstopplack freilegen und den Bestückungsdruck auf der Oberseite lasern, deckungsgleich nach dem Wenden.
- **Prüfungen:** Spiegelung der Bohrdatei, falsche Eingabedatei, Bohrdatei einer anderen Platine.
- **Praktisch:** Drehung in 90°-Schritten, Texte weglassen (inklusive ihrer Aussparung in der Massefläche), Historie der letzten 10 Projekte.
- **Offen für jede Laser-Software:** SVG und DXF in mm, erprobt mit M-Design Hub, geeignet für LightBurn und xTool Studio.

Das Programm läuft unter Linux, braucht Python und vier frei verfügbare Bibliotheken und lässt sich auch ohne Oberfläche auf der Kommandozeile nutzen.

## Überblick

fritzing2laser macht aus einem Fritzing-Kupferexport (SVG) und der Bohrdatei Laserdaten, mit denen ein CO2-Laser den Ätzlack von lackierten Platinen entfernt. Danach wird geätzt und gebohrt.

Die Ausgaben sind normale SVG- und DXF-Dateien in mm. Sie funktionieren in M-Design Hub (Monport) und in LightBurn, grundsätzlich auch in jeder anderen Laser-Software, die SVG oder DXF importiert.

Arbeitsablauf:

1. In Fritzing die Kupfer-SVG und die Bohrdatei exportieren, für den Faserlaser bei Bedarf auch Lötstopp- und Bestückungsdruck-SVG.
2. Dateien in fritzing2laser laden, Profil wählen und die Laserdaten erzeugen (SVG und DXF).
3. **CO2 + Lack:** Platine entfetten und dünn mit Acryllack beschichten, Lack weglasern, ätzen, Lack mit Aceton entfernen, an den Zentrierpunkten bohren.
4. **Faserlaser direkt:** Kupfer abtragen, bohren und Platinenkontur schneiden, Platine wenden und den Bestückungsdruck lasern.

Das Programm besteht aus diesen Dateien, alle im selben Ordner:

| Datei | Zweck |
| --- | --- |
| `fritzing2laser.py` | Rechenkern, auch direkt auf der Kommandozeile nutzbar |
| `fritzing2laser_gui.py` | grafische Oberfläche mit Projekt-Historie |
| `fritzing2laser.desktop` | Starter für Anwendungsmenü und Dock (Linux) |
| `OCR-Fritzing-mono.ttf` | optional: Originalschrift für Kupfertexte |

Die Versionsangabe steht in der ersten Protokollzeile, aktuell `2026-11-28`.

## Einrichtung (Linux)

Das Programm braucht Python 3.10 oder neuer, tkinter für die Oberfläche und vier Pakete aus pip. Auf aktuellen Debian- und Ubuntu-Systemen werden die Pakete in eine eigene Umgebung (venv) im Programmordner installiert, weil pip dort keine systemweite Installation zulässt.

| Paket | Wofür |
| --- | --- |
| `resvg-py` | rendert die Fritzing-SVG exakt in ein Rasterbild |
| `opencv-python-headless` | Konturen, Abstände, Loch-Erkennung |
| `numpy` | Rechnen mit dem Rasterbild |
| `ezdxf` | schreibt die DXF-Dateien |
| `tkinter` (Systempaket `python3-tk`) | grafische Oberfläche |

**1. Systempakete installieren**

```bash
sudo apt install python3 python3-venv python3-tk
```

**2. Programmdateien ablegen**, zum Beispiel in `~/Fritzing/Laser/`. Beide `.py`-Dateien müssen im selben Ordner liegen.

**3. venv anlegen und Pakete installieren**

```bash
cd ~/Fritzing/Laser
python3 -m venv .venv --system-site-packages
.venv/bin/pip install resvg-py opencv-python-headless numpy ezdxf
```

`--system-site-packages` sorgt dafür, dass die venv das tkinter des Systems mitbenutzt. Bricht `resvg-py` mit einem Fehler zu Rust oder `cargo` ab, gibt es für diese Python-Version kein fertiges Paket; dann eine andere Python-Version für die venv verwenden.

**4. Originalschrift (optional)**

Für Kupfertexte in der Fritzing-Schrift `OCR-Fritzing-mono.ttf` aus [fritzing-app/resources/fonts](https://github.com/fritzing/fritzing-app/tree/develop/resources/fonts) neben die Programmdateien legen. Ohne sie nimmt das Programm eine Ersatzschrift. Wer Texte ohnehin weglässt, braucht sie nicht.

**5. Starten**

```bash
~/Fritzing/Laser/.venv/bin/python ~/Fritzing/Laser/fritzing2laser_gui.py
```

**6. Starter mit Logo (optional)**

Die GUI legt beim ersten Start ihr Logo unter `~/.local/share/icons/` ab. Danach den Starter installieren:

```bash
cp fritzing2laser.desktop ~/.local/share/applications/
```

„Fritzing → Laser“ erscheint dann im Anwendungsmenü und lässt sich ans Dock heften. In der `.desktop`-Datei stehen die Pfade fest eingetragen; bei einem anderen Ordner dort `Path` und `Exec` anpassen.

**Windows:** Python von python.org installieren (tkinter ist enthalten), dann `py -m pip install resvg-py opencv-python-headless numpy ezdxf` und `py fritzing2laser_gui.py`. Getestet ist das Programm nur unter Linux.

## Dateien aus Fritzing exportieren

Gebraucht werden zwei Dateien aus demselben Export-Ordner: die Kupfer-SVG der Lage, die gelasert wird, und die Bohrdatei.

| Datei | Fritzing-Menü | Hinweis |
| --- | --- | --- |
| `<Name>_etch_copper_bottom_mirror.svg` | Datei → Exportieren → für die Produktion → Ätzbar (SVG) | Kupferlage; gespiegelt ist richtig, wenn direkt auf die Kupferseite gelasert wird |
| `<Name>_drill.txt` | Datei → Exportieren → für die Produktion → Extended Gerber | aus dem Gerber-Export nur diese Datei verwenden |
| `<Name>_etch_mask_bottom_mirror.svg` | wie die Kupfer-SVG (Ätzbar) | optional: Lötstoppmaske, gleich gespiegelt wie das Kupfer |
| `<Name>_etch_silk_top.svg` | wie die Kupfer-SVG (Ätzbar) | optional: Bestückungsdruck Oberseite, **nicht** gespiegelt |

Die Bohrdatei liegt immer in der Draufsicht vor. Ob sie gespiegelt werden muss, erkennt das Programm an der SVG und prüft es zusätzlich an den Pads. Die Menünamen können je nach Fritzing-Version leicht abweichen.

Alle Dateien sollten im selben Ordner liegen: Die GUI trägt dann beim Wählen der Kupfer-SVG Bohrdatei, Lötstopp- und Bestückungsdruck-SVG automatisch ein. Darauf achten, im Feld „Kupfer-SVG“ wirklich die `_etch_copper_`-Datei zu wählen; bei einem anderen Namen fragt die GUI nach.

## Bedienung der Oberfläche

Die Oberfläche ist von oben nach unten in fünf Bereiche geteilt. Ein normaler Durchlauf: SVG wählen, Einstellungen prüfen, „Erzeugen“ klicken, Protokoll lesen.

**Dateien**

- **Kupfer-SVG:** der Fritzing-Export. Beim Wählen wird `<Name>_drill.txt` aus demselben Ordner automatisch als Bohrdatei eingetragen; gibt es keine, wird das Feld geleert.
- **Bohrdatei:** für runde Zentrierpunkte und die Spiegelprüfung. Ohne Bohrdatei fragt das Programm nach, weil die Fritzing-Löcher dann angeschnitten bleiben.
- **Schrift:** optional, siehe Einrichtung.
- **Ausgabeordner:** leer = Ordner der SVG.
- **Dateinamen-Präfix:** leer = Name der SVG ohne `_etch…`.

**Einstellungen** – alle Werte und ihre Wirkung stehen im nächsten Abschnitt. Dezimalzahlen gehen mit Komma oder Punkt.

**Ausgabe** – Häkchen für Vektor, Gang 1 Fläche, Gang 2 Kontur und „Texte im Kupfer weglassen“. „Standardwerte“ setzt alle Einstellungen zurück, die Dateien bleiben.

**Buttons**

- **▶ Erzeugen:** schreibt die gewählten Laserdateien.
- **◯ Bohrlöcher rund (SVG):** schreibt nur eine Kopie der Fritzing-SVG mit kreisrunden Löchern (`<Name>_rund.svg`).
- **Ausgabeordner öffnen:** öffnet den Ordner im Dateimanager.

**Letzte Projekte und Protokoll**

- Die Liste zeigt die letzten 10 Platinen mit ihren Einstellungen, je Platine den letzten Lauf. Doppelklick oder „Laden“ holt alles zurück in die Maske, „Entfernen“ löscht den Eintrag. Gespeichert wird in `~/.fritzing2laser_history.json`.
- Beim Start lädt die GUI das zuletzt benutzte Projekt.
- Das Protokoll zeigt Version und Pfad des Rechenkerns, die Spiegelprüfung, die Lochkorrektur und die geschriebenen Dateien. Liegen SVG und Bohrdatei in verschiedenen Ordnern, fragt die GUI vor dem Start nach.

## Optionen

Alle Einstellungen gibt es in der GUI und auf der Kommandozeile. Die Standardwerte passen für einen CO2-Spot von etwa 0,1 mm.

| GUI-Feld | Kommandozeile | Standard | Wirkung |
| --- | --- | --- | --- |
| Abstand 1. Linie zur Kupferkante \[mm\] | `--offset` | 0.05 | Versatz der Kontur in die Laserfläche, etwa halber Spotdurchmesser; so wird die Leiterbahn nicht schmaler |
| Linienabstand Vektor \[mm\] | `--step` | 0.06 | Abstand der parallelen Linien im Vektor-Modus; kleiner als der Spot wählen |
| Anzahl Linien um Kupferbahnen | `--lines` | 0 | 0 = Spalten vollständig füllen; N = höchstens N Linien je Kupferkante, Rest bleibt als Kupferinsel stehen |
| Zentrierpunkt Bohrung Ø \[mm\] | `--mark` | 0.5 | runder Punkt in jeder Bohrung, wird mitgeätzt; 0 = Pad bleibt voll Kupfer |
| Lochdurchmesser runde Löcher \[mm\] | `--hole` | 0 | nur für „Bohrlöcher rund (SVG)“; 0 = Lochgröße wie in der SVG |
| Rasterauflösung \[px/mm\] | `--res` | 100 | 100 = 0,01 mm Genauigkeit; höher braucht deutlich mehr Speicher und Zeit |
| Vereinfachungstoleranz \[mm\] | `--eps` | 0.012 | größer = weniger Punkte und kürzere Pfade, aber gröbere Rundungen |
| Drehung \[°\] | `--rotate` | 0 | 0, 90, -90 oder 180; plus = gegen den Uhrzeigersinn, Nullpunkt bleibt unten links |
| Bohrungen spiegeln | `--mirror` | auto | auto = wie die SVG; ja/nein nur, wenn das Protokoll eine Warnung zeigt |
| Texte im Kupfer weglassen | `--no-text` | aus | entfernt alle Fritzing-Texte aus der Kupferlage |
| Ausgabe Vektor / Gang 1 / Gang 2 | – | alle an | auf der Kommandozeile werden immer alle drei erzeugt |
| Ausgabeordner | `-d`, `--outdir` | Ordner der SVG | Zielordner |
| Dateinamen-Präfix | `-o`, `--prefix` | Name der SVG | Anfang der Ausgabedateinamen |
| Schrift | `--font` | neben dem Script | Pfad zu `OCR-Fritzing-mono.ttf` |
| Button „Bohrlöcher rund (SVG)“ | `--round-holes` | – | erzeugt nur `<Name>_rund.svg` |

## Ausgabedateien und Nutzung in M-Design Hub und LightBurn

Jede Ausgabe gibt es als SVG und als DXF mit identischer Geometrie, in mm, Nullpunkt unten links. Alle Dateien einer Platine haben dieselben Koordinaten und liegen deshalb deckungsgleich übereinander.

| Datei | Inhalt | Modus (M-Design Hub / LightBurn) |
| --- | --- | --- |
| `<Name>_Vektor.svg/.dxf` | Spalten mit parallelen Linien gefüllt, inklusive Zentrierpunkten; ersetzt Gang 1 und 2 | Cut/Linie, 1 Durchgang – empfohlen |
| `<Name>_Gang1_Flaeche.svg/.dxf` | geschlossene Flächen = Lack weg, schwarze Even-Odd-Füllung | Fill/Gravur |
| `<Name>_Gang2_Kontur.svg/.dxf` | Kanten der Flächen, um den Offset versetzt | Cut/Linie, nach Gang 1 |
| `<Name>_rund.svg` | Kopie der Fritzing-SVG mit kreisrunden Löchern | für Tonertransfer oder als Bild, nicht als Vektor zum Lasern |

Empfehlung aus den Tests: den Vektor-Modus nehmen. Er läuft immer entlang der Spalten, deshalb werden Spalten quer zur Scanrichtung genauso gut freigelegt wie längs. Mit Gang 1 als Flächengravur blieb quer zur Scanrichtung oft Lack stehen.

In `_rund.svg` sind die neuen Löcher weiß gefüllte Kreise. Als Vektor importiert, könnte die Laser-Software sie als eigene Objekte lasern.

**In LightBurn**

- Datei über Datei → Importieren laden; SVG und DXF kommen in mm und in Originalgröße an. Alles Schwarze landet auf demselben Layer.
- Vektor-Datei: Layer auf Modus **Line**, 1 Durchgang.
- Gang 1 und 2 zusammen: beide Dateien importieren, Gang 2 auf einen eigenen Layer legen (Modus Line), Gang 1 auf **Fill**. In der Layer-Liste Gang 1 vor Gang 2 sortieren. Verschachtelte Konturen füllt LightBurn abwechselnd, wie die Even-Odd-Füllung es vorsieht.
- Beim Platzieren nichts skalieren und nichts verschieben, solange mehrere Dateien deckungsgleich bleiben sollen: am einfachsten alle Teile zusammen markieren und gemeinsam bewegen.

## Kommandozeile

Der Rechenkern lässt sich ohne Oberfläche aufrufen, zum Beispiel für Skripte. `py` steht hier für `.venv/bin/python` im Programmordner.

```bash
# Standard: alle Ausgaben neben die SVG
py fritzing2laser.py Platine_etch_copper_bottom_mirror.svg Platine_drill.txt

# 3 Linien je Kupferkante, ohne Texte, in eigenen Ordner
py fritzing2laser.py Platine.svg Platine_drill.txt --lines 3 --no-text -d laser

# um 90 Grad gedreht, breiterer Spot
py fritzing2laser.py Platine.svg Platine_drill.txt --rotate 90 --offset 0.07 --step 0.08

# nur Kopie der SVG mit runden 0,6-mm-Löchern
py fritzing2laser.py Platine.svg Platine_drill.txt --round-holes --hole 0.6

# alle Optionen anzeigen
py fritzing2laser.py -h
```

## So arbeitet das Programm

Das Programm rechnet auf einem Rasterbild mit 0,01 mm Auflösung und wandelt das Ergebnis zurück in Vektoren. So werden alle Fritzing-Elemente genau so berücksichtigt, wie Fritzing sie zeichnet.

1. **Rendern:** Die SVG wird ohne Platinenumriss (und auf Wunsch ohne Texte) exakt in Zielgröße gerastert. Schwarz = Kupfer, weiß = Lack weg.
2. **Bohrdatei einlesen:** Excellon in Zoll oder mm; ist die SVG gespiegelt, werden die Bohrungen ebenfalls gespiegelt.
3. **Spiegelprüfung:** Für beide Spiegelungen wird gezählt, wie viele Bohrungen mittig in einem runden Pad liegen. Passt die andere Variante besser, erscheint eine Warnung.
4. **Lochkorrektur:** Fritzing zeichnet Leiterbahn-Enden über die Padlöcher; dadurch sind die Löcher angeschnitten oder in Teilstücke zerlegt. Alle Teilstücke eines Lochs werden zusammengefasst und mit Kupfer aufgefüllt. Der Lochmittelpunkt wird per Kreis-Fit auf den unbeschädigten Bogen bestimmt; bei stark angeschnittenen Löchern übernimmt er den Versatz der nächsten sicher erkannten Nachbarlöcher. Dort sitzt dann ein runder Zentrierpunkt.
5. **Konturen:** Gang 1 = Umrisse der Laserflächen; Gang 2 = dieselben Flächen um den Offset verkleinert; Vektor = Linien in festen Abständen von der Kupferkante, berechnet über eine Abstandskarte.
6. **Schreiben:** Drehung anwenden, Pfade vereinfachen, SVG und DXF in mm schreiben.

## Laser und Lack

Am wichtigsten ist ein dünner Acryllack. Hitzebeständiger Auspufflack brauchte so viel Energie, dass sich stellenweise das Kupfer vom Träger löste. Die Werte unten sind Startpunkte, keine gemessenen Ergebnisse: auf einem Reststreifen testen.

**Lack**

- Geeignet: schwarzer Acryl-Sprühlack matt oder Acryl-Schutzlack (z. B. Kontakt Chemie Plastik 70). Beim Teslanol T7 nennt das Datenblatt keine Harzbasis; er ist in Aceton gelöst und blau eingefärbt, also wahrscheinlich Acryl.
- Ungeeignet: Silikon-, PU- und hitzebeständige Lacke sowie Lötlack.
- Kupfer entfetten und leicht anschleifen, 2 dünne Schichten, über Nacht trocknen.
- Nach dem Lasern kurz mit Isopropanol überwischen, nach dem Ätzen den Lack mit Aceton entfernen.

**M-Design Hub**

- Fokus exakt auf die Lackoberfläche.
- Vektor-Datei im Cut-/Linienmodus, 1 Durchgang. Test mit 10 mm/s und 20 % begann gut, war aber an kurzen Stellen teils zu stark: die Leistung in kleinen Schritten senken.
- M-Design Hub hat je Layer nur einen Leistungswert. Bei kurzen Segmenten senkt die Steuerung die Leistung, sodass die Röhre dort teils nicht zündet; langsamer fahren hilft.
- Flächengravur (Gang 1): DPI = 25,4 / Zeilenabstand. Startwert 400 DPI (0,064 mm); bleiben Streifen, 500 DPI. Overscan einschalten, wenn vorhanden.
- Ist die Linie deutlich breiter als 0,1 mm, `Abstand 1. Linie` auf die halbe Linienbreite setzen.

**LightBurn**

LightBurn bietet bei vielen Steuerungen (z. B. Ruida) zwei Leistungswerte je Layer. Damit lässt sich das Problem mit kurzen Segmenten direkt lösen.

- Im Line-Layer **Min-Leistung gleich Max-Leistung** oder knapp darunter setzen, mindestens aber über der Zündschwelle der Röhre. Dann feuert der Laser auch in engen Bögen und auf kurzen Strecken.
- Im Fill-Layer **Line Interval** etwa 0,05–0,08 mm, **Overscanning** einschalten und bei Bedarf **Crosshatch** für eine zweite Füllrichtung um 90°.
- Die Wegoptimierung von LightBurn kann die Reihenfolge der Linien ändern. Wird es an kleinen Stellen zu heiß, langsamer fahren oder die Leistung senken.

## Fehlersuche

| Problem | Ursache | Lösung |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'cv2'` | Pakete fehlen oder falsches Python | mit `.venv/bin/python` starten, Pakete wie unter Einrichtung installieren |
| Löcher halb frei, winzige Löcher in Leiterbahnen | Bohrdatei fehlt oder gehört zu einer anderen Platine | Protokoll muss `Padlöcher rund ersetzt: …` zeigen; SVG neu wählen, damit die passende Bohrdatei eingetragen wird |
| Zentrierpunkte an Stellen ohne Bohrung | Spiegelung falsch | Protokollzeile `passend zu Pads: X (andere Spiegelung: Y)`; bei Warnung „Bohrungen spiegeln“ umstellen |
| Änderungen am Programm wirken nicht | alte `fritzing2laser.py` im Ordner, z. B. als `fritzing2laser(1).py` heruntergeladen | erste Protokollzeile zeigt Version und Pfad; Datei ersetzen, GUI neu starten |
| Schrift sieht anders aus als in Fritzing | Originalschrift fehlt | `OCR-Fritzing-mono.ttf` neben das Script legen oder Texte weglassen |
| Lack quer zur Scanrichtung bleibt stehen | Flächengravur mit zu kurzen Segmenten | Vektor-Modus nehmen |
| Kupfer löst sich an kleinen Stellen | zu viel Energie auf engem Raum | Leistung senken, dünneren Acryllack verwenden |
| Logo erscheint nicht im Dock | Starter nicht installiert | `fritzing2laser.desktop` nach `~/.local/share/applications/` kopieren |
