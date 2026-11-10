"""NSP Box for Android: touch front end for the unchanged NSP Box packaging engine.

Packages an already-extracted ExeFS/RomFS game snapshot into an unsigned plaintext NSP.
It does not decrypt anything and includes no games, keys or firmware.
"""
import os
import threading
import time
import traceback
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.utils import platform

import engine
from artwork import ArtworkSelection
from helpers import (IMAGE_EXTS, NUP_COMPRESSION, NUP_OPS, default_output_dir,
                     default_version, format_nup_result, human_size, list_directory,
                     nup_output_path, safe_filename, unique_output)

KV = r'''
<Field@TextInput>:
    multiline: False
    write_tab: False
    size_hint_y: None
    height: dp(46)
    font_size: '15sp'

<Btn@Button>:
    size_hint_y: None
    height: dp(48)
    font_size: '15sp'

<Cap@Label>:
    size_hint_y: None
    height: self.texture_size[1] + dp(6)
    text_size: self.width, None
    halign: 'left'
    valign: 'middle'
    font_size: '13sp'
    color: .72, .76, .86, 1

<Head@Label>:
    size_hint_y: None
    height: dp(30)
    text_size: self.width, None
    halign: 'left'
    valign: 'middle'
    bold: True
    font_size: '16sp'

<Check@BoxLayout>:
    size_hint_y: None
    height: dp(44)
    text: ''
    active: cb.active
    CheckBox:
        id: cb
        size_hint_x: None
        width: dp(44)
        active: True
    Label:
        text: root.text
        text_size: self.width, None
        halign: 'left'
        valign: 'middle'
        font_size: '14sp'

TabbedPanel:
    do_default_tab: False
    tab_pos: 'top_mid'
    tab_width: self.width / 2
    tab_height: dp(46)
    canvas.before:
        Color:
            rgba: .07, .08, .13, 1
        Rectangle:
            pos: self.pos
            size: self.size
    TabbedPanelItem:
        text: 'Game to NSP'

        ScrollView:
            do_scroll_x: False
            bar_width: dp(4)
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(12)
                spacing: dp(8)

                Label:
                    text: 'NSP Box'
                    font_size: '26sp'
                    bold: True
                    size_hint_y: None
                    height: dp(46)
                Cap:
                    text: 'Package an already-extracted Switch 2 game folder (exefs + romfs) into an NSP. Use only files you are authorised to use.'

                Head:
                    text: '1. Game folder'
                Field:
                    id: game_path
                    hint_text: '/storage/emulated/0/MyGame'
                BoxLayout:
                    size_hint_y: None
                    height: dp(48)
                    spacing: dp(8)
                    Btn:
                        text: 'Browse'
                        on_release: app.browse_game()
                    Btn:
                        text: 'Scan'
                        on_release: app.scan(game_path.text)
                Spinner:
                    id: snap
                    text: 'Scan a folder first'
                    values: []
                    size_hint_y: None
                    height: dp(48)
                    on_text: app.on_snapshot(self.text)
                Cap:
                    id: tid
                    text: ''

                Head:
                    text: '2. Details'
                Cap:
                    text: 'Title'
                Field:
                    id: title_in
                Cap:
                    text: 'Display version (max 15 bytes)'
                Field:
                    id: version_in
                Cap:
                    id: art_label
                    text: 'Artwork: none'
                BoxLayout:
                    size_hint_y: None
                    height: dp(48)
                    spacing: dp(8)
                    Btn:
                        text: 'Choose artwork'
                        on_release: app.browse_art()
                    Btn:
                        text: 'Clear'
                        on_release: app.clear_art()
                Check:
                    id: fit_cb
                    text: 'Fit whole image (otherwise centered square crop)'
                    on_kv_post: self.ids.cb.active = False

                Head:
                    text: '3. Output'
                Field:
                    id: out_dir
                Btn:
                    text: 'Browse output folder'
                    on_release: app.browse_out()
                Check:
                    id: verify_cb
                    text: 'Verify after building (recommended)'
                Check:
                    id: folder_cb
                    text: 'Create package folder (adds main.npdm companion)'
                    on_kv_post: self.ids.cb.active = False

                Btn:
                    id: build_btn
                    text: 'Build NSP'
                    height: dp(54)
                    on_release: app.start_build()
                Btn:
                    id: cancel_btn
                    text: 'Cancel'
                    disabled: True
                    on_release: app.cancel_build()
                ProgressBar:
                    id: progress
                    max: 100
                    value: 0
                    size_hint_y: None
                    height: dp(14)
                Cap:
                    id: status
                    text: 'Ready.'
                Cap:
                    id: log
                    text: ''
    TabbedPanelItem:
        text: 'NUP tools'
        ScrollView:
            do_scroll_x: False
            bar_width: dp(4)
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(12)
                spacing: dp(8)

                Label:
                    text: 'NUP tools'
                    font_size: '26sp'
                    bold: True
                    size_hint_y: None
                    height: dp(46)
                Cap:
                    text: 'Convert between NSP and NUP (NSP Box archive format, experimental). Only unencrypted NSPs made by NSP Box are supported; no keys are used.'

                Head:
                    text: '1. What do you want to do?'
                Spinner:
                    id: nup_op
                    text: 'NSP to NUP'
                    values: app.nup_op_labels
                    size_hint_y: None
                    height: dp(48)
                    on_text: app.on_nup_op(self.text)

                Head:
                    text: '2. Input'
                Field:
                    id: nup_in
                    hint_text: '/storage/emulated/0/Game.nsp'
                Btn:
                    id: nup_in_btn
                    text: 'Browse for the .nsp file'
                    on_release: app.browse_nup_in()

                Head:
                    text: '3. Output folder'
                Field:
                    id: nup_out
                Btn:
                    text: 'Browse output folder'
                    on_release: app.browse_nup_out()
                Cap:
                    id: nup_name_hint
                    text: 'The file name is chosen for you and never overwrites an existing file.'

                Head:
                    text: '4. Options'
                Cap:
                    text: 'Compression (used when making a NUP)'
                Spinner:
                    id: nup_preset
                    text: 'Balanced'
                    values: app.nup_presets
                    size_hint_y: None
                    height: dp(48)
                Check:
                    id: nup_raw
                    text: 'Store large files uncompressed (faster)'
                Check:
                    id: nup_verify
                    text: 'Verify (recommended)'
                Check:
                    id: nup_latest
                    text: 'Keep only the latest game snapshot (game folder only)'
                Cap:
                    text: 'Package number (optional, NUP to NSP / folder; leave empty for everything)'
                Field:
                    id: nup_pkg
                    input_filter: 'int'

                Btn:
                    id: nup_run_btn
                    text: 'Start'
                    height: dp(54)
                    on_release: app.start_nup()
                Btn:
                    id: nup_cancel_btn
                    text: 'Cancel'
                    disabled: True
                    on_release: app.cancel_build()
                ProgressBar:
                    id: nup_progress
                    max: 100
                    value: 0
                    size_hint_y: None
                    height: dp(14)
                Cap:
                    id: nup_status
                    text: 'Ready.'
                Cap:
                    id: nup_log
                    text: ''

'''


