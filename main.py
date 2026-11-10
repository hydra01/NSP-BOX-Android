"""NSP Box ZIP to NUP: pick a ZIP file, and the app extracts it and converts it to a .nup.

No keys are used and nothing is decrypted. The ZIP must hold an unencrypted .nsp file or a
game folder with exefs + romfs.
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

from helpers import default_output_dir, human_size, list_directory

KV = r'''
BoxLayout:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: .07, .08, .13, 1
        Rectangle:
            pos: self.pos
            size: self.size
    ScrollView:
        do_scroll_x: False
        bar_width: dp(4)
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            padding: dp(16)
            spacing: dp(12)

            Label:
                text: 'ZIP to NUP'
                font_size: '28sp'
                bold: True
                size_hint_y: None
                height: dp(52)
            Label:
                text: 'Choose a ZIP file. The app extracts it and converts it to a .nup file.'
                size_hint_y: None
                height: self.texture_size[1] + dp(8)
                text_size: self.width, None
                halign: 'center'
                font_size: '14sp'
                color: .75, .79, .88, 1

            Button:
                text: 'Choose ZIP file'
                size_hint_y: None
                height: dp(64)
                font_size: '18sp'
                on_release: app.pick_zip()
            Label:
                id: zip_label
                text: 'No file chosen'
                size_hint_y: None
                height: self.texture_size[1] + dp(8)
                text_size: self.width, None
                halign: 'center'
                font_size: '14sp'

            Button:
                id: go
                text: 'Convert to NUP'
                size_hint_y: None
                height: dp(64)
                font_size: '18sp'
                disabled: True
                background_color: .2, .6, .35, 1
                on_release: app.start()
            Button:
                id: cancel
                text: 'Cancel'
                size_hint_y: None
                height: dp(46)
                disabled: True
                on_release: app.cancel()

            ProgressBar:
                id: progress
                max: 100
                value: 0
                size_hint_y: None
                height: dp(16)
            Label:
                id: status
                text: 'Ready.'
                size_hint_y: None
                height: self.texture_size[1] + dp(8)
                text_size: self.width, None
                halign: 'center'
                font_size: '15sp'
            Label:
                id: log
                text: ''
                size_hint_y: None
                height: self.texture_size[1] + dp(8)
                text_size: self.width, None
                halign: 'left'
                font_size: '13sp'
                color: .8, .85, .95, 1

            Label:
                text: 'Saved to:'
                size_hint_y: None
                height: dp(24)
                text_size: self.width, None
                halign: 'left'
                font_size: '13sp'
                color: .6, .65, .75, 1
            TextInput:
                id: out_dir
                multiline: False
                size_hint_y: None
                height: dp(44)
                font_size: '14sp'
            Button:
                text: 'Change output folder'
                size_hint_y: None
                height: dp(44)
                on_release: app.pick_out()
'''


class Browser(Popup):
    """Simple tap-to-navigate folder/file picker (reliable on touch screens)."""

    def __init__(self, title, start, mode, callback, exts=(".zip",), **kw):
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


class ZipToNupApp(App):
    title = 'ZIP to NUP'
    zip_path = None
    busy = False
    popup = None
    cancel_event = threading.Event()

    def build(self):
        Window.bind(on_keyboard=self._on_key)
        return Builder.load_string(KV)

    def on_start(self):
        self.root.ids.out_dir.text = default_output_dir()
        self.ensure_storage_access()
        self.keep_awake()

    def _on_key(self, window, key, *args):
        if key == 27 and self.popup and self.popup._window:   # Android back button
            self.popup.dismiss()
            return True
        return False

    # ----- Android permissions / screen ----------------------------------------------------
    def ensure_storage_access(self):
        """Ask for 'All files access' so the app can read the ZIP and write the NUP anywhere."""
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
            self.say('Allow "All files access" for this app, then come back and try again.')
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
        if platform != 'android':
            return
        try:
            from android.runnable import run_on_ui_thread
            from jnius import autoclass

            @run_on_ui_thread
            def _flag():
                autoclass('org.kivy.android.PythonActivity').mActivity.getWindow().addFlags(128)
            _flag()
        except Exception:
            pass

    # ----- helpers ---------------------------------------------------------------------------
    def say(self, text, log=None):
        self.root.ids.status.text = text
        if log is not None:
            self.root.ids.log.text = log

    def _open_browser(self, title, start, mode, callback, exts=()):
        if not self.ensure_storage_access():
            return
        self.popup = Browser(title, start, mode, callback, exts=exts)
        self.popup.open()

    # ----- pickers -----------------------------------------------------------------------------
    def pick_zip(self):
        if self.busy:
            return
        start = str(Path(self.zip_path).parent) if self.zip_path else '/storage/emulated/0/Download'
        self._open_browser('Choose a ZIP file', start, 'file', self._zip_chosen, exts=('.zip',))

    def _zip_chosen(self, path):
        self.zip_path = path
        ids = self.root.ids
        try:
            size = human_size(Path(path).stat().st_size)
        except OSError:
            size = ''
        ids.zip_label.text = f'{Path(path).name}  ({size})' if size else Path(path).name
        ids.go.disabled = False
        ids.progress.value = 0
        self.say('Ready.', '')

    def pick_out(self):
        if self.busy:
            return
        self._open_browser('Choose the output folder', self.root.ids.out_dir.text, 'dir',
                           lambda p: setattr(self.root.ids.out_dir, 'text', p))

    # ----- convert -------------------------------------------------------------------------------
    def start(self):
        if self.busy or not self.zip_path:
            return
        try:
            import zstandard  # noqa: F401 - NUP archives are zstd-compressed
        except ImportError:
            self.say('Cannot convert.', 'This build of the app is missing the zstandard library.')
            return
        if not self.ensure_storage_access():
            return
        out_dir = self.root.ids.out_dir.text.strip()
        if not out_dir:
            self.say('Choose an output folder first.')
            return
        ids = self.root.ids
        self.busy = True
        self.cancel_event.clear()
        ids.go.disabled = True
        ids.cancel.disabled = False
        ids.progress.value = 0
        self.say('Starting...', '')
        threading.Thread(target=self._worker, args=(self.zip_path, out_dir), daemon=True).start()

    def _worker(self, zip_path, out_dir):
        import zip_convert
        started = time.time()

        def notify(stage, percent):
            Clock.schedule_once(lambda dt: self._progress(stage, percent))

        try:
            result = zip_convert.convert_zip(zip_path, out_dir, notify=notify, cancel=self.cancel_event)
            lines = [f'Saved: {p}' for p in result['outputs']]
            lines.append(f"Size: {human_size(result['size'])}")
            lines.append('Time: %.1f min' % ((time.time() - started) / 60))
            Clock.schedule_once(lambda dt: self._finished('Done.', '\n'.join(lines), True))
        except InterruptedError:
            Clock.schedule_once(lambda dt: self._finished('Cancelled.', 'Temporary files were removed.', False))
        except zip_convert.ConvertError as e:
            msg = str(e)
            Clock.schedule_once(lambda dt: self._finished('Could not convert.', msg, False))
        except Exception as e:  # noqa: BLE001
            print(traceback.format_exc())
            msg = str(e) or e.__class__.__name__
            Clock.schedule_once(lambda dt: self._finished('Failed.', msg, False))

    def _progress(self, stage, percent):
        self.root.ids.progress.value = percent
        self.root.ids.status.text = f'{stage}  {percent:.0f}%'

    def _finished(self, status, log, ok):
        ids = self.root.ids
        self.busy = False
        ids.go.disabled = False
        ids.cancel.disabled = True
        if ok:
            ids.progress.value = 100
        self.say(status, log)

    def cancel(self):
        self.cancel_event.set()
        self.say('Cancelling...')


if __name__ == '__main__':
    ZipToNupApp().run()
