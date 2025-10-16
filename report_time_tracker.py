import tkinter as tk
from tkinter import ttk, messagebox
import datetime, json, os

TIME_LOG = "time_log.json"

def load_time_log():
    if os.path.exists(TIME_LOG):
        with open(TIME_LOG, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception as e:
                messagebox.showerror("Ошибка чтения", f"Не удалось загрузить лог: {e}")
                return []
    return []

def seconds_to_hms(s: int) -> str:
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h}:{m:02d}:{sec:02d}"

class ReportApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Отчёт — Time Tracker")
        self.root.geometry("1000x700")

        top = ttk.Frame(root, padding=6)
        top.pack(fill="x")

        ttk.Label(top, text="Период:").pack(side="left")
        self.combo = ttk.Combobox(
            top,
            values=[
                "День", "Неделя", "Месяц",
                "Текущая неделя", "Текущий месяц",
                "Пользовательский", "За всё время"
            ],
            width=20,
            state="readonly"
        )
        self.combo.current(0)
        self.combo.pack(side="left", padx=6)
        self.combo.bind("<<ComboboxSelected>>", self.on_mode_change)

        self.lbl_from = ttk.Label(top, text="C:")
        self.ent_from = ttk.Entry(top, width=12)
        self.lbl_to = ttk.Label(top, text="По:")
        self.ent_to = ttk.Entry(top, width=12)

        self.lbl_from.pack_forget(); self.ent_from.pack_forget()
        self.lbl_to.pack_forget(); self.ent_to.pack_forget()

        # main area
        main = ttk.Frame(root)
        main.pack(fill="both", expand=True, padx=6, pady=6)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)

        cols = ("task_text", "project", "section", "start", "end", "duration")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=20)
        headers = ["Задача", "Проект", "Раздел", "Начало", "Конец", "Длительность"]
        for c, h in zip(cols, headers):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=150 if c != "task_text" else 300)
        self.tree.pack(fill="both", expand=True)

        right = ttk.Frame(main, width=300)
        right.pack(side="right", fill="y")

        ttk.Label(right, text="Сводка по проектам:").pack(anchor="w", padx=6, pady=(6,0))
        self.tree_proj = ttk.Treeview(right, columns=("project","duration"), show="headings", height=8)
        self.tree_proj.heading("project", text="Проект")
        self.tree_proj.heading("duration", text="Время")
        self.tree_proj.column("project", width=180)
        self.tree_proj.column("duration", width=100, anchor="center")
        self.tree_proj.pack(fill="x", padx=6, pady=4)

        ttk.Label(right, text="Сводка по задачам:").pack(anchor="w", padx=6, pady=(10,0))
        self.tree_task = ttk.Treeview(right, columns=("task","duration"), show="headings", height=12)
        self.tree_task.heading("task", text="Задача")
        self.tree_task.heading("duration", text="Время")
        self.tree_task.column("task", width=180)
        self.tree_task.column("duration", width=100, anchor="center")
        self.tree_task.pack(fill="x", padx=6, pady=4)

        bottom = ttk.Frame(root, padding=6)
        bottom.pack(fill="x")
        self.lbl_total = ttk.Label(bottom, text="Итого: 0:00:00")
        self.lbl_total.pack(side="left")

        # new summary frame (for grouped totals)
        self.frame_summary = ttk.Frame(root, padding=(6, 0))
        self.frame_summary.pack(fill="x")
        self.tree_summary = ttk.Treeview(self.frame_summary, columns=("label", "duration"), show="headings", height=6)
        self.tree_summary.heading("label", text="Период")
        self.tree_summary.heading("duration", text="Время")
        self.tree_summary.column("label", width=200)
        self.tree_summary.column("duration", width=120, anchor="center")
        self.tree_summary.pack(fill="x", padx=6, pady=(0, 6))

        self.update("День")

    def on_mode_change(self, event=None):
        mode = self.combo.get()
        if mode == "Пользовательский":
            self.lbl_from.pack(side="left", padx=(10, 0)); self.ent_from.pack(side="left")
            self.lbl_to.pack(side="left", padx=(6, 0)); self.ent_to.pack(side="left")
            today = datetime.date.today()
            self.ent_from.delete(0, "end"); self.ent_to.delete(0, "end")
            self.ent_from.insert(0, (today - datetime.timedelta(days=7)).strftime("%Y-%m-%d"))
            self.ent_to.insert(0, today.strftime("%Y-%m-%d"))
            self.ent_from.bind("<Return>", lambda e: self.update("Пользовательский"))
            self.ent_to.bind("<Return>", lambda e: self.update("Пользовательский"))
        else:
            self.lbl_from.pack_forget(); self.ent_from.pack_forget()
            self.lbl_to.pack_forget(); self.ent_to.pack_forget()
            self.update(mode)

    def _normalize_entries(self, raw_log):
        out = []
        for idx, e in enumerate(raw_log):
            start_dt, end_dt, dur = None, None, None
            if e.get("start") and e.get("end"):
                try:
                    start_dt = datetime.datetime.fromisoformat(e["start"])
                    end_dt = datetime.datetime.fromisoformat(e["end"])
                    dur = int(e.get("duration_seconds", (end_dt - start_dt).total_seconds()))
                except:
                    continue
            elif e.get("timestamp") and e.get("seconds"):
                try:
                    ts = datetime.datetime.strptime(e["timestamp"], "%Y-%m-%d %H:%M:%S")
                    sec = int(e["seconds"])
                    end_dt = ts
                    start_dt = ts - datetime.timedelta(seconds=sec)
                    dur = sec
                except:
                    continue
            if start_dt and end_dt:
                out.append({
                    "task_text": e.get("task_text", "—"),
                    "project": e.get("project", "—"),
                    "section": e.get("section", "—"),
                    "start": start_dt, "end": end_dt,
                    "duration_seconds": dur, "orig_index": idx
                })
        return out

    def update(self, mode=None):
        raw = load_time_log()
        entries = self._normalize_entries(raw)
        if not mode: mode = self.combo.get()
        now = datetime.datetime.now()

        if mode == "День":
            start = datetime.datetime.combine(now.date(), datetime.time.min)
            end = datetime.datetime.combine(now.date(), datetime.time.max)
            grouping = None
        elif mode == "Неделя" or mode == "Текущая неделя":
            start = datetime.datetime.combine((now - datetime.timedelta(days=now.weekday())).date(), datetime.time.min)
            end = start + datetime.timedelta(days=6, hours=23, minutes=59, seconds=59)
            grouping = "by_day"
        elif mode == "Месяц" or mode == "Текущий месяц":
            start = datetime.datetime.combine(now.replace(day=1).date(), datetime.time.min)
            next_month = now.replace(day=28) + datetime.timedelta(days=4)
            end = datetime.datetime.combine((next_month - datetime.timedelta(days=next_month.day)).date(), datetime.time.max)
            grouping = "by_week"
        elif mode == "За всё время":
            start = datetime.datetime.min
            end = datetime.datetime.max
            grouping = None
        else:  # пользовательский
            try:
                start = datetime.datetime.fromisoformat(self.ent_from.get() + "T00:00:00")
                end = datetime.datetime.fromisoformat(self.ent_to.get() + "T23:59:59")
            except Exception:
                messagebox.showerror("Фильтр", "Неверный формат даты (YYYY-MM-DD).")
                return
            grouping = None

        filtered = [e for e in entries if not (e["end"] < start or e["start"] > end)]
        total_seconds = sum(e["duration_seconds"] for e in filtered)

        self.tree.delete(*self.tree.get_children())
        for e in filtered:
            self.tree.insert("", "end", values=(
                e["task_text"], e["project"], e["section"],
                e["start"].strftime("%Y-%m-%d %H:%M:%S"),
                e["end"].strftime("%Y-%m-%d %H:%M:%S"),
                seconds_to_hms(e["duration_seconds"])
            ))

        self.lbl_total.config(text=f"Итого: {seconds_to_hms(total_seconds)}")

        # summaries
        proj, task = {}, {}
        for e in filtered:
            proj[e["project"]] = proj.get(e["project"], 0) + e["duration_seconds"]
            task[e["task_text"]] = task.get(e["task_text"], 0) + e["duration_seconds"]

        self.tree_proj.delete(*self.tree_proj.get_children())
        for p, secs in sorted(proj.items(), key=lambda x: -x[1]):
            self.tree_proj.insert("", "end", values=(p, seconds_to_hms(secs)))

        self.tree_task.delete(*self.tree_task.get_children())
        for t, secs in sorted(task.items(), key=lambda x: -x[1]):
            self.tree_task.insert("", "end", values=(t, seconds_to_hms(secs)))

        # additional grouped summary at bottom
        self.tree_summary.delete(*self.tree_summary.get_children())

        if grouping == "by_day":
            days = {}
            for e in filtered:
                d = e["start"].strftime("%Y-%m-%d (%a)")
                days[d] = days.get(d, 0) + e["duration_seconds"]
            for d, s in sorted(days.items()):
                self.tree_summary.insert("", "end", values=(d, seconds_to_hms(s)))

        elif grouping == "by_week":
            weeks = {}
            for e in filtered:
                year, week, _ = e["start"].isocalendar()
                key = f"Неделя {week} ({year})"
                weeks[key] = weeks.get(key, 0) + e["duration_seconds"]
            for w, s in sorted(weeks.items()):
                self.tree_summary.insert("", "end", values=(w, seconds_to_hms(s)))

if __name__ == "__main__":
    root = tk.Tk()
    app = ReportApp(root)
    root.mainloop()