class Browser(Popup):
    """Simple tap-to-navigate folder/file picker (reliable on touch screens)."""

    def __init__(self, title, start, mode, callback, exts=IMAGE_EXTS, **kw):
        super().__init__(title=title, size_hint=(.97, .94), auto_dismiss=False, **kw)
        self.mode = mode              # 'dir' or 'file'
        self.exts = exts
        self.callback = callback
        self.path = self._valid(start)
        self.roots_view = False

        root = BoxLayout(orientation='vertical', spacing=dp(6), padding=dp(6))
        self.path_label = Label(size_hint_y=None, height=dp(40), shorten=True,
                                shorten_from='left', halign='left', valign='middle')
        self.path_label.bind(size=lambda w, s: setattr(w, 'text_size', s))
        root.add_widget(self.path_label)

        self.grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(3))
        self.grid.bind(minimum_height=self.grid.setter('height'))
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.grid)
        root.add_widget(scroll)

        row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(6))
        for text, action in (('Up', self.go_up), ('Storage', self.show_roots)):
            row.add_widget(Button(text=text, on_release=lambda *_, a=action: a()))
        if mode == 'dir':
            row.add_widget(Button(text='Use this folder', on_release=lambda *_: self.choose(self.path)))
        row.add_widget(Button(text='Cancel', on_release=lambda *_: self.dismiss()))
        root.add_widget(row)
        self.content = root
        self.refresh()

    @staticmethod
    def _valid(start):
        p = Path(start) if start else Path('/storage/emulated/0')
        while not p.is_dir() and p != p.parent:
            p = p.parent
        return p if p.is_dir() else Path('/')

    def _entry(self, text, callback):
        b = Button(text=text, size_hint_y=None, height=dp(48), halign='left',
                   valign='middle', background_color=(.2, .24, .36, 1), shorten=True,
                   shorten_from='right', on_release=lambda *_: callback())
        b.bind(size=lambda w, s: setattr(w, 'text_size', (s[0] - dp(16), s[1])))
        self.grid.add_widget(b)

    def refresh(self):
        self.grid.clear_widgets()
        self.roots_view = False
        self.path_label.text = str(self.path)
        folders, files = list_directory(self.path, want_files=self.mode == 'file', exts=self.exts)
        if folders is None:
            self._entry('Cannot open this folder (permission?)', lambda: None)
            return
        for name in folders[:1500]:
            self._entry('[folder]  ' + name, lambda n=name: self.enter(n))
        for name in files[:1500]:
            self._entry('[file]  ' + name, lambda n=name: self.choose(self.path / n))
        if not folders and not files:
            self._entry('(empty)', lambda: None)

    def show_roots(self):
        self.grid.clear_widgets()
        self.roots_view = True
        self.path_label.text = 'Storage locations'
        roots = []
        if os.path.isdir('/storage/emulated/0'):
            roots.append(('Internal storage', '/storage/emulated/0'))
        try:
            for name in sorted(os.listdir('/storage')):
                full = f'/storage/{name}'
                if name not in ('emulated', 'self') and os.path.isdir(full):
                    roots.append((f'SD card / USB  ({name})', full))
        except OSError:
            pass
        if not roots:
            roots.append(('Home', os.path.expanduser('~')))
        for label, full in roots:
            self._entry(label, lambda f=full: self.jump(f))

    def jump(self, full):
        self.path = Path(full)
        self.refresh()

    def enter(self, name):
        self.path = self.path / name
        self.refresh()

    def go_up(self):
        if self.roots_view:
            return
        if self.path.parent != self.path:
            self.path = self.path.parent
            self.refresh()

    def choose(self, path):
        self.dismiss()
        self.callback(str(path))


