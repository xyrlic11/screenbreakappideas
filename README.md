# Blink

A Windows break reminder built on the 20-20-20 rule: every 20 minutes of
screen time, look at something 20 feet away for 20 seconds.

The difference from the dozens of apps that already do this is what
happens when you don't want to stop. Blink never blocks you — but every
way out costs something, and the cost is visible.

> ภาษาไทย: [README.th.md](README.th.md)

---

## Running it

```bash
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt
```

```bash
.venv\Scripts\python -m blink
```

| Flag | What it does |
|---|---|
| `--tray` | Start in the tray with no window. What autostart uses |
| `--debug` | Shrink every interval: a 20 minute cycle becomes 20 seconds |
| `--simulate 8h` | Replay a working day through the engine and print the timeline. No window, no Qt |

```
     time  event
------------------------------------------------------------
  0:18:01  <show_toast seconds_left=120>
  0:19:51  <show_edge seconds_left=10>
  0:20:01  <start_break kind='short', duration_sec=20.0>
  0:20:21  <end_break kind='short', outcome='completed'>
  2:00:01  <show_long_warning remaining_sec=60.0, snoozes_left=2>
  2:01:01  <start_break kind='long', duration_sec=300.0>
```

### Building the app

```bash
python tools/build.py
```

Regenerates `assets/blink.ico` from the same code that draws the tray
icon, then runs PyInstaller. Output is `dist/Blink/Blink.exe`, about
100 MB with Qt bundled. It is unsigned, so SmartScreen warns the first
time anyone else runs it — that needs a code signing certificate.

## The window

Four pages behind a Fluent navigation sidebar.

- **Home** — a ring counting down to the next break, and today's numbers
- **Stats** — compliance, streak, and seven days of breaks taken versus skipped
- **Settings** — every setting that matters, with a control instead of JSON
- **About** — version, privacy, and where the files live

It follows Windows: accent colour and light/dark come from the registry,
the window gets a Mica backdrop, a dark title bar and rounded corners
where the OS supports them, and falls back to a plain solid window where
it does not. Closing the window leaves the app in the tray; quitting is a
deliberate choice from the tray menu.

Latin text uses Segoe UI Variable, Thai falls back to Leelawadee UI, and
line height is raised to 150% because Thai stacks vowels above and tone
marks below the baseline.

## How it works

Six layers, one direction of travel. Every second, the sensors are read,
the state machine updates, the policy decides, and the UI does as it is
told.

```
Sensors  ──►  State machine  ──►  Policy  ──►  Commands  ──►  UI
idle time     is time accruing?   is a break     show_toast    overlay
lock state    for how long?       due yet?       start_break   toast
sleep gaps                                       lock_...      window
```

The UI counts nothing. Ask it how long until the next break and it does
not know — it only knows what it was last told to draw. That constraint is
what makes the interesting behaviour testable.

### The escalation ladder

Being yanked out of a sentence is the fastest way to get an app like this
uninstalled, so the interruption arrives in three stages:

| When | What | How much it interrupts |
|---|---|---|
| 2 min before | Toast in the corner | Barely — dismissible, never takes focus |
| 10 s before | Screen edge breathes | Peripheral vision only, click-through |
| On time | Fullscreen break | Total |

### Grace period

If the deadline lands while you are typing hard, the overlay waits for a
gap in your typing — up to two minutes, then it comes anyway. Someone
merely sitting and reading gets interrupted immediately; there is nothing
to protect.

### How hard it pushes

The one thing you actually get to choose about how it behaves. Both eye
breaks and long breaks have their own setting.

| Mode | What happens | Skipping it |
|---|---|---|
| **Take over the screen** | Fullscreen, covers everything, the default | Hold the skip button for 5 seconds |
| **Just remind me** | A card in the corner with the same countdown and activity. Never takes focus, never covers anything — you can keep typing straight through it | Click the card |
| **Lock the screen** | `LockWorkStation()`. Long breaks only | Unlock early — recorded as skipped |

Reminder mode is a real choice, not a lesser one: a completed break in
reminder mode still counts as taken. The history records which mode each
break used, so the two never get quietly conflated.

Picking reminder mode for the long break also drops the 60 second
countdown that precedes it. That warning exists so you can save your work
before the screen disappears — a card in the corner takes nothing away, so
warning you about it first would just be nagging.

### The break screen

Five activities, picked at random, never the same one twice running. A
black screen is not an eye break — people sit and stare straight at it, so
each of these asks the eyes to do something they cannot do while reading.

| Activity | Asks you to | Used on |
|---|---|---|
| Look far away | Change focal distance — a circle shrinks to nothing, with nothing to read | Both |
| Follow the dot | Track movement edge to edge, eyes only | Both |
| Blink slowly | Close fully, in time with an eyelid — screens halve your blink rate | Both |
| Breathe 4-7-8 | One 19 second cycle, so it only fits a long break | Long |
| Neck and shoulders | Follow a dial through four movements | Long |

The overlay covers `screen.geometry()`, not `availableGeometry()`, so the
taskbar goes too — otherwise a Discord badge blinking away in the corner
undoes the point of stopping. A real clock in the top corner makes up for
it. Escape does nothing.

### The way out costs something

| | Skip | Emergency |
|---|---|---|
| Where | Bottom right | Bottom left, nowhere near it |
| Cost | Hold for 5 seconds | None, one click |
| Recorded as | `skipped` | `emergency` |

The emergency button is deliberately free. An escape hatch people are
afraid to use is an escape hatch that gets worked around, and then the
whole cost system is theatre. It is recorded instead, and the stats page
shows it.

