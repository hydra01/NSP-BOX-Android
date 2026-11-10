# ZIP to NUP (Android)

A simple converter: choose a ZIP file, the app extracts it and converts it to a `.nup` file.

The ZIP can contain either an unencrypted `.nsp` file, or a game folder with `exefs` + `romfs`
(also inside sub-folders). No keys are used and nothing is decrypted. Encrypted/retail NSPs are refused.

The conversion engine (`engine.py`, `container_format.py`, `verify_format.py`, `artwork.py`,
`compatibility.py`, `nup_format.py`, `nup_tools.py`, `dlc.py`) is copied unchanged from NSP Box 4.0.0 (MIT).
`zip_convert.py` (safe ZIP extraction + detection) and `main.py` (the screen) are new.

## Use
1. Install the APK and allow **All files access** when asked.
2. Tap **Choose ZIP file**, pick your ZIP.
3. Tap **Convert to NUP**. The `.nup` is saved in `/storage/emulated/0/NSPBox` (change it at the bottom).

Free space needed: about 2x the size of the extracted files. Keep the app open and the screen on
until it says Done. The file name is taken from the ZIP and never overwrites an existing file.

## Build the APK
Upload everything in this folder to a GitHub repo, open **Actions > Build Android APK > Run workflow**,
and download the `NSPBox-apk` artifact when it finishes (30-60 minutes the first time).

NUP compression uses the `zstandard` library, which python-for-android does not ship, so this project
carries its own build recipe in `recipes/zstandard/`.

`extras/main_full.py` is the earlier two-tab version (Game folder to NSP + NUP tools); it is not part of the APK.
