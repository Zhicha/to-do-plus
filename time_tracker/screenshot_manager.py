# time_tracker/screenshot_manager.py
"""
Screenshot manager:
- save screenshots as JPEG to reduce size
- autoscreen thread
- monthly archive of previous month into ZIP (runs automatically if day >= 10 and archive not exists)
"""

import os, threading, datetime, time, zipfile
from pathlib import Path

try:
    from PIL import ImageGrab, Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

class ScreenshotManager:
    def __init__(self, base_dir="screenshots", get_project_callback=None, toast_master=None,
                 autoscreen_enabled=True, interval_minutes=15, jpg_quality=75):
        self.base_dir = os.path.abspath(base_dir)
        self.get_project = get_project_callback or (lambda: "Общее")
        self.toast_master = toast_master
        self.autoscreen_enabled = autoscreen_enabled
        self.interval_minutes = int(interval_minutes)
        self.jpg_quality = int(jpg_quality)
        self._thread = None
        self._stop = threading.Event()
        os.makedirs(self.base_dir, exist_ok=True)
        # run archive check on init in background thread (non-blocking)
        threading.Thread(target=self._maybe_archive_previous_month, daemon=True).start()

    def _toast(self, text, duration=3000):
        # weak coupling: if toast_master provided, try to show a small popover
        try:
            if self.toast_master:
                from tkinter import Toplevel, Label
                # try to use the Toast from app if exists
                if hasattr(self.toast_master, "winfo_exists"):
                    # instantiate a simple transient small window (non-blocking)
                    top = Toplevel(self.toast_master)
                    top.overrideredirect(True)
                    top.attributes("-topmost", True)
                    Label(top, text=text, bg="#333", fg="white", padx=10, pady=6).pack()
                    self.toast_master.update_idletasks()
                    mx = self.toast_master.winfo_rootx(); my = self.toast_master.winfo_rooty()
                    mw = self.toast_master.winfo_width(); mh = self.toast_master.winfo_height()
                    w = 360; h = 60
                    x = mx + mw - w - 10; y = my + mh - h - 10
                    top.geometry(f"{w}x{h}+{x}+{y}")
                    top.after(duration, top.destroy)
                    return
        except Exception:
            pass
        # fallback: print
        print("Toast:", text)

    def update_settings(self, enabled: bool, interval_minutes: int):
        self.autoscreen_enabled = bool(enabled)
        self.interval_minutes = int(interval_minutes)
        if self.autoscreen_enabled:
            self.start_autoscreen()
        else:
            self.stop_autoscreen()

    def start_autoscreen_if_needed(self):
        if self.autoscreen_enabled:
            self.start_autoscreen()

    def start_autoscreen(self):
        if not PIL_AVAILABLE:
            self._toast("Pillow не установлен — скриншоты недоступны.", duration=4000)
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._autoscreen_loop, daemon=True)
        self._thread.start()
        self._toast("Автоскриншоты включены.", duration=1500)

    def stop_autoscreen(self):
        self._stop.set()
        self._toast("Автоскриншоты остановлены.", duration=1200)

    def _autoscreen_loop(self):
        interval = max(1, int(self.interval_minutes)) * 60
        while not self._stop.wait(interval):
            try:
                self.take_screenshot(auto=True)
            except Exception as e:
                print("Autoscreen error:", e)

    def manual_screenshot(self):
        return self.take_screenshot(auto=False)

    def take_screenshot(self, auto=False):
        if not PIL_AVAILABLE:
            raise RuntimeError("Pillow не установлен")
        ts = datetime.datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") if False else datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        project = self.get_project() or "Общее"
        folder = os.path.join(self.base_dir, project)
        os.makedirs(folder, exist_ok=True)
        # save as JPG to reduce size
        filename = f"{ts}.jpg"
        path = os.path.join(folder, filename)
        try:
            img = ImageGrab.grab()
            # ensure RGB for JPEG
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(path, "JPEG", quality=self.jpg_quality, optimize=True)
            if not auto:
                self._toast(f"Скриншот сохранён: {path}", duration=3000)
            return path
        except Exception as e:
            print("Ошибка скриншота:", e)
            raise

    # Archive previous month into ZIP and remove original files (keep only archive)
    def _maybe_archive_previous_month(self):
        try:
            now = datetime.datetime.datetime.now()
        except Exception:
            now = datetime.datetime.now()
        day = now.day
        # only run archiving if day >= 10
        if day < 10:
            return
        prev_month_date = (now.replace(day=1) - datetime.timedelta(days=1))
        year = prev_month_date.year; month = prev_month_date.month
        archive_name = f"{year}-{month:02d}.zip"
        archive_folder = os.path.join(self.base_dir, "archives")
        os.makedirs(archive_folder, exist_ok=True)
        archive_path = os.path.join(archive_folder, archive_name)
        if os.path.exists(archive_path):
            # already archived
            return
        # collect files from each project folder that belong to prev month
        files_to_archive = []
        for proj in os.listdir(self.base_dir):
            proj_path = os.path.join(self.base_dir, proj)
            if not os.path.isdir(proj_path) or proj == "archives":
                continue
            for fname in os.listdir(proj_path):
                # expect filenames like YYYY-MM-DD_HH-MM-SS.jpg (saved as jpg)
                try:
                    if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                        continue
                    # parse date part
                    date_part = fname.split("_")[0]
                    # date_part may be YYYY-MM-DD
                    dt = datetime.datetime.strptime(date_part, "%Y-%m-%d")
                    if dt.year == year and dt.month == month:
                        files_to_archive.append((os.path.join(proj_path, fname), os.path.join(proj, fname)))
                except Exception:
                    continue
        if not files_to_archive:
            return
        # create zip
        try:
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for fullpath, arcname in files_to_archive:
                    zf.write(fullpath, arcname=arcname)
            # remove originals
            for fullpath, _ in files_to_archive:
                try:
                    os.remove(fullpath)
                except:
                    pass
            self._toast(f"Скриншоты за {year}-{month:02d} заархивированы.", duration=4000)
        except Exception as e:
            print("Archive error:", e)
            self._toast(f"Ошибка архивации: {e}", duration=5000)

