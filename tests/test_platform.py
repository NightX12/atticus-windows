"""The platform layer: interfaces, the fake backend, and that the win32 backend keeps every name winctl.py had."""
import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import atticus_platform as plat
from atticus_platform import base, fake, pure

F = type('FakeGroups', (), base.grouped(fake))   # always the fake backend, also on Windows CI

CALLABLE = ['apps', 'windows', 'joplin']   # same names as their win32 submodules
WINCTL_NAMES = ['_all', '_find_item', '_find_items', '_joplin_settings', '_open_clip', '_panels', '_press', '_rid', '_titles', '_walk', 'apps',
                'ask_text', 'ask_yes', 'bash', 'bring', 'browser_url', 'capture', 'choose', 'cloaked', 'close', 'describe_exe', 'exe_of', 'find',
                'find_files', 'focus_app', 'frame', 'front', 'get_clip', 'hotkey', 'joplin', 'joplin_cmd', 'joplin_note', 'joplin_notebook', 'key',
                'keys', 'kill_tree', 'laptop', 'launch', 'matches', 'media', 'monitors', 'note', 'notify', 'opener', 'paste_into', 'pid_of', 'place',
                'ps', 'real_pid', 'rect_for', 'secret_get', 'secret_set', 'set_clip', 'set_frame', 'title', 'to_app', 'trash', 'ui_click', 'ui_item',
                'ui_see', 'ui_set', 'windows', 'BROWSERS', 'MEDIA', 'HOME']
ATTICUS_USES = ['_joplin_settings', 'apps', 'ask_text', 'ask_yes', 'bash', 'bring', 'browser_url', 'capture', 'choose', 'find', 'find_files', 'focus_app',
                'frame', 'front', 'get_clip', 'hotkey', 'joplin_cmd', 'key', 'kill_tree', 'launch', 'media', 'monitors', 'note', 'notify', 'opener',
                'paste_into', 'place', 'rect_for', 'secret_get', 'secret_set', 'trash', 'ui_click', 'ui_item', 'ui_see', 'ui_set', 'windows', 'BROWSERS']


class PlatformTests(unittest.TestCase):
    def setUp(self):
        fake.reset()

    def test_every_interface_is_there(self):
        for name, proto in base.INTERFACES.items():
            self.assertIsInstance(getattr(plat, name), proto, name)

    def test_backend_choice(self):
        self.assertEqual(plat.BACKEND, os.environ.get('ATTICUS_PLATFORM') or ('win32' if sys.platform == 'win32' else 'fake'))

    def test_fake_has_what_atticus_calls(self):
        missing = [n for n in ATTICUS_USES if not hasattr(fake, n)]
        self.assertEqual(missing, [])

    def test_win32_keeps_every_winctl_name(self):
        """On Windows: the real import. Elsewhere: the same import with stub DLLs, which still catches cycles and NameErrors at import."""
        code = ('import sys, ctypes, json\n'
                + ("" if sys.platform == 'win32' else 'from unittest import mock\nsys.platform = "win32"; ctypes.WinDLL = mock.MagicMock()\n')
                + 'import atticus_platform.win32 as w\n'
                f'print(json.dumps([n for n in {WINCTL_NAMES!r} if not hasattr(w, n)] + [n for n in {CALLABLE!r} if not callable(getattr(w, n))]))\n')
        r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), '[]')

    def test_win32_refuses_other_systems(self):
        if sys.platform == 'win32':
            self.skipTest('Windows')
        r = subprocess.run([sys.executable, '-c', 'import atticus_platform.win32'], capture_output=True, text=True,
                           cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.assertIn('ImportError', r.stderr)

    def test_fake_windows_find_focus_and_front(self):
        fake.WINDOWS.extend([{'hwnd': 1, 'title': 'notes.txt - Notepad', 'exe': 'notepad.exe', 'proc': 'notepad', 'app': 'Notepad'},
                             {'hwnd': 2, 'title': 'Inbox - Google Chrome', 'exe': 'chrome.exe', 'proc': 'chrome', 'app': 'Google Chrome'}])
        self.assertEqual([w['hwnd'] for w in F.windows.find('chrome')], [2])
        self.assertTrue(F.apps.focus('Google Chrome', 'inbox'))
        self.assertEqual(F.windows.front()[2], 2)
        self.assertFalse(F.apps.focus('Spotify'))
        self.assertEqual(F.windows.place('Notepad', 'middle'), 'where must be left, right, full or center')

    def test_fake_clipboard_and_secrets(self):
        F.clipboard.set('hello')
        self.assertEqual(F.clipboard.get(), 'hello')
        self.assertTrue(F.secrets.set('jellyfin/key', 's3cret'))
        self.assertEqual(F.secrets.get('jellyfin/key'), 's3cret')
        self.assertTrue(F.secrets.set('jellyfin/key', ''))
        self.assertEqual(F.secrets.get('jellyfin/key'), '')

    def test_rect_for_and_key_are_shared(self):
        self.assertIs(fake.rect_for, pure.rect_for)
        self.assertEqual(pure.key('Code.exe'), 'code')
        self.assertEqual(F.windows.rect_for('right', (0, 0, 1001, 800), (10, 10)), (500, 0, 501, 800))

    def test_ui_item_reads_the_last_look(self):
        with tempfile.TemporaryDirectory() as d:
            plat.configure(d)
            open(plat.paths.UI_FILE, 'w').write('{"items": {"B1": {"name": "Send", "type": "Button"}, "X1": {"name": "Send", "type": "Text"}}}')
            self.assertEqual(fake.ui_item('send')['type'], 'Button')
            self.assertIsNone(fake.ui_item('nothing'))

    @unittest.skipIf(sys.platform == 'win32', 'the fake backend kills with POSIX signals')
    def test_fake_kill_tree_stops_children(self):
        p = subprocess.Popen([sys.executable, '-c', 'import subprocess, sys, time; subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"]); time.sleep(30)'])
        time.sleep(.5)
        kids = fake._children(p.pid)
        self.assertTrue(kids)
        fake.kill_tree(p.pid)
        p.wait(timeout=5)
        time.sleep(.2)
        for k in kids:
            try:
                os.kill(k, 0)
                state = open(f'/proc/{k}/stat').read().split(') ')[1][0] if os.path.exists(f'/proc/{k}/stat') else 'Z'
                self.assertEqual(state, 'Z')   # only a zombie may remain until init reaps it
            except ProcessLookupError:
                pass

    def test_not_yet_ported_says_so(self):
        with self.assertRaises(NotImplementedError):
            plat.scheduler.install({'id': 'x'})
        with self.assertRaises(NotImplementedError):
            plat.audio.loopback_start('x.wav')


if __name__ == '__main__':
    unittest.main()
