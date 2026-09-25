# Manual test checklist

Everything here needs a real keyboard, so no test suite covers it. Run the whole list for **each app**
separately — the C# one and the Python one — and never both at once: they share one instance lock, and the second
one to start will refuse to.

Before you start, check that both **English (US)** and **Arabic (101)** are in your language bar, and that Caps Lock
is off. `%APPDATA%\GibberishRewriter\logs\csharp.log` and `python.log` are worth keeping open in a second window.

Starting each app:

| App | Command |
|---|---|
| C# | `csharp\src\GibberishRewriter.App\bin\Debug\net10.0-windows\GibberishRewriter.exe` |
| Python | `python -m gibberish_rewriter`, from `python\` with `.venv\Scripts\python.exe` |

The default hotkeys are `Shift+CapsLock+Tab` (fix what you just typed) and ``Shift+CapsLock+` `` (fix the selection).
Pressing the same hotkey again undoes the fix.

## Where to run each case

Each case says which apps to use. "Editors" means: Notepad; Chrome or Edge, in both a plain text box and a rich one
such as WhatsApp Web; the VS Code editor; the Claude Code chat box in VS Code. "Consoles" means: the VS Code terminal
and Windows Terminal with PowerShell.

## The cases

- [ ] **1. Start.** A tray icon appears, and a notification names the two layouts and the two hotkeys. The log shows
  `Starting`, `Config loaded` and `Layout pair 04090409 and 04012C01`. If no notification appears, the app did not
  start — read the log before going on.
- [ ] **2. English typed on the Arabic layout.** In each editor, with Arabic on, type `hello` (it comes out `اثممخ`)
  and press `Shift+CapsLock+Tab`. The text becomes `hello` and the layout switches to English. Press again: the text
  is `اثممخ` and the layout is Arabic again.
- [ ] **3. Arabic typed on the English layout.** With English on, type `lvpfh` and fix it: `مرحبا`.
- [ ] **4. Capitals, punctuation and diacritics.** Type a run with capitals and punctuation (`Hello, World!`) and fix
  it; then one with Arabic diacritics from Shift + Q, W, E, R, A, S, X or `` ` ``. Every character is removed one at a
  time and the fixed text is right.
- [ ] **5. Selection: one line.** Type `lvpfh` on the English layout, select it, press ``Shift+CapsLock+` ``: it
  becomes `مرحبا`. Press again in the same window: the change is undone.
- [ ] **6. Selection: several lines.** Same, with three lines selected at once. The line breaks survive.
- [ ] **7. The clipboard survives a selection fix.** Copy some text, do a selection fix, then paste: your text is
  still there. Repeat with an image on the clipboard.
- [ ] **8. Keys that are not chords still work.** A CapsLock tap toggles Caps Lock; `` ` `` alone types `ذ` on the
  Arabic layout; `Shift+Tab` still moves focus backwards in a dialog.
- [ ] **9. Consoles.** In each console, type `lvpfh` at the prompt on the English layout, select it with the mouse and
  press ``Shift+CapsLock+` ``. `مرحبا` is pasted at the cursor and the original text stays — a console pastes instead
  of replacing the selection. In the VS Code terminal with nothing selected, expect Ctrl+C to cancel the
  running command: that is documented, not a bug.
- [ ] **10. An administrator window.** Start PowerShell as administrator, type something and press the typed-fix
  hotkey. Either the chord acts as ordinary keys, or a notification says the app cannot fix text in an administrator
  window. Nothing is typed into the window.
- [ ] **11. A second copy.** Start the same app again: a message box says it is already running and the second copy
  exits. Then start the *other* app while this one runs: the same message.
- [ ] **12. The tray menu.** **Enabled** greys the icon and keys pass through untouched; clicking it again restores.
  **Start with Windows** toggles its check mark and the `GibberishRewriter` value under
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. **Open config file** opens the file.
- [ ] **13. A bad config is survivable.** Save the config with `"maxRunLength": 1`: within 2 seconds a notification
  shows `number.range`, and the last good settings stay in use. Put `1000` back.
- [ ] **14. A layout that is not installed.** Set `"layouts": { "latin": "0000FFFF", "arabic": "auto" }` and save.
  Within 2 seconds a notification says `0000FFFF` is not installed, the icon greys, and the log shows
  `No usable layout pair; disabled`. Put `"auto"` back: the icon turns blue and a typed fix works again.
- [ ] **15. Caps Lock after the lock screen.** With Caps Lock off, press `Win+L`, turn Caps Lock **on** at the sign-in
  screen, and unlock. The log shows `Session unlocked`. With Arabic on, type `hello` and fix it: the text is `HELLO`,
  because the app took the Caps Lock state from Windows. Turn Caps Lock off again.
- [ ] **16. A missing file.** Copy the published folder somewhere, delete `shared\icons` from the copy, and start it.
  A message box names the folder and the missing file, and the app exits. It must never exit silently.
- [ ] **17. Exit.** The icon disappears, the log shows `Exited`, and Caps Lock behaves normally again.

## Recording a run

| | C# | Python |
|---|---|---|
| Date | | |
| Windows version | | |
| Cases that failed | | |
| Notes | | |

A case that fails is worth more than a case that passes: write down the app, the window you were in, what you typed,
what you expected and what happened, and attach the last lines of the log.
