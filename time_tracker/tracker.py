# time_tracker/tracker.py
"""
Utilities for time log management:
- load_time_log
- append_time_log
- parse_range (for overlap detection)
- check_overlaps(existing_list, start_dt, end_dt) -> list of overlaps
"""

import json, os, datetime

TIME_LOG = os.path.join(os.path.dirname(__file__), "..", "time_log.json")
# normalize path
TIME_LOG = os.path.normpath(TIME_LOG)

def load_time_log():
    if os.path.exists(TIME_LOG):
        with open(TIME_LOG, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def append_time_log(entry):
    data = []
    if os.path.exists(TIME_LOG):
        try:
            with open(TIME_LOG, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = []
    data.append(entry)
    with open(TIME_LOG, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def parse_range(e):
    """
    Return (start_dt, end_dt, label) where possible, else (None, None, None).
    Handles different historical formats:
      - {'start': iso, 'end': iso, ...}
      - {'timestamp': 'YYYY-MM-DD HH:MM:SS', 'seconds': N}
    """
    if not isinstance(e, dict):
        return (None, None, None)
    label = e.get("task_text") or e.get("task_id") or "?"
    if e.get("start") and e.get("end"):
        try:
            s = datetime.datetime.fromisoformat(e["start"])
            en = datetime.datetime.fromisoformat(e["end"])
            return (s, en, label)
        except:
            pass
    if e.get("timestamp") and e.get("seconds") is not None:
        try:
            ts = datetime.datetime.strptime(e["timestamp"], "%Y-%m-%d %H:%M:%S")
            sec = int(e.get("seconds", 0))
            # assume timestamp is end time
            en = ts
            s = ts - datetime.timedelta(seconds=sec)
            return (s, en, label)
        except:
            pass
    return (None, None, label)

def check_overlaps(existing_entries, start_dt, end_dt):
    """
    existing_entries: list (raw json objects)
    start_dt, end_dt: datetime objects
    Returns list of tuples (s_ex, e_ex, label) for overlaps where intervals intersect.
    Overlap condition: start_dt < e_ex and s_ex < end_dt
    """
    out = []
    for e in existing_entries:
        s_ex, e_ex, label = parse_range(e)
        if not s_ex or not e_ex:
            continue
        if start_dt < e_ex and s_ex < end_dt:
            out.append((s_ex, e_ex, label))
    return out

