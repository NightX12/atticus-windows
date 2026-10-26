"""winctl section: dialogs (split from winctl.py, code unchanged)."""
import ctypes, json, os, re, subprocess, sys, time
from ctypes import wintypes as W
from ._core import ps

# ---------- talking to the person ----------

PIPE = r'\\.\pipe\atticus'


def to_app(line):
    """One line to the running Atticus app (toasts, its own settings). False when it isn't running."""
    try:
        with open(PIPE, 'w', encoding='utf-8') as p:
            p.write(line.replace('\n', ' ') + '\n')
        return True
    except OSError:
        return False


def notify(text, heading='Atticus'):
    if to_app('notify\t' + text):
        return
    t = text.replace("'", "''")
    h = heading.replace("'", "''")
    ps("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; "
       "$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
       f"$s = $x.GetElementsByTagName('text'); $s.Item(0).InnerText = '{h}'; $s.Item(1).InnerText = '{t}'; "
       "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe').Show([Windows.UI.Notifications.ToastNotification]::new($x))")


def ask_text(prompt='What should I do?'):
    import tkinter as tk
    from tkinter import simpledialog
    r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)
    try:
        return (simpledialog.askstring('Atticus', prompt, parent=r) or '').strip()
    finally:
        r.destroy()


def ask_yes(heading, text):
    import tkinter as tk
    from tkinter import messagebox
    r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)
    try:
        return messagebox.askyesno(heading, text + '\n\nAllow?', parent=r)
    finally:
        r.destroy()


def choose(question, options):
    """A small list to pick from when there is no Atticus box. -> index, or None."""
    import tkinter as tk
    r = tk.Tk(); r.title('Atticus'); r.attributes('-topmost', True)
    got = []
    tk.Label(r, text=question, padx=12, pady=8).pack()
    lb = tk.Listbox(r, width=60, height=min(8, len(options)))
    for o in options:
        lb.insert('end', o)
    lb.pack(padx=12)
    lb.bind('<Double-Button-1>', lambda _: (got.extend(lb.curselection()), r.destroy()))
    tk.Button(r, text='Pick', command=lambda: (got.extend(lb.curselection()), r.destroy())).pack(pady=8)
    r.mainloop()
    return got[0] if got else None


