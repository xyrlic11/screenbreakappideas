# Fonts

Blink picks the first family it finds, in this order:

1. **Sarabun** — only if a `.ttf` is dropped into this folder
2. **Leelawadee UI** — ships with Windows 8 and later, renders Thai correctly
3. Segoe UI / Tahoma

Nothing needs to be installed for the app to run and render Thai properly:
Leelawadee UI covers it. Every `.ttf` placed here is registered at startup
via `QFontDatabase.addApplicationFont`.

Drop `Sarabun-Regular.ttf` (and any other weights) here before packaging if
you want the app to look identical on machines whose Thai font support is
older or has been stripped.

Line height is raised to 150% in `blink/ui/theme.py` regardless of family,
because Thai stacks vowels above and tone marks below the baseline and the
default Qt leading makes adjacent rows collide.
