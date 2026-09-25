# shared

The single source of truth for both Gibberish Rewriter implementations (C# and Python).
Both test suites read these files directly:

| File | Contents |
|---|---|
| `keys.json` | Key names and virtual-key codes, which names are hold keys, and the key-table keys in order (`tableKeys`) |
| `config.default.json` | The default config |
| `layouts/us-arabic101.json` | Key table snapshot for English (US) and Arabic (101) |
| `wordlists/english.txt`, `wordlists/ESDB-COPYRIGHT.txt` | English word list, used to choose between one-key and two-key lam-alef, and its license |
| `vectors/convert.json` | Selected text and its conversion |
| `vectors/chords.json` | Key events and the pass/swallow decisions, CapsLock replays and fired chords |
| `vectors/typing.json` | Events and the platform calls for typed fixes and undo |
| `vectors/selection.json` | Scripted clipboard and foreground behavior and the platform calls for selection fixes |
| `vectors/config.json` | Config text and the parsed config or error code |
| `icons/tray.ico`, `icons/tray-disabled.ico` | Tray icons |

Never edit a vector to make one implementation pass. Fix the implementation instead.