class NSPBoxApp(App):
    title = 'NSP Box'
    snapshots = {}
    art_path = None
    busy = False
    popup = None
    cancel_event = threading.Event()
    nup_op_labels = list(NUP_OPS)
    nup_presets = list(NUP_COMPRESSION)

    def build(self):
        Window.bind(on_keyboard=self._on_key)
        return Builder.load_string(KV)

    # ----- lifecycle / permissions -------------------------------------------------
    def on_start(self):
        ids = self.root.ids
        ids.out_dir.text = default_output_dir()
        ids.nup_out.text = default_output_dir()
        ids.nup_latest.ids.cb.active = True
        self.snapshots = {}
        self.art_path = None
        self.cancel_event = threading.Event()
        self.busy = False
        self.popup = None
        self.ensure_storage_access()
        self.keep_awake()

    def _on_key(self, window, key, *args):
        if key == 27 and self.popup and self.popup._window:   # Android back button
            self.popup.dismiss()
            return True
        return False

    def ensure_storage_access(self):
        """Request 'All files access' so the app can read game folders and write big NSPs."""
        if platform != 'android':
            return True
        try:
            from jnius import autoclass
            Environment = autoclass('android.os.Environment')
            if Environment.isExternalStorageManager():
                return True
            Intent = autoclass('android.content.Intent')
            Settings = autoclass('android.provider.Settings')
            Uri = autoclass('android.net.Uri')
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
            intent.setData(Uri.parse('package:' + activity.getPackageName()))
            activity.startActivity(intent)
            self.say('Allow "All files access" for NSP Box, then come back and tap Scan.')
            return False
        except Exception:
            try:  # Android 10 and older
                from android.permissions import Permission, request_permissions
                request_permissions([Permission.READ_EXTERNAL_STORAGE,
                                     Permission.WRITE_EXTERNAL_STORAGE])
            except Exception:
                pass
            return True

    def keep_awake(self):
        """Stop the screen from sleeping during long builds."""
        if platform != 'android':
            return
        try:
            from android.runnable import run_on_ui_thread
            from jnius import autoclass

            @run_on_ui_thread
            def _flag():
                activity = autoclass('org.kivy.android.PythonActivity').mActivity
                activity.getWindow().addFlags(128)   # FLAG_KEEP_SCREEN_ON
            _flag()
        except Exception:
            pass

    # ----- small UI helpers ---------------------------------------------------------
    def say(self, text, log=None):
        ids = self.root.ids
        ids.status.text = text
        if log is not None:
            ids.log.text = log

    def _open_browser(self, title, start, mode, callback, exts=IMAGE_EXTS):
        if not self.ensure_storage_access():
            return
        self.popup = Browser(title, start, mode, callback, exts=exts)
        self.popup.open()

    # ----- folder / artwork pickers -------------------------------------------------
    def browse_game(self):
        self._open_browser('Select the game folder', self.root.ids.game_path.text, 'dir',
                           self._game_chosen)

    def _game_chosen(self, path):
        self.root.ids.game_path.text = path
        self.scan(path)

    def browse_art(self):
        start = str(Path(self.art_path).parent) if self.art_path else self.root.ids.game_path.text
        self._open_browser('Choose artwork image', start, 'file', self._art_chosen)

    def _art_chosen(self, path):
        self.art_path = path
        self.root.ids.art_label.text = 'Artwork: ' + Path(path).name

    def clear_art(self):
        self.art_path = None
        self.root.ids.art_label.text = 'Artwork: none'

    def browse_out(self):
        self._open_browser('Select the output folder', self.root.ids.out_dir.text, 'dir',
                           lambda p: setattr(self.root.ids.out_dir, 'text', p))

    # ----- scanning -------------------------------------------------------------------
    def scan(self, folder):
        if self.busy:
            return
        folder = folder.strip()
        if not folder:
            self.say('Choose a game folder first.')
            return
        if not self.ensure_storage_access():
            return
        self.say('Scanning for exefs + romfs snapshots...', '')
        threading.Thread(target=self._scan_worker, args=(folder,), daemon=True).start()

    def _scan_worker(self, folder):
        try:
            found, skipped = engine.find_snapshots(folder)
        except Exception as e:  # noqa: BLE001 - show any scan error to the user
            Clock.schedule_once(lambda dt, m=str(e): self.say('Scan failed.', m))
            return
        Clock.schedule_once(lambda dt: self._scan_done(found, skipped))

    def _scan_done(self, found, skipped):
        ids = self.root.ids
        self.snapshots = {}
        labels = []
        for s in found:
            label = f'{s.label}  (v{s.version})'
            while label in self.snapshots:
                label += '*'
            self.snapshots[label] = s
            labels.append(label)
        ids.snap.values = labels
        note = f'{len(skipped)} DLC folder(s) ignored (DLC is not supported in this Android build).' if skipped else ''
        ids.snap.text = ''          # force on_text to fire even if the label repeats
        ids.snap.text = labels[0]
        self.say(f'Found {len(found)} complete snapshot(s).', note)

    def on_snapshot(self, text):
        s = self.snapshots.get(text)
        if not s:
            return
        ids = self.root.ids
        ids.title_in.text = s.title
        ids.version_in.text = default_version(s)
        ids.tid.text = f'Title ID: {s.title_id:016X}'

    # ----- building ---------------------------------------------------------------------
    def start_build(self):
        if self.busy:
            return
        ids = self.root.ids
        snapshot = self.snapshots.get(ids.snap.text)
        if not snapshot:
            self.say('Scan a game folder and select a snapshot first.')
            return
        if not self.ensure_storage_access():
            return
        title = ids.title_in.text.strip()
        version = ids.version_in.text.strip()
        out_dir = ids.out_dir.text.strip()
        if not title or not out_dir:
            self.say('Enter a title and an output folder.')
            return
        output = unique_output(out_dir, safe_filename(title), ids.folder_cb.active)
        art = None
        if self.art_path:
            art = (ArtworkSelection(Path(self.art_path), fit=True) if ids.fit_cb.active
                   else self.art_path)
        options = dict(snapshot=snapshot, output=output, title=title, display_version=version,
                       artwork_path=art, verify=ids.verify_cb.active,
                       package_folder=ids.folder_cb.active)
        self.busy = True
        self.cancel_event.clear()
        ids.build_btn.disabled = True
        ids.nup_run_btn.disabled = True
        ids.cancel_btn.disabled = False
        ids.progress.value = 0
        self.say('Starting...', '')
        threading.Thread(target=self._build_worker, args=(options,), daemon=True).start()

    def _build_worker(self, options):
        started = time.time()

        def notify(stage, percent):
            Clock.schedule_once(lambda dt: self._progress(stage, percent))

        try:
            report = engine.build(notify=notify, cancel=self.cancel_event, **options)
            elapsed = time.time() - started
            lines = [
                f"Saved: {report['output']}",
                f"Size: {human_size(report['size'])}",
                f"Title ID: {report['title_id']}",
                f"Verified: {'yes' if report['verified'] else 'skipped'}",
                f"SHA-256: {report['sha256']}",
                f'Time: {elapsed / 60:.1f} min',
            ]
            Clock.schedule_once(lambda dt: self._finished('Complete.', '\n'.join(lines)))
        except InterruptedError:
            self._remove_empty_folder(options)
            Clock.schedule_once(lambda dt: self._finished('Cancelled.', 'Unfinished output was removed.'))
        except Exception as e:  # noqa: BLE001
            self._remove_empty_folder(options)
            detail = str(e) or e.__class__.__name__
            print(traceback.format_exc())
            Clock.schedule_once(lambda dt: self._finished('Build failed.', detail))

    @staticmethod
    def _remove_empty_folder(options):
        """The engine creates the package folder up front; drop it if the build left it empty."""
        if options['package_folder']:
            try:
                options['output'].parent.joinpath(options['output'].stem).rmdir()
            except OSError:
                pass

    def _progress(self, stage, percent):
        self.root.ids.progress.value = percent
        self.root.ids.status.text = f'{stage}  {percent:.0f}%'

    def _finished(self, status, log):
        ids = self.root.ids
        self.busy = False
        ids.build_btn.disabled = False
        ids.nup_run_btn.disabled = False
        ids.cancel_btn.disabled = True
        if status == 'Complete.':
            ids.progress.value = 100
        self.say(status, log)

    # ----- NUP tab ----------------------------------------------------------------------
    def on_nup_op(self, label):
        spec = NUP_OPS.get(label)
        if not spec:
            return
        key, kind, exts, out_ext = spec
        ids = self.root.ids
        if kind == 'dir':
            ids.nup_in_btn.text = 'Browse for the game folder'
            ids.nup_in.hint_text = '/storage/emulated/0/MyGame'
        else:
            ids.nup_in_btn.text = 'Browse for the %s file' % exts[0]
            ids.nup_in.hint_text = '/storage/emulated/0/File' + exts[0]
        ids.nup_name_hint.text = ('Nothing is written; the NUP is only read.' if out_ext is None else
                                  'The name is chosen for you and never overwrites an existing %s.'
                                  % ('file' if out_ext else 'folder'))

    def browse_nup_in(self):
        key, kind, exts, out_ext = NUP_OPS[self.root.ids.nup_op.text]
        start = self.root.ids.nup_in.text or self.root.ids.nup_out.text
        if kind == 'dir':
            self._open_browser('Select the game folder', start, 'dir',
                               lambda p: setattr(self.root.ids.nup_in, 'text', p))
        else:
            self._open_browser('Select the %s file' % exts[0], str(Path(start).parent) if start else '',
                               'file', lambda p: setattr(self.root.ids.nup_in, 'text', p), exts=exts)

    def browse_nup_out(self):
        self._open_browser('Select the output folder', self.root.ids.nup_out.text, 'dir',
                           lambda p: setattr(self.root.ids.nup_out, 'text', p))

    def nup_say(self, text, log=None):
        ids = self.root.ids
        ids.nup_status.text = text
        if log is not None:
            ids.nup_log.text = log

    def start_nup(self):
        if self.busy:
            return
        ids = self.root.ids
        label = ids.nup_op.text
        key, kind, exts, out_ext = NUP_OPS[label]
        try:
            import zstandard  # noqa: F401 - NUP archives are zstd-compressed
        except ImportError:
            self.nup_say('NUP tools are unavailable.',
                         'This build of the app does not include the zstandard library.')
            return
        if not self.ensure_storage_access():
            return
        source = ids.nup_in.text.strip()
        out_dir = ids.nup_out.text.strip()
        if not source or not os.path.exists(source):
            self.nup_say('Choose an existing input first.')
            return
        if out_ext is not None and not out_dir:
            self.nup_say('Choose an output folder.')
            return
        pkg = ids.nup_pkg.text.strip()
        try:
            output = nup_output_path(label, source, out_dir) if out_ext is not None else None
        except ValueError as e:
            self.nup_say(str(e))
            return
        options = dict(key=key, label=label, source=source, output=output,
                       preset=ids.nup_preset.text, large_raw=ids.nup_raw.active,
                       verify=ids.nup_verify.active, latest=ids.nup_latest.active,
                       package=int(pkg) if pkg else None)
        self.busy = True
        self.cancel_event.clear()
        ids.nup_run_btn.disabled = True
        ids.nup_cancel_btn.disabled = False
        ids.build_btn.disabled = True
        ids.nup_progress.value = 0
        self.nup_say('Starting...', '')
        threading.Thread(target=self._nup_worker, args=(options,), daemon=True).start()

    def _nup_run(self, o, output, notify):
        import nup_tools as tools
        from nup_format import PRESETS
        level, common = PRESETS[o['preset']], dict(notify=notify, cancel=self.cancel_event)
        key, src = o['key'], Path(o['source'])
        if key == 'nsp_to_nup':
            return tools.nsp_to_nup(src, output, level=level, large_raw=o['large_raw'],
                                    verify=o['verify'], **common)
        if key == 'pack':
            return tools.pack_folder(src, output, latest_snapshot=o['latest'], level=level,
                                     large_raw=o['large_raw'], verify=o['verify'], **common)
        if key == 'nup_to_nsp':
            return tools.nup_to_nsp(src, output, selection=o['package'], verify=o['verify'], **common)
        if key == 'extract':
            return tools.extract(src, output, selection=None if o['package'] is None else [o['package']],
                                 **common)
        return tools.inspect(src, verify=o['verify'], **common)

    def _nup_worker(self, o):
        started = time.time()

        def notify(stage, percent):
            Clock.schedule_once(lambda dt: self._nup_progress(stage, percent))

        try:
            output = o['output']
            try:
                result = self._nup_run(o, output, notify)
            except ValueError as first:
                # A game plus DLC cannot go into one .nsp file; use a folder instead.
                if o['key'] == 'nup_to_nsp' and 'new output folder' in str(first) and output:
                    output = unique_output(output.parent, output.stem, ext='')
                    result = self._nup_run(o, output, notify)
                else:
                    raise
            log = format_nup_result(o['label'], result) + '\nTime: %.1f min' % ((time.time() - started) / 60)
            Clock.schedule_once(lambda dt: self._nup_finished('Complete.', log))
        except InterruptedError:
            Clock.schedule_once(lambda dt: self._nup_finished('Cancelled.', 'Unfinished output was removed.'))
        except Exception as e:  # noqa: BLE001
            detail = str(e) or e.__class__.__name__
            print(traceback.format_exc())
            Clock.schedule_once(lambda dt: self._nup_finished('Failed.', detail))

    def _nup_progress(self, stage, percent):
        self.root.ids.nup_progress.value = percent
        self.root.ids.nup_status.text = f'{stage}  {percent:.0f}%'

    def _nup_finished(self, status, log):
        ids = self.root.ids
        self.busy = False
        ids.nup_run_btn.disabled = False
        ids.nup_cancel_btn.disabled = True
        ids.build_btn.disabled = False
        if status == 'Complete.':
            ids.nup_progress.value = 100
        self.nup_say(status, log)

    def cancel_build(self):
        self.cancel_event.set()
        self.say('Cancelling...')
        self.nup_say('Cancelling...')


if __name__ == '__main__':
    NSPBoxApp().run()
