# Gibberish Rewriter

A Windows tray app that fixes text typed on the wrong keyboard layout (English US ↔ Arabic 101).
Typed `اثممخ` on the Arabic layout when you meant `hello`? Press the hotkey and it becomes `hello`, and the layout switches to English.

| Hotkey | Action |
|---|---|
| Shift + CapsLock + Tab | Fix what I just typed |
| Shift + CapsLock + `` ` `` | Fix selected text |
| The same hotkey again, before any other input | Undo that fix |

## How it works

- **Fix what I just typed.** The app remembers the keys you typed since the last Enter, Tab, arrow key, click or window change. The hotkey deletes that text with Backspaces, types what the same keys give on the other layout, and switches the window's layout.
- **Fix selected text.** The hotkey copies the selection, converts it, pastes it back, and restores your clipboard. Pasting keeps line breaks intact and doesn't press Enter, so chat apps don't send half a message.
- **Undo.** Press the same hotkey again before typing anything else and the fix is reversed.

In console windows (Windows Terminal, the classic console) a selection fix pastes at the cursor instead of replacing the selection, because consoles don't let an app replace selected text.

There are two implementations with the same behavior, the **C# app** and the **Python app**. Run whichever you like — but only one at a time: they share one instance lock, one config file and one autostart entry.

## Requirements

- Windows 10 or 11, 64-bit.
- The **English (US)** and **Arabic (101)** keyboard layouts installed (Settings → Time & language → Language & region). Other Latin/Arabic layouts work if you put their HKL codes in the config file (see below).
- To build: the .NET 10 SDK (`winget install Microsoft.DotNet.SDK.10`). Not needed to run a published copy.

## Run it from source

```powershell
dotnet build csharp\GibberishRewriter.slnx
.\csharp\src\GibberishRewriter.App\bin\Debug\net10.0-windows\GibberishRewriter.exe
```

A blue icon with a white `ع` appears in the tray. Its menu has **Enabled**, **Open config file**, **Start with Windows** and **Exit**. Only one copy runs at a time.

The Python app is the same app again: set it up once with `cd python`, `python -m venv .venv` and `.venv\Scripts\python.exe -m pip install -e ".[dev]"`, then start it with `.venv\Scripts\python.exe -m gibberish_rewriter`. Its tray icon says Python in the tooltip, and it reads the same config file and the same `shared\` folder as the C# app.

Either app shows a notification when it starts, naming the two layouts it found and the two hotkeys. No notification and no tray icon means it did not start: look in the log.

## Install it so it keeps running

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\publish.ps1" -Install
```

This builds a self-contained copy (about 50 MB, no .NET needed) into `dist\` and copies it to `%LOCALAPPDATA%\Programs\GibberishRewriter`. Start `GibberishRewriter.exe` from there and tick **Start with Windows** in the tray menu. It then starts at every sign-in.

Tick **Start with Windows** only on a copy in a folder that stays put. `dist\` and `bin\` are replaced on every build, which breaks the sign-in entry while the build runs. To update, exit the app from the tray, run the script again, and start it again.

The app reinstalls its keyboard hook by itself if Windows drops it. It does not restart itself after a crash; the next sign-in starts it again.

## Move it to another PC

1. Run `scripts\publish.ps1` (without `-Install`).
2. Copy the whole `dist\` folder (the exe **and** `shared\`) to the other PC, into a folder that stays put, for example `%LOCALAPPDATA%\Programs\GibberishRewriter`.
3. Run `GibberishRewriter.exe`. The exe is not signed, so SmartScreen may warn the first time: **More info → Run anyway**.
4. Tick **Start with Windows** in the tray menu.

Settings are per PC: each one creates its own config file on first start. Copy `config.json` across if you changed it.

## Config

`%APPDATA%\GibberishRewriter\config.json`, created from the defaults on first start and re-read within 2 seconds of each save. An invalid file keeps the last good settings and shows a notification.

```json
{
  "enabled": true,
  "hotkeys": {
    "fixTyped": "Shift+CapsLock+Tab",
    "fixSelection": "Shift+CapsLock+Backquote"
  },
  "switchLayoutAfterFix": true,
  "layouts": { "latin": "auto", "arabic": "auto" },
  "maxRunLength": 1000,
  "clipboardTimeoutMs": 400,
  "pasteRestoreDelayMs": 300,
  "releaseTimeoutMs": 3000
}
```

`"auto"` picks the one Latin and the one Arabic layout installed. With more than one of either, give 8-digit HKL codes such as `"04090409"` and `"04012C01"`; `GibberishRewriter.exe --dump-layouts out.json` shows what the app reads from Windows.

Logs: `%APPDATA%\GibberishRewriter\logs\csharp.log` or `python.log`, rolled over at 1 MB.

## Privacy

To fix what you typed, the app installs a low-level keyboard hook, so it sees every key you press. What it does with that:

- Typed characters stay in memory only, for the current run (at most `maxRunLength` keys). The run is cleared on every Enter, click, window change and on exit.
- Typed text is never written to disk or logged. The logs contain event kinds, counts, window class names and errors.
- The app makes no network connections.
- Selected text passes through the clipboard only during a selection fix. The app's own clipboard writes are marked to stay out of clipboard history and cloud sync.

## Limits

- Windows only. Linux would need a new platform layer (X11 or Wayland input capture and layout switching); the conversion logic would carry over.
- Windows of apps running as administrator can't be fixed unless Gibberish Rewriter also runs as administrator.
- Layouts with dead keys (such as US-International) aren't supported.
- CapsLock toggles when released instead of when pressed, because it is part of the hotkeys.

## Tests

```powershell
dotnet test csharp\GibberishRewriter.slnx
python\.venv\Scripts\python.exe -m pytest python
```

Or run `scripts\test-all.ps1`, which runs both suites and checks that both apps' `--dump-layouts` matches the snapshot in `shared\layouts\`. Add `-Integration` to either route to also run the tests that read the real layouts and clipboard.

What only a keyboard can confirm is in [the manual checklist](docs/manual-test-checklist.md): 17 cases, run once per app.

## Project layout

| Folder | Contents |
|---|---|
| `shared/` | What both apps read: key names, the default config, the key table snapshot, the word list, tray icons, and the test vectors both test suites run ([details](shared/README.md)) |
| `csharp/` | The C# app: `GibberishRewriter.Core` (pure logic), `GibberishRewriter.App` (Windows, WinForms tray) and their tests |
| `python/` | The Python app: `core/` (the same logic), `win/` (Windows through `ctypes`), `app/` (host, `pystray` tray) and tests |
| `scripts/` | Publishing, running every test, and rebuilding the word list and icons |

## License

[MIT](LICENSE). The English word list in `shared/wordlists/` comes from the English Speller Database; its own notice is in [ESDB-COPYRIGHT.txt](shared/wordlists/ESDB-COPYRIGHT.txt).
