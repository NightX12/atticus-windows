# Roadmap: Atticus für Windows

Stand: 26.10.2026. Basis: Fork `NightX12/atticus-windows` (= Upstream FindlayHi, Merge mit atticus-mac bis `eba8597`, 13.10.2026).

## 1. CI-Stand und Testfehler

- **Upstream (FindlayHi):** Workflow `Checks` (windows-latest) zuletzt am 14.10.2026 grün (5/5 letzte Läufe erfolgreich). Er führt die Python-Unittests, `atticus.py --selftest`, `dotnet build` + `Atticus.exe --selftest` und eine PowerShell-Syntaxprüfung aus.
- **Fork (NightX12):** bisher keine Actions-Läufe (Actions im Fork noch nicht aktiviert/ausgelöst).
- **Lokal (Linux):** 50 Tests, 21 Errors, 1 Skip. **Alle 21 hängen an der Umgebung, keiner ist ein echter Logikfehler:**
  - ca. 16× `winctl` ist `None` (Import von `ctypes.wintypes`/`windll` schlägt außerhalb von Windows fehl → `AttributeError` bei `apps`, `bash`, `kill_tree`, `rect_for`, `find`, `focus_app`, `secret_set`, `UI_FILE`, `joplin`).
  - 3× `PermissionError` auf Fake-`*.cmd`-Dateien (unter Linux nicht ausführbar, Windows startet `.cmd` direkt).
  - 2× `FileNotFoundError` (`child-survived`, `action`): Folge der fehlenden Prozessbaum-/Job-Object-Logik bzw. des nicht laufenden Fake-CLI.
- **Empfehlung:** Tests mit `@unittest.skipUnless(sys.platform == 'win32')` markieren bzw. `winctl` per Fake-Backend ersetzbar machen (siehe Abschnitt 3); verbindlich bleibt die Windows-CI.

## 2. Lückenliste Mac-Kern vs. Windows-Kern

Mac `atticus.py` 7.798 Zeilen / ~325 Funktionen; Windows `atticus.py` 1.904 + `winctl.py` 969 Zeilen / ~156 Funktionen. Ca. 270 Mac-Funktionen fehlen. Gruppiert:

| Prio | Bereich | Fehlende Funktionen (Auszug) | Nutzen | Aufwand | Abhängigkeiten |
|---|---|---|---|---|---|
| 1 | Hands (Klick/Tippen/Scrollen) | `hands*`, `fast_hands`, `cached_hands`, `window_target`, `window_text`, `point_context` | sehr hoch | M | UI Automation (`uiautomation`), `SendInput` in winctl |
| 2 | Plattform-Schicht | (neu, s. Abschnitt 3) | hoch (Merge-Kosten) | M | – |
| 3 | Agents / Hintergrundarbeit + Mini-Screen | `Agents`, `agent_*` (~30), `managed_agent`, `named_agents`, `work_page`, `background_tab` | sehr hoch | L | Hands, Browser-Adapter, C#-Fenster für Mini-Screen |
| 4 | Browser-Steuerung | `browser_adapter`, `page_ready`, `text_page`, `allow_page_js`, `handed_page` | hoch | M | Chrome/Edge per CDP statt AppleScript, `ui/web.js` |
| 5 | Diktat + Cleanup | `dictate_*` (~15), `dictation_event` | hoch | M | Speech.cs (vorhanden), Caret-Einfügen per UIA/Clipboard |
| 6 | Auswahl umschreiben / Text am Cursor | `selection_context`, `replacement_reply` | mittel-hoch | S | Hands, Clipboard |
| 7 | Routinen | `routine_*` (~12) | mittel | S | Windows Task Scheduler (`schtasks`) statt launchd |
| 8 | Profil & Gedächtnis | `profile_*`, `memory_*`, `_save_profile`, `remember_rule`, `forget_rules` | mittel | S | rein Python, kaum plattformabhängig → direkt übernehmen |
| 9 | Meeting Copilot | `meeting_*` (~20) | hoch | L | WASAPI-Loopback in C#, Transkription |
| 10 | Bildschirm zeichnen | `draw`, `draw_target`, `drawing*` | mittel | M | Overlay.cs |
| 11 | Modellwahl / Routing / Devin / Pi | `models`, `routing_mode`, `run_devin`, `pi_plan`, `claude_plan` | mittel | S | rein Python |
| 12 | Feedback/Telemetrie/Fehlerbericht | `feedback`, `report_error`, `telemetry_enabled`, `install_exception_hooks` | niedrig-mittel | S | – |
| 13 | Kontakte, Kalender | `contacts`, `contact_matches`, `calendar_*` | mittel | M | Outlook/People-API bzw. Google-Connector |
| 14 | Spotify, Menüleiste | `_spotify_*`, `menu_bar_*`, `osa*` | niedrig | S/–| Spotify Web-API bzw. SMTC; Menüleiste → Tray, `osa` entfällt |

