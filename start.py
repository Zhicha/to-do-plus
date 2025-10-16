# start.py
import tkinter as tk
from tkinter import ttk, messagebox
import datetime, json, os, uuid, threading, time, subprocess, sys
from pathlib import Path

# local modules
from time_tracker import tracker
from time_tracker.screenshot_manager import ScreenshotManager

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
        if action == "1":
            if not text.isdigit():
                return False
            if len(value_if_allowed) in (2, 5) and not value_if_allowed.endswith('.'):
                def _insert():
                    cur = entry.get()
                    if len(cur) == 2 or len(cur) == 5:
                        entry.delete(0, tk.END)
                        entry.insert(0, cur + '.')
                entry.after(1, _insert)
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

# Toast (auto-size to show full text)
class Toast:
    def __init__(self, master, text, duration=3000):
        self.top = tk.Toplevel(master)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        try:
            self.top.attributes("-alpha", 0.95)
        except Exception:
            pass
        self.label = tk.Label(self.top, text=text, bg="#333", fg="white", padx=12, pady=8, justify="left", anchor="w")
        self.label.config(wraplength=400)
        self.label.pack()
        master.update_idletasks()
        self.top.update_idletasks()

        req_w = self.label.winfo_reqwidth()
        req_h = self.label.winfo_reqheight()
        max_w = 700
        max_h = 250
        width = min(max_w, req_w + 8)
        height = min(max_h, req_h + 6)
        if req_w > max_w:
            self.label.config(wraplength=(max_w - 20))
            self.top.update_idletasks()
            req_w = self.label.winfo_reqwidth()
            req_h = self.label.winfo_reqheight()
            width = min(max_w, req_w + 8)
            height = min(max_h, req_h + 6)

        try:
            mx = master.winfo_rootx()
            my = master.winfo_rooty()
            mwidth = master.winfo_width()
            mheight = master.winfo_height()
            x = mx + mwidth - width - 10
            y = my + mheight - height - 10
        except Exception:
            x = 100; y = 100

        self.top.geometry(f"{int(width)}x{int(height)}+{int(x)}+{int(y)}")
        self.top.after(duration, self.top.destroy)

class TodoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("To-Do Менеджер + Таймер")
        self.tasks = load_tasks()
        self.settings = load_settings()
        self.timer_running = False
        self.current_task_id = None

        # Screenshot manager (providing a callback to get current project)
        def _get_project_for_screenshot():
            if self.current_task_id:
                t = next((x for x in self.tasks if x["id"] == self.current_task_id), None)
                if t:
                    return t.get("project", "Общее")
            return "Общее"

        self.screenshot_mgr = ScreenshotManager(
            base_dir=SCREENSHOT_BASE,
            get_project_callback=_get_project_for_screenshot,
            toast_master=self.root,
            autoscreen_enabled=self.settings.get("autoscreen_enabled", True),
            interval_minutes=int(self.settings.get("autoscreen_interval", 15))
        )

        # Build UI (keeps structure similar to previous file)
        top = ttk.Frame(root, padding=5)
        top.pack(fill="x")
        ttk.Label(top, text="Задача:").pack(side="left")
        self.entry_text = ttk.Entry(top, width=40); self.entry_text.pack(side="left", padx=5)

        ttk.Label(top, text="Проект:").pack(side="left")
        self.entry_project = ttk.Combobox(top, values=self.get_projects(), width=14)
        self.entry_project.pack(side="left", padx=5)

        ttk.Label(top, text="Раздел:").pack(side="left")
        self.entry_section = ttk.Combobox(top, values=self.get_sections(), width=12)
        self.entry_section.pack(side="left", padx=5)

        ttk.Label(top, text="Дедлайн:").pack(side="left", padx=(6, 0))
        self.entry_deadline = ttk.Entry(top, width=12); self.entry_deadline.pack(side="left", padx=(2,6))
        mask_date_entry(self.entry_deadline)

        ttk.Label(top, text="Заметка:").pack(side="left")
        self.entry_note = ttk.Entry(top, width=18); self.entry_note.pack(side="left", padx=5)

        ttk.Button(top, text="➕ Добавить", command=self.add_task).pack(side="left", padx=5)
        ttk.Button(top, text="✏️ Редактировать", command=self.open_edit).pack(side="left", padx=5)
        self.var_hide_done = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Скрыть готовые", variable=self.var_hide_done, command=self.refresh).pack(side="left", padx=8)

        # autoscreen + reports
        setf = ttk.Frame(root, padding=5); setf.pack(fill="x")
        self.var_autoscreen = tk.BooleanVar(value=self.settings.get("autoscreen_enabled", True))
        ttk.Checkbutton(setf, text="Делать скриншоты", variable=self.var_autoscreen,
                        command=self.save_current_settings).pack(side="left")
        ttk.Label(setf, text="Интервал (мин):").pack(side="left", padx=(10,5))
        self.spin_interval = tk.Spinbox(setf, from_=1, to=120, width=5, command=self.save_current_settings)
        self.spin_interval.delete(0, "end"); self.spin_interval.insert(0, self.settings.get("autoscreen_interval", 15))
        self.spin_interval.pack(side="left")
        ttk.Button(setf, text="📸 Скриншот сейчас", command=self.screenshot_mgr.manual_screenshot).pack(side="left", padx=10)
        ttk.Button(setf, text="📊 Отчёты", command=self.open_reports).pack(side="left")

        # timer area
        timerf = ttk.Frame(root, padding=5); timerf.pack(fill="x")
        self.timer_label = ttk.Label(timerf, text="00:00:00"); self.timer_label.pack(side="left", padx=10)
        self.timer_indicator = ttk.Label(timerf, text="●", foreground="gray"); self.timer_indicator.pack(side="left")
        self.btn_start = ttk.Button(timerf, text="▶️ Старт", command=self.start_timer); self.btn_start.pack(side="left", padx=5)
        self.btn_stop = ttk.Button(timerf, text="⏹ Стоп", command=self.stop_timer, state="disabled"); self.btn_stop.pack(side="left", padx=5)

        # Add manual activity button
        self.btn_add_activity = ttk.Button(timerf, text="Добавить активность", command=self.add_manual_activity)
        self.btn_add_activity.pack(side="left", padx=6)

        self.current_task_label = ttk.Label(timerf, text="", foreground="black"); self.current_task_label.pack(side="left", padx=10)

        # tree tasks
        self.tree = ttk.Treeview(root, columns=("text","date","deadline","project","section","note","done"), show="headings", height=15)
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)
        column_spec = [
            ("text","Задача",520), ("date","Дата",70), ("deadline","Дедлайн",90),
            ("project","Проект",140), ("section","Раздел",120), ("note","Заметка",160), ("done","✓",40)
        ]
        for col,name,width in column_spec:
            self.tree.heading(col, text=name)
            self.tree.column(col, width=width, anchor="w")
        self.tree.tag_configure("done", foreground="green")
        self.tree.tag_configure("overdue", foreground="red")
        self.tree.tag_configure("current", background="#fff5b7")

        bottom = ttk.Frame(root, padding=5); bottom.pack(fill="x")
        ttk.Button(bottom, text="✅ Готово", command=self.mark_done).pack(side="left", padx=5)
        ttk.Button(bottom, text="🗑️ Удалить", command=self.delete_task).pack(side="left", padx=5)
        ttk.Button(bottom, text="🚪 Выход", command=root.quit).pack(side="right", padx=5)

        # initialize screenshot manager (archive check runs inside)
        self.screenshot_mgr.start_autoscreen_if_needed()

        self.refresh()
        self.update_timer()

    # helpers
    def get_sections(self):
        vals = sorted({t.get("section","") for t in self.tasks if t.get("section")})
        return vals or ["Общее"]
    def get_projects(self):
        vals = sorted({t.get("project","") for t in self.tasks if t.get("project")})
        return vals or ["Общее"]

    def add_task(self):
        text = self.entry_text.get().strip()
        if not text:
            messagebox.showwarning("Ошибка", "Введите текст задачи.")
            return
        t = {
            "id": str(uuid.uuid4()),
            "text": text,
            "project": self.entry_project.get().strip() or "Общее",
            "section": self.entry_section.get().strip(),
            "date": datetime.date.today().strftime("%d.%m.%Y"),
            "deadline": self.entry_deadline.get().strip(),
            "note": self.entry_note.get().strip(),
            "done": False
        }
        self.tasks.append(t)
        save_tasks(self.tasks)
        self.entry_text.delete(0, tk.END)
        try:
            self.entry_project.set(""); self.entry_section.set("")
        except: pass
        self.entry_deadline.delete(0, tk.END); self.entry_note.delete(0, tk.END)
        self.refresh()

    def refresh(self):
        try:
            self.entry_project['values'] = self.get_projects()
            self.entry_section['values'] = self.get_sections()
        except: pass

        hide_done = getattr(self, "var_hide_done", tk.BooleanVar(value=True)).get()
        today = datetime.date.today()
        for i in self.tree.get_children():
            self.tree.delete(i)
        for t in self.tasks:
            if hide_done and t.get("done"): continue
            tags = []
            if t.get("done"): tags.append("done")
            else:
                dl = t.get("deadline","")
                if dl:
                    try:
                        d = datetime.datetime.strptime(dl, "%d.%m.%Y").date()
                        if d < today: tags.append("overdue")
                    except: pass
            self.tree.insert("", "end", iid=t["id"],
                values=(t["text"], t.get("date",""), t.get("deadline",""),
                        t.get("project",""), t.get("section",""), t.get("note",""),
                        "✅" if t.get("done") else ""), tags=tags)

    def mark_done(self):
        sel = self.tree.selection()
        if not sel: return
        tid = sel[0]
        for t in self.tasks:
            if t["id"] == tid:
                t["done"] = not t.get("done", False)
                break
        save_tasks(self.tasks)
        self.refresh()

    def delete_task(self):
        sel = self.tree.selection()
        if not sel: return
        if not messagebox.askyesno("Удалить", "Удалить выбранную задачу?"): return
        tid = sel[0]
        self.tasks = [t for t in self.tasks if t["id"] != tid]
        save_tasks(self.tasks)
        self.refresh()

    def open_edit(self):
        sel = self.tree.selection()
        if not sel: return
        tid = sel[0]
        task = next((t for t in self.tasks if t["id"] == tid), None)
        if not task: return
        win = tk.Toplevel(self.root); win.title("Редактировать задачу"); win.geometry("420x220")
        def make_row_label(frame,label): ttk.Label(frame, text=label, width=12).pack(side="left")

        f1 = ttk.Frame(win, padding=4); f1.pack(fill="x", padx=6, pady=(6,0))
        make_row_label(f1, "Задача:"); e_text = ttk.Entry(f1); e_text.pack(side="left", fill="x", expand=True); e_text.insert(0, task["text"])

        f2 = ttk.Frame(win, padding=4); f2.pack(fill="x", padx=6, pady=(6,0))
        make_row_label(f2, "Проект:"); e_project = ttk.Combobox(f2, values=self.get_projects()); e_project.pack(side="left", fill="x", expand=True); e_project.set(task.get("project",""))
        f3 = ttk.Frame(win, padding=4); f3.pack(fill="x", padx=6, pady=(6,0))
        make_row_label(f3, "Раздел:"); e_section = ttk.Combobox(f3, values=self.get_sections()); e_section.pack(side="left", fill="x", expand=True); e_section.set(task.get("section",""))

        f4 = ttk.Frame(win, padding=4); f4.pack(fill="x", padx=6, pady=(6,0))
        make_row_label(f4, "Дедлайн:"); e_deadline = ttk.Entry(f4); e_deadline.pack(side="left", fill="x", expand=True); e_deadline.insert(0, task.get("deadline","")); mask_date_entry(e_deadline)

        f5 = ttk.Frame(win, padding=4); f5.pack(fill="x", padx=6, pady=(6,0))
        make_row_label(f5, "Заметка:"); e_note = ttk.Entry(f5); e_note.pack(side="left", fill="x", expand=True); e_note.insert(0, task.get("note",""))

        def save_edit():
            task["text"] = e_text.get().strip(); task["project"] = e_project.get().strip(); task["section"] = e_section.get().strip()
            task["deadline"] = e_deadline.get().strip(); task["note"] = e_note.get().strip()
            save_tasks(self.tasks); self.refresh(); win.destroy()

        btns = ttk.Frame(win, padding=6); btns.pack(fill="x")
        ttk.Button(btns, text="💾 Сохранить", command=save_edit).pack(side="left", padx=6)
        ttk.Button(btns, text="❌ Отмена", command=win.destroy).pack(side="left")

    # timer handlers
    def start_timer(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Таймер", "Выберите задачу.")
            return
        self.current_task_id = sel[0]
        self.timer_start = time.time()
        self.timer_running = True
        self.btn_start.config(state="disabled"); self.btn_stop.config(state="normal")
        self.screenshot_mgr.start_autoscreen_if_needed()
        self.screenshot_mgr.take_screenshot(auto=True)
        task = next((t for t in self.tasks if t["id"] == self.current_task_id), None)
        if task: self.current_task_label.config(text=f"— {task['text']}")
        self.highlight_current_task()
        Toast(self.root, "Таймер запущен")

    def stop_timer(self):
        if not self.timer_running: return
        self.timer_running = False
        self.btn_start.config(state="normal"); self.btn_stop.config(state="disabled")
        end_time = time.time(); elapsed = end_time - self.timer_start
        task = next((t for t in self.tasks if t["id"] == self.current_task_id), None)
        entry = {
            "task_id": self.current_task_id,
            "task_text": task.get("text","") if task else "",
            "project": task.get("project","") if task else "",
            "section": task.get("section","") if task else "",
            "start": datetime.datetime.fromtimestamp(self.timer_start).isoformat(),
            "end": datetime.datetime.fromtimestamp(end_time).isoformat(),
            "duration_seconds": int(elapsed)
        }
        tracker.append_time_log(entry)   # use tracker module for log writes
        self.screenshot_mgr.stop_autoscreen()
        Toast(self.root, f"Таймер остановлен ({seconds_to_hms(elapsed)})")
        self.remove_highlight(); self.current_task_id = None; self.refresh()

    def highlight_current_task(self):
        self.remove_highlight()
        if self.current_task_id and self.tree.exists(self.current_task_id):
            tags = list(self.tree.item(self.current_task_id, "tags"))
            if "current" not in tags: tags.append("current")
            self.tree.item(self.current_task_id, tags=tags)

    def remove_highlight(self):
        for item in self.tree.get_children():
            tags = list(self.tree.item(item, "tags"))
            if "current" in tags:
                tags.remove("current")
                self.tree.item(item, tags=tags)

    def update_timer(self):
        if self.timer_running:
            elapsed = int(time.time() - self.timer_start)
            self.timer_label.config(text=seconds_to_hms(elapsed))
            self.timer_indicator.config(foreground="green" if elapsed % 2 == 0 else "gray")
        else:
            self.timer_indicator.config(foreground="gray")
        self.root.after(1000, self.update_timer)

    def save_current_settings(self):
        self.settings["autoscreen_enabled"] = self.var_autoscreen.get()
        try:
            self.settings["autoscreen_interval"] = int(self.spin_interval.get())
        except Exception:
            self.settings["autoscreen_interval"] = DEFAULT_SETTINGS["autoscreen_interval"]
        save_settings(self.settings)
        # notify screenshot manager of new settings
        self.screenshot_mgr.update_settings(self.settings["autoscreen_enabled"], self.settings["autoscreen_interval"])

    # Manual activity dialog with overlap check and forbid future times
    def add_manual_activity(self):
        sel = self.tree.selection()
        if not sel:
            Toast(self.root, "Сначала выберите задачу!", duration=3000); return
        tid = sel[0]; task = next((t for t in self.tasks if t["id"] == tid), None)
        if not task:
            Toast(self.root, "Не удалось определить задачу.", duration=3000); return

        win = tk.Toplevel(self.root); win.title("Добавить активность"); win.geometry("380x240"); win.resizable(False, False)
        lbl = ttk.Label(win, text=task.get("text",""), wraplength=360, justify="left"); lbl.pack(padx=8, pady=(10,6))

        fr_date = ttk.Frame(win, padding=4); fr_date.pack(fill="x", padx=8)
        ttk.Label(fr_date, text="Дата:", width=10).pack(side="left")
        entry_date = ttk.Entry(fr_date, width=12); entry_date.pack(side="left"); entry_date.insert(0, datetime.date.today().strftime("%d.%m.%Y"))
        mask_date_entry(entry_date)

        fr_start = ttk.Frame(win, padding=4); fr_start.pack(fill="x", padx=8)
        ttk.Label(fr_start, text="Начало:", width=10).pack(side="left")
        entry_start = ttk.Entry(fr_start, width=8); entry_start.pack(side="left"); entry_start.insert(0, datetime.datetime.now().strftime("%H:%M"))
        mask_time_entry(entry_start)

        fr_end = ttk.Frame(win, padding=4); fr_end.pack(fill="x", padx=8)
        ttk.Label(fr_end, text="Окончание:", width=10).pack(side="left")
        entry_end = ttk.Entry(fr_end, width=8); entry_end.pack(side="left"); entry_end.insert(0, (datetime.datetime.now()+datetime.timedelta(minutes=15)).strftime("%H:%M"))
        mask_time_entry(entry_end)

        def on_save():
            date_s = entry_date.get().strip(); start_s = entry_start.get().strip(); end_s = entry_end.get().strip()
            try:
                start_dt = datetime.datetime.strptime(f"{date_s} {start_s}", "%d.%m.%Y %H:%M")
                end_dt = datetime.datetime.strptime(f"{date_s} {end_s}", "%d.%m.%Y %H:%M")
            except Exception:
                Toast(self.root, "Неверный формат даты/времени.", duration=3500); return
            if end_dt <= start_dt:
                Toast(self.root, "Время окончания должно быть позже начала.", duration=3500); return

            now_dt = datetime.datetime.now()
            if start_dt > now_dt or end_dt > now_dt:
                Toast(self.root, "Нельзя добавлять активность с началом или окончанием в будущем.", duration=4500); return

            # check overlaps using tracker helper
            existing = tracker.load_time_log()
            overlaps = tracker.check_overlaps(existing, start_dt, end_dt)
            if overlaps:
                # build full message (not truncated) and use Toast
                msg_lines = [f"Найдены перекрытия ({len(overlaps)}):"]
                for s_ex,e_ex,txt in overlaps[:10]:
                    msg_lines.append(f"• {s_ex.strftime('%Y-%m-%d %H:%M')} — {e_ex.strftime('%H:%M')} ({txt})")
                if len(overlaps) > 10:
                    msg_lines.append("...и другие")
                Toast(self.root, "\n".join(msg_lines), duration=6000)
                return

            duration = int((end_dt - start_dt).total_seconds())
            entry = {
                "task_id": tid,
                "task_text": task.get("text",""),
                "project": task.get("project",""),
                "section": task.get("section",""),
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "duration_seconds": duration
            }
            try:
                tracker.append_time_log(entry)
                Toast(self.root, "Активность добавлена.", duration=2500)
                win.destroy()
            except Exception as e:
                Toast(self.root, f"Ошибка записи: {e}", duration=4000)

        btns = ttk.Frame(win, padding=8); btns.pack(fill="x")
        ttk.Button(btns, text="💾 Сохранить", command=on_save).pack(side="left", padx=6)
        ttk.Button(btns, text="Отмена", command=win.destroy).pack(side="left")

    def open_reports(self):
        try:
            report_path = os.path.join(os.path.dirname(__file__), "report_time_tracker.py")
            subprocess.Popen([sys.executable, report_path])
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = TodoApp(root)
    root.mainloop()

