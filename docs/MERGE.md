# Merging atticus-mac into the Windows port

`atticus.py` reaches the OS only through `atticus_platform` (`import atticus_platform as plat; winctl = plat.ctl`).
When an upstream change adds a macOS call, replace it with the platform call below (add a function to
`atticus_platform/win32/` and `atticus_platform/fake.py` if none fits) and add the row here.

| macOS (atticus-mac) | Windows port | Interface (`base.py`) |
|---|---|---|
| `osascript` window bounds / `System Events` | `winctl.place`, `winctl.frame`, `winctl.find` | `Windows` |
| `open -a`, `mdfind kMDItemKind == Application` | `winctl.launch`, `winctl.apps`, `winctl.opener` | `Apps` |
| `pbpaste` / `pbcopy` | `winctl.get_clip` / `winctl.set_clip` | `Clipboard` |
| Peekaboo `see` / `click` / `type` | `winctl.ui_see` / `ui_click` / `ui_set`, `hotkey`, `paste_into` | `Hands` |
| `screencapture` | `winctl.capture` | `Screen` |
| `security find-generic-password` (Keychain) | `winctl.secret_get` / `secret_set` (Credential Manager) | `Secrets` |
| process groups, `killpg` | `winctl.kill_tree` (psutil / taskkill) | `Process` |
| `launchd` plists | not yet (AP6: Task Scheduler) | `Scheduler` |
| AppleScript `URL of active tab` | `winctl.browser_url` (UI Automation); CDP later (AP5) | `Browser` |
| ScreenCaptureKit audio | not yet (Meeting Copilot: WASAPI loopback) | `Audio` |

Layout: `atticus_platform/win32/*.py` is the former `winctl.py`, split by its own section headings with every function
body unchanged (only `APPS_FILE`/`UI_FILE` moved to `atticus_platform/paths.py`, and `key`, `rect_for`, `ui_item` to
`pure.py`, shared with the fake). The package is not called `platform` because that would shadow Python's own module,
which `atticus.py` imports.