Reihenfolge-Logik: zuerst die plattformneutralen Python-Teile (8, 11, 12) "gratis" übernehmen, dann Plattform-Schicht, dann Hands als Fundament für Agents/Browser/Selektion.

## 3. Plattform-Abstraktionsschicht

Ziel: `atticus.py` bleibt so nah wie möglich am Mac-Original, damit Upstream-Merges fast konfliktfrei laufen. Plattformcode wandert hinter schmale Interfaces.

```
platform/
  __init__.py      # wählt Backend: win32 → windows, darwin → mac, sonst fake
  base.py          # Protocols / abstrakte Klassen
  windows/         # heutiges winctl.py, aufgeteilt
    apps.py  windows.py  input.py  screen.py  clipboard.py
    secrets.py  process.py  scheduler.py  browser.py  audio.py
  fake.py          # deterministisches Test-Backend (Linux-CI, Unittests)
```

Interfaces (`base.py`):
- `Apps`: `installed()`, `running()`, `launch(name)`, `quit(name)`, `focus(name)`
- `Windows`: `list()`, `rect_for(win)`, `move(win, rect)`, `work_area()`, `front()`
- `Hands`: `click(target)`, `type_text(s)`, `key(combo)`, `scroll(dx,dy)`, `tree(win)` (UIA)
- `Screen`: `capture(win|None)`, `ocr(img)`
- `Clipboard`: `get()`, `set()`, `selection()`
- `Secrets`: `get/set/delete` (Windows Credential Manager)
- `Process`: `run_shell(cmd)`, `kill_tree(pid)` (Job Objects)
- `Scheduler`: `install(routine)`, `remove(id)` (schtasks)
- `Browser`: `open`, `read_page`, `click`, `eval` (CDP)
- `Audio`: `loopback_start/stop` (WASAPI, über C#-Host)

Regeln:
1. `atticus.py` importiert nur `platform` – nie `ctypes`, `osascript` o. ä.
2. Mac-Aufrufe (`osa(...)`) im Original werden beim Merge durch `platform.<x>` ersetzt; diese Stellen in einer Mapping-Tabelle `docs/MERGE.md` pflegen.
3. Langfristig das Interface upstream an atticus-mac vorschlagen – dann wird jeder Merge trivial.
4. Tests laufen gegen `fake.py` auf Linux; native Tests (`*_native.py`) nur auf Windows-CI.

## 4. Nächste Arbeitspakete (Top 5)

1. **AP2 – Plattform-Schicht + Fake-Backend**: `winctl.py` in `platform/windows/` aufteilen, `fake.py`, Linux-Tests grün; Fork-Actions aktivieren. (M)
2. **AP3 – Plattformneutrale Kernteile übernehmen**: Profil/Gedächtnis, Modelle/Routing, Feedback/Telemetrie aus atticus-mac portieren inkl. Tests. (S–M)
3. **AP4 – Hands auf Windows**: UIA + `SendInput`, `hands*`-Funktionen, Tests `test_hands*`. (M)
4. **AP5 – Browser via CDP + Auswahl umschreiben**: Grundlage für Agents. (M)
5. **AP6 – Routinen über Task Scheduler + Diktat-Cleanup**. (S–M)

Danach: Agents/Mini-Screen (L), Meeting Copilot mit WASAPI-Loopback (L).
