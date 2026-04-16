# PDFBread

PDFBread is a desktop PDF presenter for dual-screen talks with an optional NDI output path.

## What It Does

- Opens multiple PDF decks in separate tabs.
- Shows the audience presentation on one screen and a teleprompter view on another.
- Keeps a presenter console in the main app window with slide thumbnails and a large current-slide preview.
- Supports optional NDI output for both the main presentation feed and the teleprompter feed.
- Lets you keep per-tab timers while also defining a default timer duration in settings.

## Current Workflow

- `Открыть PDF` loads a PDF into the current tab.
- `+` creates a new empty PDF tab.
- `Настройки` opens a separate settings window for:
  - output screens;
  - global NDI configuration;
  - default timer duration for tabs.
- `Запуск` starts the presentation and teleprompter outputs.
- While a deck is live, switching to another PDF tab allows sending that tab to output with `Вывести вкладку`.

## Controls

- Click the large slide preview to go forward.
- Use `Left/Right`, `Up/Down`, `PageUp/PageDown`, `Space`, or `Backspace` to navigate.
- Press `Esc` in the fullscreen output windows to stop the live output.

## Timer Logic

- Each PDF tab has its own timer.
- Settings only define the default duration.
- `Из настроек` inside a tab copies the default duration to that tab.
- `Применить ко всем вкладкам` applies the default duration to every open PDF tab.

## NDI

- NDI is optional.
- To use it on Windows, install `NDI Tools` or `NDI Runtime`.
- PDFBread can publish:
  - `Main` feed;
  - `Teleprompter` feed.
- NDI is configured once in the settings window and applies to all tabs.

## Quick Start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pdfbread
```

Or use the included launchers:

- `run_pdfbread_gui.bat`
- `run_pdfbread.bat`

## Build EXE

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\build_exe.ps1
```

The build output will appear in:

```text
dist\PDFBread\PDFBread.exe
```

## Project Layout

- `src/pdfbread/` — application source code
- `icon.png` — application icon
- `run_pdfbread*.bat/.ps1` — Windows launch helpers
- `build_exe.ps1` — PyInstaller build script

