import os, json, tkinter as tk

DEFAULT_SETTINGS = {
    "autoscreen_enabled": True,
    "autoscreen_interval": 15  # минут
}

FILE = "tasks.json"
SETTINGS_FILE = "settings.json"
TIME_LOG = "time_log.json"
SCREENSHOT_BASE = "screenshots"


def load_tasks():
    if os.path.exists(FILE):
        with open(FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_tasks(tasks):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def mask_date_entry(entry: tk.Entry):
    def on_validate(action, index, value_if_allowed, prior_value, text, validation_type, trigger_type, widget_name):
        if action == "1":  # вставка символа
            if not text.isdigit():
                return False
            # Автоматическая вставка точки после 2 и 5 символа
            if len(value_if_allowed) in (2, 5) and not value_if_allowed.endswith('.'):
                value_if_allowed += '.'
                entry.delete(0, tk.END)
                entry.insert(0, value_if_allowed)
        return len(value_if_allowed) <= 10
    vcmd = (entry.register(on_validate), "%d", "%i", "%P", "%s", "%S", "%v", "%V", "%W")
    entry.config(validate="key", validatecommand=vcmd)


def mask_time_entry(entry: tk.Entry):
    def on_validate(P):
        if len(P) > 5:
            return False
        for ch in P:
            if not (ch.isdigit() or ch == ':'):
                return False
        if len(P) == 2 and ':' not in P:
            def _insert_colon():
                cur = entry.get()
                if len(cur) == 2 and ':' not in cur:
                    entry.delete(0, tk.END)
                    entry.insert(0, cur + ":")
            entry.after(1, _insert_colon)
        return True
    vcmd = (entry.register(on_validate), "%P")
    entry.config(validate="key", validatecommand=vcmd)


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                from utils import DEFAULT_SETTINGS
                return {**DEFAULT_SETTINGS, **json.load(f)}
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def seconds_to_hms(sec):
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02}:{m:02}:{s:02}"