`Ctrl+Alt+Shift+Esc` does the same thing from the keyboard, for when the
mouse is not an option or an overlay ever wedges.

### The long break is the only thing that really locks the screen

| | Every | For | Enforced by |
|---|---|---|---|
| Eye break | 20 min | 20 s | Fullscreen overlay |
| Long break | 2 h | 5 min | `LockWorkStation()`, if you choose it |

Locking the screen for a 20 second break would cost more time in
retyping your password than the break itself, which is why it is not even
offered for eye breaks. For 5 minutes it is exactly the right amount of
friction — you have to physically get up.

Locking is **not the default**. Out of the box the long break is a
5 minute overlay, preceded by a 60 second countdown with two snoozes. That
countdown is a floating panel rather than a fullscreen one — it is telling
you to save your work, so it must not cover the thing you need to save.

### What stops the clock

- Under a minute without input still counts as screen time. Reading a
  page without touching the mouse is exactly the case this app is for.
- Over a minute, the counter freezes.
- Over five minutes, it resets: your eyes genuinely rested.
- Locked screen: frozen immediately, reset only once the lock has lasted
  as long as any other absence would need to. A one second Win+L is not a
  rest, and the same signal fires for the UAC secure desktop.
- Suspend and hibernate: detected by watching for a hole in the tick
  stream rather than subscribing to power events. Cheaper, and it also
  covers clock changes, a stopped process and a debugger breakpoint.

## Privacy

- **No keyboard hook.** Idle time comes from `GetLastInputInfo`, which
  reports *when* input last happened and never *what* was pressed. No
  antivirus flags it, and it needs no elevation.
- **No network.** There is no code in this repo that opens a socket.
- **No admin rights.** Autostart is a value under the user's own `Run` key.
- **Nothing identifying is stored.** The history table records when a break
  was due, what you did about it, and how long you had been at the screen.
  No window titles, no process names.

## Files

| | |
|---|---|
| `%APPDATA%\Blink\config.json` | Settings. Missing keys are refilled, out-of-range values clamped, a corrupt file falls back to defaults rather than stopping the app |
| `%APPDATA%\Blink\blink.sqlite3` | Break history, including which mode enforced each break |
| `%APPDATA%\Blink\sounds\` | Two chimes, synthesised on first run |

Days roll over at 04:00, not midnight — working until 2am belongs to the
day you started.

## Tests

```bash
.venv\Scripts\python -m pytest
```

`blink/core/` imports nothing but the standard library — no Qt, no Win32,
and it never reads the clock. Time and sensor values are handed in as
parameters. Eight hours of simulated screen time replays in **0.27
seconds**, so every rule below is covered by a test that runs instantly:

- the ladder fires in order, at the right second
- walking away freezes the counter; five minutes away resets it
- suspend does not come back as hours of screen time
- pause freezes without wiping progress (otherwise it is a free reset)
- grace defers while typing, and gives up at the ceiling
- a long break subsumes the short one instead of stacking two overlays
- cancelling a long break does not re-fire it one second later
- work past midnight lands on the right logical day
- a day with nothing due is 100% compliance, not 0%
- a one second Win+L, and a UAC prompt, cost you nothing
- unlocking three seconds into a locked long break records `skipped`, not
  `completed` — the cycle still resets, but the statistics stay honest
- walking away announces one reset, not one per second
- a skip ends the streak; an idle day stops it without extending it
- short breaks never draw an activity too slow to finish
- both enforcement modes emit byte-identical command streams, so nothing
  downstream can start depending on which one is on screen
- an unknown mode in config.json falls back to the field's default, never
  to the harshest option — a typo must not be what turns locking on
- a database written before the mode column still opens, keeping its rows
- both locale files define the same keys **and the same `{placeholders}`**

That last one matters more than it looks: `t()` swallows a missing
placeholder so the app cannot crash, which means a translator dropping a
`{slot}` would otherwise reach the screen as raw `{count}`.

## Layout

```
blink/
├── core/         stdlib only, no Qt, no Win32, no clock
│   ├── models.py     State, Phase, Command, Config
│   ├── state.py      what counts as screen time
│   ├── policy.py     20-20-20, escalation, grace, long break
│   └── ticker.py     read → update → decide
├── sensors/      three ctypes calls, nothing more
├── storage/      config.json and the history database
└── ui/           Qt. Draws things, reports clicks, counts nothing
    ├── theme.py      tokens, system accent, Mica
    ├── window.py     the four-page main window
    ├── pages/        home, stats, settings, about
    ├── activities/   what you do during a break
    ├── overlay.py    the fullscreen break
    └── break_popup.py  the corner reminder
tools/            icon generation and the PyInstaller build
```

## Known limitations

- **Fullscreen exclusive games**: Windows will not let any overlay draw on
  top of them. Nothing to be done about it from user space.
- **Unsigned builds**: SmartScreen warns until the binary is code-signed.
- **Multi-monitor**: overlays are built per screen on every break, and the
  buttons appear on whichever screen the mouse is on. Monitors plugged in
  *during* a break are not picked up until the next one.
- **Mica**: needs Windows 11. Older versions get a solid window.

## Not built yet

Eye debt (skip now, next break is longer), whitelist and do-not-disturb
for calls and presentations, audio and active-window detection, a longer
statistics history than seven days, and an installer.

The eye-debt seam is already in place: break length comes from
`PolicyEngine._next_break_sec()`, and that is the only line that needs to
change.
