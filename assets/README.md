# Wiiz app icon

`wiiz-icon.png` is the user-approved cartridge / Wiiz design generated with
OpenAI's built-in image generation tool on 2026-10-21 for this project.
It contains no ROM artwork or third-party emulator artwork.

The source is retained here rather than in ignored build output.
Run `powershell -File tools/generate-icons.ps1` from the repository root to
regenerate `assets/wiiz.ico` (16, 24, 32, 48, 64, 128, 256 pixels) and Android
launcher PNGs (mdpi through xxxhdpi) using Windows System.Drawing.
No additional runtime imaging dependency is needed.

Windows embeds resource 101 in the executable. The window uses SDL's existing
native window handle property and Win32 LoadImage / WM_SETICON for large and
small icons. Android uses its standard manifest mipmap icon support.
These changes concern UI assets only; no emulator core or Mapper code changed.
