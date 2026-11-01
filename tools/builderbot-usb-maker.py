#!/usr/bin/env python3
"""AerieOS USB Maker (R198): the stick maker (builderbot-stick.py) in a
window, for Windows above all, where it is built into one .exe that asks for
Administrator once at start. Nothing here writes a disk itself: every step
is builderbot-stick.py's own (the disks it lists, the release it fetches and
checks, the write and the read back), so the window and the command line
can never write a stick two ways.

    python tools/builderbot-usb-maker.py      the window (Python's own tkinter)

The steps, one page each: which AerieOS (the newest release, the newest
dev build, a release by name, or an image file you have); which stick (the
removable disks alone, the system disk never listed); a few settings for
the stick's first boot; the last page naming the stick by model, size and drive letter,
with a box to tick before Write; then the progress and the read back.

Another tool can open the same window with pages of its own before these,
and a prepared configuration for the stick's first boot (Maker(extra=...)).
"""
import datetime
import importlib.util
import os
import platform
import queue
import re
import subprocess
import sys
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
TITLE = "AerieOS USB Maker"


def load(name, file):
    path = os.path.join(HERE, file)
    spec = importlib.util.spec_from_file_location(name, path)
    if not os.path.isfile(path) or spec is None or spec.loader is None:
        raise SystemExit(f"{file} is not beside this tool in {HERE}: run it with builderbot-stick.py in the same folder")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


stick = load("builderbot_stick", "builderbot-stick.py")

if sys.platform == "win32":
    # A windowed .exe has no console: every PowerShell the stick maker asks
    # (the disks, the volumes on one) would flash one of its own open.
    _run = subprocess.run

    def _quiet(*a, **kw):
        kw.setdefault("creationflags", 0x08000000)    # CREATE_NO_WINDOW
        return _run(*a, **kw)
    subprocess.run = _quiet


class Stopped(Exception):
    """What the stick maker said when it stopped (its die)."""


