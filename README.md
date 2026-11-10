# NSP Box for Android

Android port of NSP Box (Game tab). It packages an already-extracted, complete
`exefs` + `romfs` game folder into an unsigned plaintext NSP. It does not decrypt
anything and contains no games, keys or firmware. Use only files you are authorised to use.

The packaging engine (`engine.py`, `container_format.py`, `verify_format.py`, `artwork.py`,
`compatibility.py`) is copied unchanged from NSP Box 4.0.0 (MIT). `main.py` is a new
touch interface built with Kivy.

## Included / not included
Included: game snapshot scan, title/version editing, artwork (centered crop or fit),
NSP build with verification, optional package folder with `main.npdm`, cancel, automatic
numbering if the output name exists.
NUP tools tab: NSP to NUP, game folder to NUP, NUP to NSP, NUP to folder, and inspect/verify,
with Fast / Balanced / Smaller compression.
Not included: DLC tab, Windows emulator patching, and the interactive crop editor
(these are Windows-specific or need a larger rewrite).

NUP compression uses the `zstandard` library, which python-for-android does not ship, so this
project carries its own build recipe in `recipes/zstandard/`. If that part of the cloud build ever
fails, delete `,zstandard` from `requirements` and the `p4a.local_recipes` line in
`buildozer.spec`: the app then builds without NUP and says so on the NUP tab.

## Build the APK (no PC setup needed)
1. Create a new GitHub repository and upload everything in this folder
   (keep the `.github/workflows/android.yml` path).
2. Open the repo's **Actions** tab, choose **Build Android APK**, and press **Run workflow**.
3. When it finishes (the first build takes about 20-40 minutes), download the `NSPBox-apk` artifact.
4. Unzip it, copy the `.apk` to your phone and install it (allow "Install unknown apps").

Or build locally on Linux: `pip install buildozer cython` then `buildozer android debug`.

## First run
Android will send you to a settings page: switch on **All files access** for NSP Box, go back,
and tap Scan. This is needed to read big game folders and write multi-GiB files. Because of
that permission, this app is for sideloading, not the Play Store.

## Tips and limits
- Keep the screen on and the app in the foreground while building; Android may stop it otherwise.
- Free space needed: about the game size + 2%.
- Internal storage and exFAT SD cards work for big files. FAT32 cards cannot hold files over 4 GiB.
- Untested on real hardware so far: the engine and UI were tested on Linux only.
  If anything fails on your phone, send the error text shown under the progress bar.