def releases():
    """The published releases, newest first: [(tag, is a dev build)]."""
    import json
    import urllib.request
    req = urllib.request.Request(stick.API, headers={"Accept": "application/json", "User-Agent": "builderbot-usb-maker"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 (the releases' address)
        rows = json.loads(r.read())
    return [(str(x["tag_name"]), bool(x.get("prerelease"))) for x in rows
            if not x.get("draft") and re.fullmatch(stick.TAG, str(x.get("tag_name") or ""))]


def settings_lines(s):
    """The stick's builderbot.env lines from the settings page's fields: the
    dev channel, a name, a time zone and a fixed address; refused with why."""
    out = []
    if s.get("dev"):
        out.append("BB_RELEASE_CHANNEL=dev")
    if s.get("hostname"):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,62}", s["hostname"]):
            raise ValueError("a name is letters, digits and hyphens")
        out.append(f"BB_HOSTNAME={s['hostname']}")
    if s.get("tz"):
        if not re.fullmatch(r"[A-Za-z_]+(/[A-Za-z0-9_+-]+){0,2}", s["tz"]):
            raise ValueError("a time zone is Region/City, as Europe/London")
        out.append(f"TZ={s['tz']}")
    if s.get("address"):
        ip = r"\d{1,3}(\.\d{1,3}){3}"
        if not (re.fullmatch(ip, s["address"]) and re.fullmatch(r"\d{1,2}", s.get("mask") or "")
                and re.fullmatch(ip, s.get("gateway") or "")):
            raise ValueError("a fixed address needs the address, the mask's length (24) and the gateway")
        out += [f"BB_NET_ADDRESS={s['address']}", f"BB_NET_MASK={s['mask']}", f"BB_NET_GATEWAY={s['gateway']}"]
        if s.get("dns"):
            out.append(f"BB_NET_DNS={s['dns']}")
    return out


class Maker(tk.Tk):
    """The window: a page at a time, Back and Next under it. `extra` is
    another tool's: {"pages": [(title, build(frame, maker) -> check() or
    None)], "config": maker -> path of a prepared configuration or None,
    "sets": maker -> {KEY: VALUE} over the settings', "done": words}."""

    def __init__(self, extra=None, title=TITLE):
        super().__init__()
        self.title(title)
        self.minsize(620, 460)
        self.extra = extra or {}
        self.q = queue.Queue()
        self.busy = False
        self.choice = {"source": tk.StringVar(value=self.extra.get("source") or "latest"), "tag": tk.StringVar(), "file": tk.StringVar(),
                       "disk": None, "ack": tk.BooleanVar(value=False)}
        self.fields = {k: tk.StringVar() for k in ("hostname", "tz", "address", "mask", "gateway", "dns")}
        self.head = ttk.Label(self, font=("Segoe UI", 14, "bold"))
        self.head.pack(anchor="w", padx=16, pady=8)
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True, padx=16)
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=16, pady=8)
        self.back = ttk.Button(bar, text="Back", command=lambda: self.go(-1))
        self.back.pack(side="left")
        self.next = ttk.Button(bar, text="Next", command=lambda: self.go(1))
        self.next.pack(side="right")
        self.pages = [*(self.extra.get("pages") or []), ("Which AerieOS", self.page_release), ("Which stick", self.page_disk),
                      ("The stick's first boot", self.page_settings), ("Write it", self.page_confirm),
                      ("Writing", self.page_write)]
        self.at, self.check = 0, None
        self.show()
        self.after(100, self.pump)

    # ---- moving between pages ----
    def show(self):
        for w in self.body.winfo_children():
            w.destroy()
        title, build = self.pages[self.at]
        self.head.config(text=f"{title}")
        # The window's own pages are its methods; another tool's are given it.
        self.check = build(self.body) if getattr(build, "__self__", None) is self else build(self.body, self)
        last = self.at == len(self.pages) - 1
        self.back.config(state="disabled" if self.at == 0 or last else "normal")
        self.next.config(text="Write" if self.at == len(self.pages) - 2 else "Next", state="disabled" if last else "normal")

    def go(self, step):
        if step > 0 and self.check:
            why = self.check()
            if why:
                messagebox.showwarning(TITLE, why, parent=self)
                return
        self.at = max(0, min(len(self.pages) - 1, self.at + step))
        self.show()

    # ---- the pages ----
    def page_release(self, f):
        v = self.choice["source"]
        best = self.extra.get("source") or "latest"
        rows = [("latest", "The newest release" + (" (recommended)" if best == "latest" else "")),
                ("dev", "The newest dev build" + (" (recommended)" if best == "dev" else " (unstable)")),
                ("tag", "A release by name:"), ("file", "An image file I have:")]
        for val, word in rows:
            ttk.Radiobutton(f, text=word, value=val, variable=v).pack(anchor="w", pady=2)
            if val == "tag":
                tags = ttk.Combobox(f, textvariable=self.choice["tag"], width=36)
                tags.pack(anchor="w", padx=24)
                threading.Thread(target=lambda: self.q.put(("tags", releases())), daemon=True).start()
                self._tags = tags
            if val == "file":
                row = ttk.Frame(f)
                row.pack(anchor="w", padx=24, fill="x")
                ttk.Entry(row, textvariable=self.choice["file"], width=48).pack(side="left")
                ttk.Button(row, text="Browse", command=lambda: self.choice["file"].set(
                    filedialog.askopenfilename(parent=self, filetypes=[("AerieOS stick image", "*.raw.xz")]) or self.choice["file"].get())).pack(side="left", padx=6)
        ttk.Label(f, text="The image is fetched from AerieOS's releases, its checksum and its build's attestation checked.",
                  foreground="gray", wraplength=560).pack(anchor="w", pady=(12, 0))

        def check():
            s = v.get()
            if s == "tag" and not re.fullmatch(stick.TAG, self.choice["tag"].get().strip()):
                return "Name a release by its tag, as v0.9.0 or v0.9.0-dev.4724."
            if s == "file" and not os.path.isfile(self.choice["file"].get()):
                return "Pick the image file: builderbot-os-VERSION.stick.raw.xz."
            return None
        return check

    def page_disk(self, f):
        ttk.Label(f, text="Only removable disks are listed; the one running this computer never is. Plug the stick in and press Look again.",
                  wraplength=560).pack(anchor="w")
        lb = tk.Listbox(f, height=8, activestyle="none")
        lb.pack(fill="both", expand=True, pady=8)
        rows = []

        def fill():
            lb.delete(0, "end")
            rows.clear()
            try:
                for d in stick.disks():
                    if d.get("removable") and not d.get("system"):
                        rows.append(d)
                        lb.insert("end", f"{stick.named(d)}   ({d['id']})")
            except Exception as e:      # noqa: BLE001 (said, not raised)
                lb.insert("end", f"the disks could not be listed: {e}")
            if not rows:
                lb.insert("end", "no removable disk: plug the stick in, then Look again")
        ttk.Button(f, text="Look again", command=fill).pack(anchor="w")
        fill()

        def check():
            sel = lb.curselection()
            if not sel or sel[0] >= len(rows):
                return "Pick the stick to write."
            self.choice["disk"] = rows[sel[0]]
            return None
        return check

    def page_settings(self, f):
        grid = ttk.Frame(f)
        grid.pack(anchor="w")
        rows = [("hostname", "The machine's name"), ("tz", "Time zone (Region/City)"), ("address", "A fixed address (empty: from DHCP)"),
                ("mask", "Its mask's length (24)"), ("gateway", "Gateway"), ("dns", "DNS servers (comma between)")]
        for i, (k, word) in enumerate(rows):
            ttk.Label(grid, text=word).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Entry(grid, textvariable=self.fields[k], width=30).grid(row=i, column=1, sticky="w", padx=8)
        ttk.Label(f, text="All of these are optional: left empty, the first boot asks or uses DHCP.", foreground="gray").pack(anchor="w", pady=(10, 0))

        def check():
            try:
                settings_lines(self.settings())
            except ValueError as e:
                return str(e)
            return None
        return check

    def settings(self):
        return {k: v.get().strip() for k, v in self.fields.items()}

    def page_confirm(self, f):
        d = self.choice["disk"] or {}
        ttk.Label(f, text=stick.named(d), font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(f, text=f"({d.get('id', '')})", foreground="gray").pack(anchor="w")
        ttk.Label(f, text="Everything on this stick is erased and cannot be brought back. Check it is the stick you mean, "
                          "and that nothing on it is needed.", wraplength=560, foreground="#b42318").pack(anchor="w", pady=12)
        self.choice["ack"].set(False)
        ttk.Checkbutton(f, text="Erase this stick and write AerieOS to it", variable=self.choice["ack"]).pack(anchor="w")
        return lambda: None if self.choice["ack"].get() else "Tick the box to say this is the stick to erase."

    def page_write(self, f):
        self.bar = ttk.Progressbar(f, mode="indeterminate")
        self.bar.pack(fill="x", pady=(4, 8))
        self.bar.start(12)
        self.log = tk.Text(f, height=14, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)
        self.busy = True
        threading.Thread(target=self.work, daemon=True).start()
        return None

    # ---- the work, on its own thread; the window hears it through the queue ----
    def work(self):
        # Downloads, not AppData: the Microsoft Store's Python keeps a private
        # copy of AppData, so the image and the log were where nobody looks.
        work_dir = os.path.join(os.path.expanduser("~"), "Downloads", "AerieOS USB Maker")
        os.makedirs(work_dir, exist_ok=True)
        self.log_path = os.path.join(work_dir, "usb-maker.log")
        logf = open(self.log_path, "a", encoding="utf-8")

        def note(s):
            logf.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {s}\n")
            logf.flush()

        def say(s):
            note(s)
            self.q.put(("say", str(s)))
        stick.say = say

        def die(s):
            raise Stopped(str(s))
        stick.die = die
        cfg = None
        d = self.choice["disk"] or {}
        note(f"---- {self.title()}: {sys.executable} {platform.python_version()} on {platform.platform()}, "
             f"administrator {stick.is_admin()}")
        note(f"the image: {self.choice['source'].get()} {self.choice['tag'].get() or self.choice['file'].get()}; "
             f"the stick: {d.get('id')} ({stick.named(d) if d else 'none'})")
        try:
            os.chdir(work_dir)
            if not stick.is_admin():
                raise Stopped("writing a stick needs Administrator: close this window and start it again, "
                              "answering Yes when Windows asks; nothing was fetched or written")
            src = self.choice["source"].get()
            if src == "file":
                image = self.choice["file"].get()
                if os.path.isfile(image + ".sha256"):
                    stick.check_sha(image, image + ".sha256")
                stick.attested(image)
                stick.signed(stick.tag_of(image), image)
            else:
                image = stick.release_image(self.choice["tag"].get().strip() if src == "tag" else "latest", "dev" if src == "dev" else "normal")
            d = self.choice["disk"]
            again = stick.pick(d["id"])
            if (again["size"], again["model"]) != (d["size"], d["model"]):
                raise Stopped("the stick is not the one picked any more (it was unplugged or changed): nothing written")
            lines = {ln.split("=", 1)[0]: ln.split("=", 1)[1] for ln in settings_lines(self.settings())}
            lines.update((self.extra.get("sets") or (lambda m: {}))(self) or {})
            cfg = (self.extra.get("config") or (lambda m: None))(self)
            self.q.put(("mode", "write"))
            stick.write_image(image, d["id"], verify_after=True, sets=[f"{k}={v}" for k, v in lines.items()], config=cfg)
            self.q.put(("done", self.extra.get("done") or "Done. Boot the machine from the stick: it comes up as its own controller, "
                        "and its first page, at http://ITS-ADDRESS:7680 on your network, makes the owner."))
            note("done")
        except Stopped as e:
            note(f"stopped: {e}")
            self.q.put(("stopped", f"{e}\n\nThe log: {self.log_path}"))
        except Exception as e:      # noqa: BLE001 (said in the window; the traceback goes to the log)
            note("failed:\n" + traceback.format_exc())
            self.q.put(("stopped", f"{type(e).__name__}: {e}\n\nThe log, with the whole error: {self.log_path}"))
        finally:
            logf.close()
            if cfg and os.path.isfile(cfg):
                os.unlink(cfg)

    def pump(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "tags" and getattr(self, "_tags", None) and self._tags.winfo_exists():
                    self._tags["values"] = [t + ("  (dev build)" if dev else "") for t, dev in val]
                    self._tags.bind("<<ComboboxSelected>>", lambda e: self.choice["tag"].set(self._tags.get().split()[0]))
                elif kind in ("say", "done", "stopped") and getattr(self, "log", None):
                    self.log.config(state="normal")
                    self.log.insert("end", (val if kind == "say" else ("\n" + val)) + "\n")
                    self.log.see("end")
                    self.log.config(state="disabled")
                    m = re.search(r"(\d+)%$", val)
                    if m and kind == "say":
                        self.bar.stop()
                        self.bar.config(mode="determinate", value=int(m.group(1)))
                    if kind in ("done", "stopped"):
                        self.busy = False
                        self.bar.stop()
                        self.bar.config(mode="determinate", value=100 if kind == "done" else 0)
                        (messagebox.showinfo if kind == "done" else messagebox.showerror)(TITLE, val, parent=self)
                elif kind == "mode" and getattr(self, "bar", None):
                    self.bar.config(mode="indeterminate")
                    self.bar.start(12)
        except queue.Empty:
            pass
        self.after(150, self.pump)


def main(extra=None, title=TITLE):
    # Writing a disk needs Administrator: started without it (python, not
    # the .exe), the window starts again as Administrator, Windows asking.
    if stick.elevate():
        return
    app = Maker(extra, title)
    app.protocol("WM_DELETE_WINDOW", lambda: app.destroy() if not app.busy or messagebox.askyesno(
        TITLE, "A stick is being written. Stop and close? The stick will not boot until it is written again.", parent=app) else None)
    app.mainloop()


if __name__ == "__main__":
    main()
