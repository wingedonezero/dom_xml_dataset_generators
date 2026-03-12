#!/usr/bin/env python3
"""
DoM XML Dataset Generator — GUI Frontend
Supports: xml_dataset_generator_nsp.py, xml_dataset_generator_galaxy.py,
          xml_dataset_generator_gm9.py, xml_dataset_generator_nold.py,
          xml_dataset_generator_anonymous.py, cdn2nsp.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess, threading, json, os, shlex, sys, venv, platform
from datetime import datetime

# ── Config ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "dom_gui_config.json")
VENV_DIR    = os.path.join(SCRIPT_DIR, ".dom_venv")

def _venv_python():
    if platform.system() == "Windows":
        p = os.path.join(VENV_DIR, "Scripts", "python.exe")
    else:
        p = os.path.join(VENV_DIR, "bin", "python")
    return p if os.path.exists(p) else None

DEFAULTS = {
    "scripts_dir":           SCRIPT_DIR,
    "hactoolnet_path":       "",
    "keys_path":             "",
    "cert_path":             "",
    "default_outdir":        "",
    "dumper":                "",
    "project":               "",
    "tool":                  "DoM XML Dataset Generator",
    "section":               "Trusted Dump",
    "region":                "World",
    "num_threads":           "4",
    "use_venv":              True,
    "nsp_nspdir":            "",
    "nsp_exclude_nsp":       False,
    "nsp_exclude_tik":       False,
    "nsp_exclude_comment":   False,
    "nsp_cdate_as_ddate":    False,
    "nsp_dump_date":         "",
    "nsp_release_date":      "",
    "galaxy_csvdir":         "",
    "galaxy_httpdir":        "",
    "gm9_indir":             "",
    "nold_indir":            "",
    "anon_input":            "",
    "cdn_cdndir":            "",
    "cdn_process_nsp":       False,
    "cdn_keep_deltas":       False,
    "run_history":           [],
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                d = json.load(f)
            cfg = dict(DEFAULTS)
            cfg.update(d)
            return cfg
        except Exception:
            pass
    return dict(DEFAULTS)

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        messagebox.showerror("Config Error", f"Could not save config:\n{e}")

# ── Script patcher ────────────────────────────────────────────────────────────

# Known bad imports in the scripts that need to be removed before running.
# Key = script filename, Value = list of exact lines to strip out.
KNOWN_BAD_IMPORTS = {
    "xml_dataset_generator_nsp.py": [
        "from turtle import title\n",
        "from turtle import title\r\n",
    ],
}

def patch_script_if_needed(script_path):
    """
    Removes known broken import lines from a script in-place (one-time, idempotent).
    Returns True if a patch was applied, False if already clean.
    """
    name = os.path.basename(script_path)
    bad_lines = KNOWN_BAD_IMPORTS.get(name)
    if not bad_lines or not os.path.exists(script_path):
        return False
    with open(script_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    new_lines = [l for l in lines if l not in bad_lines]
    if len(new_lines) == len(lines):
        return False  # nothing to remove
    with open(script_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    return True


# ── Palette ────────────────────────────────────────────────────────────────────

BG     = "#1e1e2e"
BG2    = "#181825"
BG3    = "#313244"
BG4    = "#45475a"
ACCENT = "#cba6f7"
BLUE   = "#89b4fa"
GREEN  = "#a6e3a1"
RED    = "#f38ba8"
YELLOW = "#f9e2af"
TEAL   = "#94e2d5"
ORANGE = "#fab387"
TEXT   = "#cdd6f4"
TEXT2  = "#a6adc8"
MONO   = ("Courier New", 9)
FONT   = ("Segoe UI", 10)
FONTB  = ("Segoe UI", 10, "bold")
FONTH  = ("Segoe UI", 11, "bold")

# ── Mousewheel-aware ScrollableFrame ──────────────────────────────────────────

class ScrollableFrame(tk.Frame):
    """Canvas+scrollbar frame that scrolls on mouse wheel when hovered."""
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self._scroll = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scroll.set)
        self._scroll.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self._canvas, bg=BG)
        self._win  = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>",   self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<Enter>",     self._bind_wheel)
        self._canvas.bind("<Leave>",     self._unbind_wheel)
        # Also bind when hovering over child widgets
        self.inner.bind("<Enter>",  self._bind_wheel)
        self.inner.bind("<Leave>",  self._unbind_wheel)

    def _on_inner_configure(self, _e):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, e):
        self._canvas.itemconfig(self._win, width=e.width)

    def _bind_wheel(self, _e=None):
        self._canvas.bind_all("<MouseWheel>", self._scroll_win)   # Windows / macOS
        self._canvas.bind_all("<Button-4>",   self._scroll_win)   # Linux up
        self._canvas.bind_all("<Button-5>",   self._scroll_win)   # Linux down

    def _unbind_wheel(self, _e=None):
        self._canvas.unbind_all("<MouseWheel>")
        self._canvas.unbind_all("<Button-4>")
        self._canvas.unbind_all("<Button-5>")

    def _scroll_win(self, event):
        if event.num == 4:
            self._canvas.yview_scroll(-2, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(2, "units")
        else:
            self._canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

# ── Widget helpers ─────────────────────────────────────────────────────────────

def make_frame(parent, **kw):
    return tk.Frame(parent, bg=BG, **kw)

def make_label(parent, text, color=TEXT2, font=FONT, **kw):
    return tk.Label(parent, text=text, bg=BG, fg=color, font=font, **kw)

def styled_button(parent, text, command, color=ACCENT, **kw):
    return tk.Button(parent, text=text, command=command,
                     bg=BG3, fg=color, font=FONT, relief="flat",
                     activebackground=color, activeforeground=BG,
                     padx=8, pady=3, cursor="hand2", **kw)

def section_bar(parent, text):
    f = tk.Frame(parent, bg=BG2, pady=1)
    f.pack(fill="x", pady=(12, 4))
    tk.Label(f, text=f"  {text}", bg=BG2, fg=ACCENT, font=FONTH,
             anchor="w", pady=5).pack(fill="x")


class PathRow(tk.Frame):
    def __init__(self, parent, label, kind="dir", width=46, required=False, **kw):
        super().__init__(parent, bg=BG, **kw)
        self.kind = kind
        tk.Label(self, text=label + (" *" if required else ""),
                 bg=BG, fg=YELLOW if required else TEXT2,
                 font=FONT, width=22, anchor="w").pack(side="left")
        self.var = tk.StringVar()
        tk.Entry(self, textvariable=self.var, bg=BG3, fg=TEXT,
                 insertbackground=TEXT, font=FONT, relief="flat", width=width).pack(side="left", padx=(0, 6))
        styled_button(self, "Browse", self._browse, color=BLUE).pack(side="left")

    def _browse(self):
        p = (filedialog.askdirectory() if self.kind == "dir"
             else filedialog.askopenfilename() if self.kind == "file"
             else filedialog.asksaveasfilename())
        if p:
            self.var.set(p)

    def get(self):    return self.var.get().strip()
    def set(self, v): self.var.set(v)


class LabeledEntry(tk.Frame):
    def __init__(self, parent, label, width=28, required=False, **kw):
        super().__init__(parent, bg=BG, **kw)
        tk.Label(self, text=label + (" *" if required else ""),
                 bg=BG, fg=YELLOW if required else TEXT2,
                 font=FONT, width=22, anchor="w").pack(side="left")
        self.var = tk.StringVar()
        tk.Entry(self, textvariable=self.var, bg=BG3, fg=TEXT,
                 insertbackground=TEXT, font=FONT, relief="flat", width=width).pack(side="left")

    def get(self):    return self.var.get().strip()
    def set(self, v): self.var.set(v)


class CheckRow(tk.Frame):
    def __init__(self, parent, label, helptext="", **kw):
        super().__init__(parent, bg=BG, **kw)
        self.var = tk.BooleanVar()
        tk.Checkbutton(self, text=label, variable=self.var, bg=BG, fg=TEXT,
                       selectcolor=BG3, activebackground=BG, activeforeground=ACCENT,
                       font=FONT).pack(side="left")
        if helptext:
            tk.Label(self, text=helptext, bg=BG, fg=BG4,
                     font=("Segoe UI", 8)).pack(side="left", padx=6)

    def get(self):    return self.var.get()
    def set(self, v): self.var.set(v)

# ── Output Console ─────────────────────────────────────────────────────────────

class OutputConsole(tk.Frame):
    def __init__(self, parent, history_ref, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._proc    = None
        self._running = False
        self._history = history_ref
        self._build()

    def _build(self):
        bar = tk.Frame(self, bg=BG2)
        bar.pack(fill="x")
        tk.Label(bar, text="  Output Console", bg=BG2, fg=ACCENT, font=FONTH, pady=6).pack(side="left")
        self.status_lbl = tk.Label(bar, text="● Idle", bg=BG2, fg=TEXT2, font=FONT)
        self.status_lbl.pack(side="left", padx=14)
        styled_button(bar, "Stop",     self.stop,      color=RED).pack(side="right", padx=6,  pady=4)
        styled_button(bar, "Save Log", self._save_log, color=TEXT2).pack(side="right", padx=2, pady=4)
        styled_button(bar, "Clear",    self.clear,     color=TEXT2).pack(side="right", padx=2, pady=4)

        self.text = scrolledtext.ScrolledText(
            self, bg=BG2, fg=TEXT, font=MONO, relief="flat", wrap="word", state="disabled")
        self.text.pack(fill="both", expand=True, padx=4, pady=4)
        for tag, clr in [("info", TEXT), ("ok", GREEN), ("err", RED),
                         ("cmd", BLUE), ("head", YELLOW), ("dim", TEXT2)]:
            self.text.tag_config(tag, foreground=clr)

        prev = tk.Frame(self, bg=BG2)
        prev.pack(fill="x")
        tk.Label(prev, text="  CMD:", bg=BG2, fg=TEXT2, font=MONO).pack(side="left")
        self.cmd_var = tk.StringVar()
        tk.Entry(prev, textvariable=self.cmd_var, bg=BG2, fg=TEAL, font=MONO,
                 relief="flat", state="readonly", readonlybackground=BG2).pack(
            side="left", fill="x", expand=True, padx=4, pady=4)

    def write(self, msg, tag="info"):
        self.text.configure(state="normal")
        self.text.insert("end", msg, tag)
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def set_status(self, txt, color=TEXT2):
        self.status_lbl.configure(text=txt, fg=color)

    def set_cmd_preview(self, parts):
        self.cmd_var.set(shlex.join(parts))

    def stop(self):
        if self._proc and self._running:
            try:
                self._proc.terminate()
                self.write("\n⚠ Process terminated by user.\n", "err")
            except Exception:
                pass

    def _save_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", title="Save Log",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            with open(path, "w") as f:
                f.write(self.text.get("1.0", "end"))
            self.write(f"\nLog saved to: {path}\n", "ok")

    def run_command(self, cmd_parts):
        if self._running:
            messagebox.showwarning("Busy", "A process is already running.\nStop it first.")
            return
        # Auto-patch known broken imports in scripts before running
        if len(cmd_parts) > 1 and os.path.isfile(cmd_parts[1]):
            if patch_script_if_needed(cmd_parts[1]):
                self.write(f"⚠ Auto-patched bad import in {os.path.basename(cmd_parts[1])}\n", "err")
        self.set_cmd_preview(cmd_parts)
        threading.Thread(target=self._stream, args=(cmd_parts,), daemon=True).start()

    def _stream(self, cmd_parts):
        self._running = True
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.write(f"\n{'─'*68}\n", "dim")
        self.write(f"[{ts}]\n", "head")
        self.write(f"  {shlex.join(cmd_parts)}\n\n", "cmd")
        self.set_status("● Running", GREEN)
        self._history.append({"time": ts, "cmd": shlex.join(cmd_parts)})
        if len(self._history) > 100:
            self._history.pop(0)
        try:
            cwd = None
            if len(cmd_parts) > 1 and os.path.isfile(cmd_parts[1]):
                cwd = os.path.dirname(cmd_parts[1])

            # Build env with venv bin on PATH so shutil.which('nsz') etc. work inside scripts
            env = os.environ.copy()
            vp = _venv_python()
            if vp:
                venv_bin = os.path.dirname(vp)
                env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
                env["VIRTUAL_ENV"] = VENV_DIR

            self._proc = subprocess.Popen(
                cmd_parts,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True, bufsize=1, cwd=cwd,
                env=env)

            stderr_lines = []

            def _read_stderr():
                for line in self._proc.stderr:
                    stderr_lines.append(line)

            stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
            stderr_thread.start()

            for line in self._proc.stdout:
                tag = ("err" if any(w in line.lower() for w in
                                    ["error", "failed", "traceback", "exception", "critical"])
                       else "ok" if any(w in line.lower() for w in
                                        ["done", "success", "complete", "saved", "written", "finished"])
                       else "info")
                self.write(line, tag)

            self._proc.wait()
            stderr_thread.join(timeout=2)

            if stderr_lines:
                self.write("\n--- stderr ---\n", "dim")
                for line in stderr_lines:
                    self.write(line, "err")

            rc = self._proc.returncode
            if rc == 0:
                self.write(f"\n✔ Finished successfully (exit 0)\n", "ok")
                self.set_status("● Done", GREEN)
            else:
                self.write(f"\n✘ Exited with code {rc}\n", "err")
                self.set_status(f"● Error (exit {rc})", RED)
        except FileNotFoundError as e:
            self.write(f"\n✘ Could not launch: {e}\n", "err")
            self.set_status("● Error", RED)
        except Exception as e:
            self.write(f"\n✘ Unexpected error: {e}\n", "err")
            self.set_status("● Error", RED)
        finally:
            self._running = False
            self._proc    = None

# ── Tab: Global Config ─────────────────────────────────────────────────────────

class ConfigTab(ScrollableFrame):
    def __init__(self, parent, cfg, **kw):
        super().__init__(parent, **kw)
        self.cfg = cfg
        self._build()

    def _build(self):
        p = self.inner

        section_bar(p, "📁  Script Location")
        self.scripts_dir = PathRow(p, "Scripts Directory", kind="dir")
        self.scripts_dir.pack(anchor="w", padx=20, pady=4)

        section_bar(p, "🔧  Shared Tools & Keys")
        self.hactoolnet = PathRow(p, "hactoolnet Binary", kind="file")
        self.hactoolnet.pack(anchor="w", padx=20, pady=4)
        self.keys = PathRow(p, "Keys File (prod.keys)", kind="file")
        self.keys.pack(anchor="w", padx=20, pady=4)
        make_label(p, "  Point to prod.keys — hactoolnet will auto-find title.keys if it's in the same folder",
                   color=TEXT2, font=("Segoe UI", 8)).pack(anchor="w", padx=20)
        self.cert = PathRow(p, "Common Cert (.cert)", kind="file")
        self.cert.pack(anchor="w", padx=20, pady=4)

        section_bar(p, "📂  Default Directories")
        self.outdir = PathRow(p, "Default Output Dir", kind="dir")
        self.outdir.pack(anchor="w", padx=20, pady=4)

        section_bar(p, "📝  XML Metadata Defaults")
        self.dumper  = LabeledEntry(p, "Dumper")
        self.dumper.pack(anchor="w", padx=20, pady=4)
        self.project = LabeledEntry(p, "Project")
        self.project.pack(anchor="w", padx=20, pady=4)
        self.tool    = LabeledEntry(p, "Tool")
        self.tool.pack(anchor="w", padx=20, pady=4)
        self.section = LabeledEntry(p, "Section")
        self.section.pack(anchor="w", padx=20, pady=4)
        self.region  = LabeledEntry(p, "Region")
        self.region.pack(anchor="w", padx=20, pady=4)
        self.threads = LabeledEntry(p, "Thread Count", width=6)
        self.threads.pack(anchor="w", padx=20, pady=4)

        section_bar(p, "🐍  Python / Venv")
        vcard = tk.Frame(p, bg=BG3, padx=14, pady=10)
        vcard.pack(fill="x", padx=20, pady=(0, 6))
        tk.Label(vcard, text=f"Venv location:  {VENV_DIR}",
                 bg=BG3, fg=TEAL, font=MONO).pack(anchor="w")
        self.venv_status_lbl = tk.Label(vcard, text="", bg=BG3, fg=TEXT2, font=FONT)
        self.venv_status_lbl.pack(anchor="w", pady=(4, 0))
        self._refresh_venv_status()

        self.use_venv = CheckRow(p, "Use venv for all script runs  (recommended)",
                                 "  keeps deps isolated from system Python")
        self.use_venv.pack(anchor="w", padx=20, pady=4)

        bf = make_frame(p)
        bf.pack(anchor="w", padx=20, pady=16)
        styled_button(bf, "💾  Save Config",      self.save,   color=GREEN).pack(side="left", padx=(0, 8))
        styled_button(bf, "↺  Reset to Defaults", self._reset, color=YELLOW).pack(side="left")
        make_label(bf, "  Config: " + CONFIG_FILE, color=TEXT2,
                   font=("Segoe UI", 9)).pack(side="left", padx=12)

        self.load_from_cfg()

    def _refresh_venv_status(self):
        vp = _venv_python()
        if vp:
            self.venv_status_lbl.configure(text=f"✔ Venv found — {vp}", fg=GREEN)
        else:
            self.venv_status_lbl.configure(
                text="✘ No venv yet — use the Setup & Deps tab to create one", fg=RED)

    def load_from_cfg(self):
        self.scripts_dir.set(self.cfg["scripts_dir"])
        self.hactoolnet.set(self.cfg["hactoolnet_path"])
        self.keys.set(self.cfg["keys_path"])
        self.cert.set(self.cfg["cert_path"])
        self.outdir.set(self.cfg["default_outdir"])
        self.dumper.set(self.cfg["dumper"])
        self.project.set(self.cfg["project"])
        self.tool.set(self.cfg["tool"])
        self.section.set(self.cfg["section"])
        self.region.set(self.cfg["region"])
        self.threads.set(self.cfg["num_threads"])
        self.use_venv.set(self.cfg.get("use_venv", True))

    def save(self):
        self.cfg["scripts_dir"]     = self.scripts_dir.get()
        self.cfg["hactoolnet_path"] = self.hactoolnet.get()
        self.cfg["keys_path"]       = self.keys.get()
        self.cfg["cert_path"]       = self.cert.get()
        self.cfg["default_outdir"]  = self.outdir.get()
        self.cfg["dumper"]          = self.dumper.get()
        self.cfg["project"]         = self.project.get()
        self.cfg["tool"]            = self.tool.get()
        self.cfg["section"]         = self.section.get()
        self.cfg["region"]          = self.region.get()
        self.cfg["num_threads"]     = self.threads.get()
        self.cfg["use_venv"]        = self.use_venv.get()
        save_config(self.cfg)
        messagebox.showinfo("Saved", "Global config saved.")

    def _reset(self):
        if messagebox.askyesno("Reset", "Reset global config to defaults?"):
            for k, v in DEFAULTS.items():
                self.cfg[k] = v
            self.load_from_cfg()

    def get_globals(self):
        vp     = _venv_python()
        use    = self.use_venv.get()
        python = vp if (use and vp) else "python3"
        return {
            "scripts_dir": self.scripts_dir.get(),
            "python":      python,
            "hactoolnet":  self.hactoolnet.get(),
            "keys":        self.keys.get(),
            "cert":        self.cert.get(),
            "outdir":      self.outdir.get(),
            "dumper":      self.dumper.get(),
            "project":     self.project.get(),
            "tool":        self.tool.get(),
            "section":     self.section.get(),
            "region":      self.region.get(),
            "threads":     self.threads.get() or "4",
        }

# ── Shared helper ──────────────────────────────────────────────────────────────

def build_script_path(g, name):
    return os.path.join(g["scripts_dir"], name)

# ── Tab: NSP Generator ─────────────────────────────────────────────────────────

class NspTab(ScrollableFrame):
    SCRIPT = "xml_dataset_generator_nsp.py"

    def __init__(self, parent, cfg, get_globals, console, **kw):
        super().__init__(parent, **kw)
        self.cfg = cfg
        self.get_globals = get_globals
        self.console = console
        self._build()

    def _build(self):
        p = self.inner

        section_bar(p, "📦  NSP / NSZ Input")
        self.nspdir = PathRow(p, "NSP Input Directory *", kind="dir", required=True)
        self.nspdir.pack(anchor="w", padx=20, pady=4)
        self.outdir = PathRow(p, "Output Directory", kind="dir")
        self.outdir.pack(anchor="w", padx=20, pady=4)
        make_label(p, "  Leave blank to use Global Config output dir",
                   color=BG4, font=("Segoe UI", 8)).pack(anchor="w", padx=20)

        section_bar(p, "🔧  Tool Overrides  (leave blank to use Global Config)")
        self.hactoolnet = PathRow(p, "hactoolnet Binary", kind="file")
        self.hactoolnet.pack(anchor="w", padx=20, pady=4)
        self.keys    = PathRow(p, "Keys File", kind="file")
        self.keys.pack(anchor="w", padx=20, pady=4)
        self.threads = LabeledEntry(p, "Thread Count", width=6)
        self.threads.pack(anchor="w", padx=20, pady=4)

        section_bar(p, "📝  XML Metadata  (leave blank to use Global Config)")
        self.dumper       = LabeledEntry(p, "Dumper")
        self.dumper.pack(anchor="w", padx=20, pady=4)
        self.project      = LabeledEntry(p, "Project")
        self.project.pack(anchor="w", padx=20, pady=4)
        self.tool         = LabeledEntry(p, "Tool")
        self.tool.pack(anchor="w", padx=20, pady=4)
        self.section      = LabeledEntry(p, "Section")
        self.section.pack(anchor="w", padx=20, pady=4)
        self.region       = LabeledEntry(p, "Region")
        self.region.pack(anchor="w", padx=20, pady=4)
        self.dump_date    = LabeledEntry(p, "Dump Date (YYYY-MM-DD)", width=14)
        self.dump_date.pack(anchor="w", padx=20, pady=4)
        self.release_date = LabeledEntry(p, "Release Date (YYYY-MM-DD)", width=14)
        self.release_date.pack(anchor="w", padx=20, pady=4)

        section_bar(p, "⚙️  Flags")
        self.excl_nsp     = CheckRow(p, "Exclude NSP metadata",          "  --exclude-nsp")
        self.excl_nsp.pack(anchor="w", padx=20, pady=2)
        self.excl_tik     = CheckRow(p, "Exclude ticket metadata",        "  --exclude-tik")
        self.excl_tik.pack(anchor="w", padx=20, pady=2)
        self.excl_comment = CheckRow(p, "Exclude script comment",         "  --exclude-comment")
        self.excl_comment.pack(anchor="w", padx=20, pady=2)
        self.cdate_ddate  = CheckRow(p, "Use NSP file date as dump date", "  --nsp-cdate-as-ddate")
        self.cdate_ddate.pack(anchor="w", padx=20, pady=2)

        bf = make_frame(p)
        bf.pack(anchor="w", padx=20, pady=16)
        styled_button(bf, "▶  Run NSP Generator", self._run,     color=GREEN).pack(side="left", padx=(0, 8))
        styled_button(bf, "👁  Preview Command",   self._preview, color=BLUE).pack(side="left")

        self._restore()

    def _restore(self):
        self.nspdir.set(self.cfg.get("nsp_nspdir", ""))
        self.excl_nsp.set(self.cfg.get("nsp_exclude_nsp", False))
        self.excl_tik.set(self.cfg.get("nsp_exclude_tik", False))
        self.excl_comment.set(self.cfg.get("nsp_exclude_comment", False))
        self.cdate_ddate.set(self.cfg.get("nsp_cdate_as_ddate", False))
        self.dump_date.set(self.cfg.get("nsp_dump_date", ""))
        self.release_date.set(self.cfg.get("nsp_release_date", ""))

    def _build_cmd(self):
        g          = self.get_globals()
        cmd        = [g["python"], build_script_path(g, self.SCRIPT)]
        nspdir     = self.nspdir.get()
        outdir     = self.outdir.get()     or g["outdir"]
        hactoolnet = self.hactoolnet.get() or g["hactoolnet"]
        keys       = self.keys.get()       or g["keys"]
        threads    = self.threads.get()    or g["threads"]
        dumper     = self.dumper.get()     or g["dumper"]
        project    = self.project.get()    or g["project"]
        tool       = self.tool.get()       or g["tool"]
        section    = self.section.get()    or g["section"]
        region     = self.region.get()     or g["region"]
        if nspdir:      cmd += ["--nspdir",      nspdir]
        if hactoolnet:  cmd += ["--hactoolnet",  hactoolnet]
        if keys:        cmd += ["--keys",        keys]
        if outdir:      cmd += ["--outdir",      outdir]
        if dumper:      cmd += ["--dumper",      dumper]
        if project:     cmd += ["--project",     project]
        if tool:        cmd += ["--tool",        tool]
        if section:     cmd += ["--section",     section]
        if region:      cmd += ["--region",      region]
        if threads:     cmd += ["--num-threads", threads]
        dd = self.dump_date.get()
        rd = self.release_date.get()
        if dd: cmd += ["--dump-date",    dd]
        if rd: cmd += ["--release-date", rd]
        if self.excl_nsp.get():     cmd.append("--exclude-nsp")
        if self.excl_tik.get():     cmd.append("--exclude-tik")
        if self.excl_comment.get(): cmd.append("--exclude-comment")
        if self.cdate_ddate.get():  cmd.append("--nsp-cdate-as-ddate")
        return cmd

    def _preview(self):
        cmd = self._build_cmd()
        self.console.set_cmd_preview(cmd)
        messagebox.showinfo("Command Preview", shlex.join(cmd))

    def _run(self):
        if not self.nspdir.get():
            messagebox.showwarning("Missing", "NSP Input Directory is required.")
            return
        self.cfg["nsp_nspdir"]          = self.nspdir.get()
        self.cfg["nsp_exclude_nsp"]     = self.excl_nsp.get()
        self.cfg["nsp_exclude_tik"]     = self.excl_tik.get()
        self.cfg["nsp_exclude_comment"] = self.excl_comment.get()
        self.cfg["nsp_cdate_as_ddate"]  = self.cdate_ddate.get()
        self.cfg["nsp_dump_date"]       = self.dump_date.get()
        self.cfg["nsp_release_date"]    = self.release_date.get()
        save_config(self.cfg)
        self.console.run_command(self._build_cmd())

# ── Tab: Galaxy ────────────────────────────────────────────────────────────────

class GalaxyTab(ScrollableFrame):
    SCRIPT = "xml_dataset_generator_galaxy.py"

    def __init__(self, parent, cfg, get_globals, console, **kw):
        super().__init__(parent, **kw)
        self.cfg = cfg; self.get_globals = get_globals; self.console = console
        self._build()

    def _build(self):
        p = self.inner
        section_bar(p, "🌌  Galaxy CSV Input")
        self.csvdir  = PathRow(p, "CSV Directory", kind="dir")
        self.csvdir.pack(anchor="w", padx=20, pady=4)
        make_label(p, "  Comma-separated text files (default: ./all_hashes)",
                   color=TEXT2, font=("Segoe UI", 8)).pack(anchor="w", padx=20)
        self.httpdir = PathRow(p, "HTTP Headers Directory", kind="dir")
        self.httpdir.pack(anchor="w", padx=20, pady=4)
        make_label(p, "  HTTP response headers (default: ./head-requests)",
                   color=TEXT2, font=("Segoe UI", 8)).pack(anchor="w", padx=20)
        self.outdir  = PathRow(p, "Output Directory", kind="dir")
        self.outdir.pack(anchor="w", padx=20, pady=4)
        make_label(p, "  Leave blank to use Global Config output dir",
                   color=BG4, font=("Segoe UI", 8)).pack(anchor="w", padx=20)
        bf = make_frame(p)
        bf.pack(anchor="w", padx=20, pady=20)
        styled_button(bf, "▶  Run Galaxy Generator", self._run,     color=GREEN).pack(side="left", padx=(0, 8))
        styled_button(bf, "👁  Preview Command",      self._preview, color=BLUE).pack(side="left")
        self.csvdir.set(self.cfg.get("galaxy_csvdir", ""))
        self.httpdir.set(self.cfg.get("galaxy_httpdir", ""))

    def _build_cmd(self):
        g = self.get_globals()
        cmd = [g["python"], build_script_path(g, self.SCRIPT)]
        if self.csvdir.get():  cmd += ["--csvdir",  self.csvdir.get()]
        if self.httpdir.get(): cmd += ["--httpdir", self.httpdir.get()]
        outdir = self.outdir.get() or g["outdir"]
        if outdir: cmd += ["--outdir", outdir]
        return cmd

    def _preview(self):
        cmd = self._build_cmd()
        self.console.set_cmd_preview(cmd)
        messagebox.showinfo("Command Preview", shlex.join(cmd))

    def _run(self):
        self.cfg["galaxy_csvdir"]  = self.csvdir.get()
        self.cfg["galaxy_httpdir"] = self.httpdir.get()
        save_config(self.cfg)
        self.console.run_command(self._build_cmd())

# ── Tab: GodMode9 ──────────────────────────────────────────────────────────────

class Gm9Tab(ScrollableFrame):
    SCRIPT = "xml_dataset_generator_gm9.py"

    def __init__(self, parent, cfg, get_globals, console, **kw):
        super().__init__(parent, **kw)
        self.cfg = cfg; self.get_globals = get_globals; self.console = console
        self._build()

    def _build(self):
        p = self.inner
        section_bar(p, "🎮  GodMode9 Input")
        self.indir  = PathRow(p, "GM9 Dumps Directory", kind="dir")
        self.indir.pack(anchor="w", padx=20, pady=4)
        self.outdir = PathRow(p, "Output Directory", kind="dir")
        self.outdir.pack(anchor="w", padx=20, pady=4)
        make_label(p, "  Leave blank to use Global Config output dir",
                   color=BG4, font=("Segoe UI", 8)).pack(anchor="w", padx=20)
        section_bar(p, "📝  Required Metadata")
        self.section = LabeledEntry(p, "Section *", required=True)
        self.section.pack(anchor="w", padx=20, pady=4)
        self.dumper  = LabeledEntry(p, "Dumper *",  required=True)
        self.dumper.pack(anchor="w", padx=20, pady=4)
        self.project = LabeledEntry(p, "Project *", required=True)
        self.project.pack(anchor="w", padx=20, pady=4)
        make_label(p, "  * Required directly by this script (cannot be empty)",
                   color=YELLOW, font=("Segoe UI", 8)).pack(anchor="w", padx=20, pady=(0, 4))
        bf = make_frame(p)
        bf.pack(anchor="w", padx=20, pady=16)
        styled_button(bf, "▶  Run GM9 Generator", self._run,     color=GREEN).pack(side="left", padx=(0, 8))
        styled_button(bf, "👁  Preview Command",   self._preview, color=BLUE).pack(side="left")
        self.indir.set(self.cfg.get("gm9_indir", ""))
        g = self.get_globals()
        self.section.set(g["section"]); self.dumper.set(g["dumper"]); self.project.set(g["project"])

    def _build_cmd(self):
        g = self.get_globals()
        cmd = [g["python"], build_script_path(g, self.SCRIPT)]
        if self.indir.get():   cmd += ["--indir",   self.indir.get()]
        outdir = self.outdir.get() or g["outdir"]
        if outdir:             cmd += ["--outdir",  outdir]
        if self.section.get(): cmd += ["--section", self.section.get()]
        if self.dumper.get():  cmd += ["--dumper",  self.dumper.get()]
        if self.project.get(): cmd += ["--project", self.project.get()]
        return cmd

    def _preview(self):
        cmd = self._build_cmd(); self.console.set_cmd_preview(cmd)
        messagebox.showinfo("Command Preview", shlex.join(cmd))

    def _run(self):
        if not self.section.get() or not self.dumper.get() or not self.project.get():
            messagebox.showwarning("Missing", "Section, Dumper, and Project are required.")
            return
        self.cfg["gm9_indir"] = self.indir.get()
        save_config(self.cfg)
        self.console.run_command(self._build_cmd())

# ── Tab: Nold ──────────────────────────────────────────────────────────────────

class NoldTab(ScrollableFrame):
    SCRIPT = "xml_dataset_generator_nold.py"

    def __init__(self, parent, cfg, get_globals, console, **kw):
        super().__init__(parent, **kw)
        self.cfg = cfg; self.get_globals = get_globals; self.console = console
        self._build()

    def _build(self):
        p = self.inner
        section_bar(p, "🎮  Wii CDN Dump Input  (Nold)")
        self.indir  = PathRow(p, "Wii CDN Dump Directory", kind="dir")
        self.indir.pack(anchor="w", padx=20, pady=4)
        self.outdir = PathRow(p, "Output Directory", kind="dir")
        self.outdir.pack(anchor="w", padx=20, pady=4)
        make_label(p, "  Leave blank to use Global Config output dir",
                   color=BG4, font=("Segoe UI", 8)).pack(anchor="w", padx=20)
        bf = make_frame(p)
        bf.pack(anchor="w", padx=20, pady=20)
        styled_button(bf, "▶  Run Nold Generator", self._run,     color=GREEN).pack(side="left", padx=(0, 8))
        styled_button(bf, "👁  Preview Command",    self._preview, color=BLUE).pack(side="left")
        self.indir.set(self.cfg.get("nold_indir", ""))

    def _build_cmd(self):
        g = self.get_globals()
        cmd = [g["python"], build_script_path(g, self.SCRIPT)]
        if self.indir.get():  cmd += ["--indir",  self.indir.get()]
        outdir = self.outdir.get() or g["outdir"]
        if outdir: cmd += ["--outdir", outdir]
        return cmd

    def _preview(self):
        cmd = self._build_cmd(); self.console.set_cmd_preview(cmd)
        messagebox.showinfo("Command Preview", shlex.join(cmd))

    def _run(self):
        self.cfg["nold_indir"] = self.indir.get()
        save_config(self.cfg); self.console.run_command(self._build_cmd())

# ── Tab: Anonymous ─────────────────────────────────────────────────────────────

class AnonTab(ScrollableFrame):
    SCRIPT = "xml_dataset_generator_anonymous.py"

    def __init__(self, parent, cfg, get_globals, console, **kw):
        super().__init__(parent, **kw)
        self.cfg = cfg; self.get_globals = get_globals; self.console = console
        self._build()

    def _build(self):
        p = self.inner
        section_bar(p, "💿  Wii U CDN Dump Input  (Anonymous)")
        self.input  = PathRow(p, "Wii U CDN Dump File *", kind="file", required=True)
        self.input.pack(anchor="w", padx=20, pady=4)
        make_label(p, "  Path to the .txt file from Wii U CDN dump",
                   color=TEXT2, font=("Segoe UI", 8)).pack(anchor="w", padx=20)
        self.outdir = PathRow(p, "Output Directory", kind="dir")
        self.outdir.pack(anchor="w", padx=20, pady=4)
        make_label(p, "  Leave blank to use Global Config output dir",
                   color=BG4, font=("Segoe UI", 8)).pack(anchor="w", padx=20)
        bf = make_frame(p)
        bf.pack(anchor="w", padx=20, pady=20)
        styled_button(bf, "▶  Run Anonymous Generator", self._run,     color=GREEN).pack(side="left", padx=(0, 8))
        styled_button(bf, "👁  Preview Command",         self._preview, color=BLUE).pack(side="left")
        self.input.set(self.cfg.get("anon_input", ""))

    def _build_cmd(self):
        g = self.get_globals()
        cmd = [g["python"], build_script_path(g, self.SCRIPT)]
        if self.input.get():  cmd += ["--input",  self.input.get()]
        outdir = self.outdir.get() or g["outdir"]
        if outdir: cmd += ["--outdir", outdir]
        return cmd

    def _preview(self):
        cmd = self._build_cmd(); self.console.set_cmd_preview(cmd)
        messagebox.showinfo("Command Preview", shlex.join(cmd))

    def _run(self):
        if not self.input.get():
            messagebox.showwarning("Missing", "Wii U CDN Dump File is required.")
            return
        self.cfg["anon_input"] = self.input.get()
        save_config(self.cfg); self.console.run_command(self._build_cmd())

# ── Tab: cdn2nsp ───────────────────────────────────────────────────────────────

class CdnTab(ScrollableFrame):
    SCRIPT = "cdn2nsp.py"

    def __init__(self, parent, cfg, get_globals, console, **kw):
        super().__init__(parent, **kw)
        self.cfg = cfg; self.get_globals = get_globals; self.console = console
        self._build()

    def _build(self):
        p = self.inner
        section_bar(p, "📡  CDN to NSP Conversion")
        self.cdndir = PathRow(p, "CDN Data Directory *", kind="dir", required=True)
        self.cdndir.pack(anchor="w", padx=20, pady=4)
        make_label(p, "  Extracted CDN data directory (processed recursively)",
                   color=TEXT2, font=("Segoe UI", 8)).pack(anchor="w", padx=20)
        self.outdir = PathRow(p, "Output Directory", kind="dir")
        self.outdir.pack(anchor="w", padx=20, pady=4)

        section_bar(p, "🔧  Tool Overrides  (leave blank to use Global Config)")
        self.hactoolnet = PathRow(p, "hactoolnet Binary", kind="file")
        self.hactoolnet.pack(anchor="w", padx=20, pady=4)
        self.keys    = PathRow(p, "Keys File", kind="file")
        self.keys.pack(anchor="w", padx=20, pady=4)
        self.cert    = PathRow(p, "Common Cert File", kind="file")
        self.cert.pack(anchor="w", padx=20, pady=4)
        self.threads = LabeledEntry(p, "Thread Count", width=6)
        self.threads.pack(anchor="w", padx=20, pady=4)

        section_bar(p, "⚙️  Flags")
        self.process_nsp = CheckRow(p, "Process NSP/NSZ files",
                                    "  Unpack & repack NSP/NSZ in CDN dir (requires nsz)")
        self.process_nsp.pack(anchor="w", padx=20, pady=2)
        self.keep_deltas = CheckRow(p, "Keep Delta Fragments",
                                    "  Write Delta Fragment NCAs to output NSPs")
        self.keep_deltas.pack(anchor="w", padx=20, pady=2)

        bf = make_frame(p)
        bf.pack(anchor="w", padx=20, pady=16)
        styled_button(bf, "▶  Run cdn2nsp",     self._run,     color=GREEN).pack(side="left", padx=(0, 8))
        styled_button(bf, "👁  Preview Command", self._preview, color=BLUE).pack(side="left")

        self.cdndir.set(self.cfg.get("cdn_cdndir", ""))
        self.process_nsp.set(self.cfg.get("cdn_process_nsp", False))
        self.keep_deltas.set(self.cfg.get("cdn_keep_deltas", False))

    def _build_cmd(self):
        g = self.get_globals()
        cmd = [g["python"], build_script_path(g, self.SCRIPT)]
        cdndir     = self.cdndir.get()
        outdir     = self.outdir.get()     or g["outdir"]
        hactoolnet = self.hactoolnet.get() or g["hactoolnet"]
        keys       = self.keys.get()       or g["keys"]
        cert       = self.cert.get()       or g["cert"]
        threads    = self.threads.get()    or g["threads"]
        if cdndir:     cmd += ["--cdndir",      cdndir]
        if hactoolnet: cmd += ["--hactoolnet",  hactoolnet]
        if keys:       cmd += ["--keys",        keys]
        if cert:       cmd += ["--cert",        cert]
        if outdir:     cmd += ["--outdir",      outdir]
        if threads:    cmd += ["--num-threads", threads]
        if self.process_nsp.get():  cmd.append("--process-nsp")
        if self.keep_deltas.get():  cmd.append("--keep-deltas")
        return cmd

    def _preview(self):
        cmd = self._build_cmd(); self.console.set_cmd_preview(cmd)
        messagebox.showinfo("Command Preview", shlex.join(cmd))

    def _run(self):
        if not self.cdndir.get():
            messagebox.showwarning("Missing", "CDN Data Directory is required.")
            return
        self.cfg["cdn_cdndir"]      = self.cdndir.get()
        self.cfg["cdn_process_nsp"] = self.process_nsp.get()
        self.cfg["cdn_keep_deltas"] = self.keep_deltas.get()
        save_config(self.cfg); self.console.run_command(self._build_cmd())

# ── Tab: Setup & Dependencies ──────────────────────────────────────────────────

REQUIRED_PACKAGES = [
    ("kaitaistruct", "kaitaistruct==0.10", "Required by all xml_dataset_generator_*.py scripts"),
    ("nsz",          "nsz==4.5.0",         "Required by cdn2nsp.py --process-nsp flag"),
    ("psutil",       "psutil==5.9.6",      "Required by cdn2nsp.py (process management)"),
    ("rsa",          "rsa",                "Required by cdn2nsp.py (RSA signature validation)"),
]

class DepsTab(ScrollableFrame):
    def __init__(self, parent, cfg, console, cfg_tab_ref, **kw):
        super().__init__(parent, **kw)
        self.cfg         = cfg
        self.console     = console
        self.cfg_tab_ref = cfg_tab_ref
        self._rows       = {}
        self._build()

    def _build(self):
        p = self.inner

        # ── Venv card ─────────────────────────────────────────────────────────
        section_bar(p, "🐍  Virtual Environment  (Recommended First-Time Setup)")

        vcard = tk.Frame(p, bg=BG3, padx=16, pady=12)
        vcard.pack(fill="x", padx=20, pady=(0, 8))

        tk.Label(vcard, text=f"Venv path:  {VENV_DIR}",
                 bg=BG3, fg=TEAL, font=MONO).pack(anchor="w")

        self.venv_lbl = tk.Label(vcard, text="Checking…", bg=BG3, fg=TEXT2, font=FONTB)
        self.venv_lbl.pack(anchor="w", pady=(6, 2))

        self.venv_pip_lbl = tk.Label(vcard, text="", bg=BG3, fg=TEXT2, font=MONO)
        self.venv_pip_lbl.pack(anchor="w")

        # Quick-start instructions
        qs = tk.Frame(vcard, bg=BG3)
        qs.pack(anchor="w", pady=(10, 6))
        tk.Label(qs, text="Quick Start:", bg=BG3, fg=YELLOW, font=FONTB).grid(row=0, column=0, sticky="w", pady=2)
        for i, txt in enumerate([
            "1.  Click  ⚡ Create Venv  to create an isolated Python environment",
            "2.  Click  ⬇ Install All Packages  to install all needed packages into the venv",
            "3.  Click  🔀 Init Git Repo  so the scripts can read their own revision info",
            "4.  Make sure  'Use venv'  is checked in Global Config",
            "5.  You're ready — run any script from its tab",
        ], 1):
            tk.Label(qs, text=txt, bg=BG3, fg=TEXT2, font=FONT).grid(row=i, column=0, sticky="w", padx=(16, 0))

        vf = tk.Frame(vcard, bg=BG3)
        vf.pack(anchor="w", pady=(10, 0))
        self.create_btn = styled_button(vf, "⚡ Create Venv",      self._create_venv,  color=ORANGE)
        self.create_btn.pack(side="left", padx=(0, 8))
        styled_button(vf, "⬇ Install All Packages", self._install_req, color=GREEN).pack(side="left", padx=(0, 8))
        styled_button(vf, "🗑  Delete Venv",          self._delete_venv, color=RED).pack(side="left")

        vf2 = tk.Frame(vcard, bg=BG3)
        vf2.pack(anchor="w", pady=(8, 0))
        self.git_btn = styled_button(vf2, "🔀 Init Git Repo", self._init_git, color=TEAL)
        self.git_btn.pack(side="left", padx=(0, 8))
        self.git_lbl = tk.Label(vf2, text="", bg=BG3, fg=TEXT2, font=FONT)
        self.git_lbl.pack(side="left")
        self._refresh_git_status()

        # ── Package grid ──────────────────────────────────────────────────────
        section_bar(p, "📦  Package Status")
        make_label(p, "  Checks inside venv when active, otherwise system Python",
                   color=TEXT2, font=("Segoe UI", 8)).pack(anchor="w", padx=20, pady=(0, 6))

        grid = tk.Frame(p, bg=BG)
        grid.pack(fill="x", padx=20, pady=4)

        for col, (txt, w) in enumerate([("Package", 16), ("Spec", 22), ("Status", 16), ("Action", 10), ("Notes", 44)]):
            tk.Label(grid, text=txt, bg=BG2, fg=ACCENT, font=FONTB,
                     width=w, anchor="w", padx=6, pady=4).grid(
                row=0, column=col, sticky="w", padx=2, pady=2)

        for i, (pkg, spec, notes) in enumerate(REQUIRED_PACKAGES, 1):
            tk.Label(grid, text=pkg,  bg=BG, fg=TEXT,  font=MONO, width=16, anchor="w", padx=6).grid(row=i, column=0, sticky="w", padx=2, pady=3)
            tk.Label(grid, text=spec, bg=BG, fg=TEXT2, font=MONO, width=22, anchor="w", padx=6).grid(row=i, column=1, sticky="w", padx=2, pady=3)
            slbl = tk.Label(grid, text="…", bg=BG, fg=TEXT2, font=FONTB, width=16, anchor="w", padx=6)
            slbl.grid(row=i, column=2, sticky="w", padx=2, pady=3)
            btn = styled_button(grid, "Install", lambda s=spec, pk=pkg: self._install_one(s, pk), color=YELLOW)
            btn.grid(row=i, column=3, sticky="w", padx=4, pady=3)
            tk.Label(grid, text=notes, bg=BG, fg=TEXT2, font=("Segoe UI", 8),
                     anchor="w", wraplength=360).grid(row=i, column=4, sticky="w", padx=6, pady=3)
            self._rows[pkg] = {"status": slbl, "btn": btn}

        bf = make_frame(p)
        bf.pack(anchor="w", padx=20, pady=16)
        styled_button(bf, "🔍 Check All",          self.check_all,    color=BLUE).pack(side="left", padx=(0, 8))
        styled_button(bf, "⬇ Install All Missing", self._install_all, color=GREEN).pack(side="left")

        self._refresh_venv_ui()
        self._refresh_git_status()

    # ── Venv helpers ──────────────────────────────────────────────────────────

    def _refresh_venv_ui(self):
        vp = _venv_python()
        if vp:
            self.venv_lbl.configure(text=f"✔ Venv active — {vp}", fg=GREEN)
            self.create_btn.configure(text="♻ Recreate Venv")
            try:
                r = subprocess.run([vp, "-m", "pip", "list", "--format=columns"],
                                   capture_output=True, text=True, timeout=8)
                count = max(0, len(r.stdout.strip().splitlines()) - 2)
                self.venv_pip_lbl.configure(text=f"  {count} packages installed in venv", fg=TEAL)
            except Exception:
                self.venv_pip_lbl.configure(text="", fg=TEXT2)
        else:
            self.venv_lbl.configure(text="✘ No venv found — click  ⚡ Create Venv  to get started", fg=RED)
            self.create_btn.configure(text="⚡ Create Venv")
            self.venv_pip_lbl.configure(text="", fg=TEXT2)
        self.check_all()
        if self.cfg_tab_ref:
            self.cfg_tab_ref._refresh_venv_status()

    def _refresh_git_status(self):
        scripts_dir = self.cfg.get("scripts_dir", SCRIPT_DIR)
        git_dir = os.path.join(scripts_dir, ".git")
        if os.path.isdir(git_dir):
            # Check it has at least one commit
            r = subprocess.run(["git", "-C", scripts_dir, "rev-parse", "--short", "HEAD"],
                               capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                self.git_lbl.configure(text=f"✔ Git repo ready  ({r.stdout.strip()})", fg=GREEN)
                self.git_btn.configure(text="🔀 Re-init Git Repo")
                return
        self.git_lbl.configure(text="✘ No git repo — scripts will fail without it", fg=RED)
        self.git_btn.configure(text="🔀 Init Git Repo")

    def _init_git(self):
        scripts_dir = self.cfg.get("scripts_dir", SCRIPT_DIR)
        def _do():
            self.console.write(f"\n{'─'*60}\n", "dim")
            self.console.write(f"Initializing git repo in: {scripts_dir}\n", "head")
            try:
                # init
                r = subprocess.run(["git", "-C", scripts_dir, "init"],
                                   capture_output=True, text=True)
                self.console.write(r.stdout or r.stderr, "info")
                # stage everything
                r = subprocess.run(["git", "-C", scripts_dir, "add", "-A"],
                                   capture_output=True, text=True)
                # commit — skip if nothing to commit
                r = subprocess.run(
                    ["git", "-C", scripts_dir, "commit", "--allow-empty",
                     "-m", "init", "--author", "DoM GUI <dom@gui>"],
                    capture_output=True, text=True)
                self.console.write(r.stdout or r.stderr, "info")
                self.console.write("✔ Git repo ready.\n", "ok")
            except FileNotFoundError:
                self.console.write("✘ git not found — please install git.\n", "err")
            except Exception as e:
                self.console.write(f"✘ {e}\n", "err")
            self.after(0, self._refresh_git_status)
        threading.Thread(target=_do, daemon=True).start()

    def _create_venv(self):
        def _do():
            self.console.write(f"\n{'─'*60}\n", "dim")
            self.console.write(f"Creating venv at {VENV_DIR} …\n", "head")
            self.console.set_status("● Creating venv…", YELLOW)
            try:
                venv.create(VENV_DIR, with_pip=True, clear=True)
                self.console.write("✔ Venv created successfully.\n", "ok")
                self.console.set_status("● Done", GREEN)
            except Exception as e:
                self.console.write(f"✘ Failed: {e}\n", "err")
                self.console.set_status("● Error", RED)
            self.after(0, self._refresh_venv_ui)
        threading.Thread(target=_do, daemon=True).start()

    def _delete_venv(self):
        if not os.path.exists(VENV_DIR):
            messagebox.showinfo("No Venv", "No venv found to delete."); return
        if messagebox.askyesno("Delete Venv",
                               f"Delete the venv at:\n{VENV_DIR}\n\nThis cannot be undone."):
            import shutil
            shutil.rmtree(VENV_DIR, ignore_errors=True)
            self.console.write(f"\n🗑 Venv deleted.\n", "err")
            self.after(0, self._refresh_venv_ui)

    def _install_req(self):
        vp = _venv_python()
        if not vp:
            if messagebox.askyesno("No Venv",
                                   "No venv found.\nCreate one automatically and then install?"):
                def _do():
                    self.console.write(f"\nCreating venv at {VENV_DIR} …\n", "head")
                    try:
                        venv.create(VENV_DIR, with_pip=True, clear=True)
                        self.console.write("✔ Venv created.\n", "ok")
                    except Exception as e:
                        self.console.write(f"✘ {e}\n", "err"); return
                    self.after(0, self._install_req)
                threading.Thread(target=_do, daemon=True).start()
            return
        req = os.path.join(self.cfg.get("scripts_dir", SCRIPT_DIR), "requirements.txt")
        specs = [spec for _, spec, _ in REQUIRED_PACKAGES]
        if os.path.exists(req):
            self.console.write(f"\nFound requirements.txt: {req}\n", "head")
            self.console.run_command([vp, "-m", "pip", "install", "-r", req])
        else:
            # No requirements.txt — install all known packages directly
            self.console.write(
                "\nNo requirements.txt found — installing known packages directly:\n"
                "  " + "  ".join(specs) + "\n", "head")
            self.console.run_command([vp, "-m", "pip", "install"] + specs)
        self.after(10000, self._refresh_venv_ui)

    # ── Package check/install ─────────────────────────────────────────────────

    def _get_python(self):
        vp  = _venv_python()
        use = self.cfg.get("use_venv", True)
        return vp if (use and vp) else "python3"

    def _check_pkg(self, python, pkg):
        try:
            r = subprocess.run([python, "-c", f"import {pkg}"],
                               capture_output=True, timeout=6)
            return r.returncode == 0
        except Exception:
            return False

    def check_all(self):
        python = self._get_python()
        for pkg, _, _ in REQUIRED_PACKAGES:
            ok  = self._check_pkg(python, pkg)
            row = self._rows[pkg]
            if ok:
                row["status"].configure(text="✔ Installed", fg=GREEN)
                row["btn"].configure(state="disabled", fg=BG4)
            else:
                row["status"].configure(text="✘ Missing", fg=RED)
                row["btn"].configure(state="normal", fg=YELLOW)

    def _install_one(self, spec, pkg):
        self._rows[pkg]["status"].configure(text="⏳ Installing…", fg=YELLOW)
        self.console.run_command([self._get_python(), "-m", "pip", "install", spec])
        self.after(6000, self._refresh_venv_ui)

    def _install_all(self):
        python  = self._get_python()
        missing = [spec for pkg, spec, _ in REQUIRED_PACKAGES if not self._check_pkg(python, pkg)]
        if not missing:
            messagebox.showinfo("All Good", "All packages are already installed!"); return
        self.console.run_command([python, "-m", "pip", "install"] + missing)
        self.after(10000, self._refresh_venv_ui)

# ── Tab: History ───────────────────────────────────────────────────────────────

class HistoryTab(tk.Frame):
    def __init__(self, parent, cfg, **kw):
        super().__init__(parent, bg=BG, **kw)
        self.cfg = cfg
        self._build()

    def _build(self):
        bar = tk.Frame(self, bg=BG2)
        bar.pack(fill="x")
        tk.Label(bar, text="  Run History", bg=BG2, fg=ACCENT, font=FONTH, pady=6).pack(side="left")
        styled_button(bar, "Clear History", self._clear,  color=RED).pack(side="right", padx=8,  pady=4)
        styled_button(bar, "Refresh",       self.refresh, color=TEXT2).pack(side="right", padx=2, pady=4)
        self.text = scrolledtext.ScrolledText(
            self, bg=BG2, fg=TEXT, font=MONO, relief="flat", wrap="word", state="disabled")
        self.text.pack(fill="both", expand=True, padx=4, pady=4)
        self.text.tag_config("head", foreground=YELLOW)
        self.text.tag_config("dim",  foreground=TEXT2)
        self.refresh()

    def refresh(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        history = self.cfg.get("run_history", [])
        if not history:
            self.text.insert("end", "No runs recorded yet.\n", "dim")
        else:
            for e in reversed(history):
                self.text.insert("end", f"[{e.get('time','?')}]\n", "head")
                self.text.insert("end", f"  {e.get('cmd','')}\n\n")
        self.text.configure(state="disabled")

    def _clear(self):
        if messagebox.askyesno("Clear History", "Clear all run history?"):
            self.cfg["run_history"] = []
            save_config(self.cfg); self.refresh()

# ── Main Application ───────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DoM XML Dataset Generator GUI")
        self.geometry("1120x840")
        self.minsize(900, 650)
        self.configure(bg=BG)
        self._apply_style()
        self.cfg = load_config()
        self._build()

    def _apply_style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TNotebook",     background=BG2, borderwidth=0)
        s.configure("TNotebook.Tab", background=BG3, foreground=TEXT2,
                    font=FONTB, padding=(14, 6), borderwidth=0)
        s.map("TNotebook.Tab",
              background=[("selected", BG), ("active", BG4)],
              foreground=[("selected", ACCENT), ("active", TEXT)])
        s.configure("TScrollbar", background=BG3, troughcolor=BG2,
                    borderwidth=0, arrowcolor=TEXT2)
        s.map("TScrollbar", background=[("active", BG4)])

    def _build(self):
        hdr = tk.Frame(self, bg=BG2)
        hdr.pack(fill="x")
        tk.Label(hdr, text="  ⚡ DoM XML Dataset Generator", bg=BG2, fg=ACCENT,
                 font=("Segoe UI", 14, "bold"), pady=10).pack(side="left")
        tk.Label(hdr, text="custom-hactoolnet branch  •  by DarkMatterCore",
                 bg=BG2, fg=TEXT2, font=("Segoe UI", 9)).pack(side="left", padx=14)
        self.venv_hdr = tk.Label(hdr, text="", bg=BG2, fg=TEXT2, font=("Segoe UI", 9))
        self.venv_hdr.pack(side="right", padx=16)
        self._update_venv_hdr()

        pane = tk.PanedWindow(self, orient="vertical", bg=BG2,
                              sashwidth=7, sashrelief="flat", sashpad=2)
        pane.pack(fill="both", expand=True)

        nb = ttk.Notebook(pane)
        pane.add(nb, minsize=340)

        self.console = OutputConsole(pane, self.cfg.setdefault("run_history", []))
        pane.add(self.console, minsize=180)

        self.cfg_tab  = ConfigTab(nb, self.cfg)
        nb.add(self.cfg_tab, text="⚙ Global Config")

        def gg(): return self.cfg_tab.get_globals()

        self.nsp_tab  = NspTab(nb,  self.cfg, gg, self.console)
        nb.add(self.nsp_tab, text="📦 NSP")

        self.gal_tab  = GalaxyTab(nb, self.cfg, gg, self.console)
        nb.add(self.gal_tab, text="🌌 Galaxy")

        self.gm9_tab  = Gm9Tab(nb, self.cfg, gg, self.console)
        nb.add(self.gm9_tab, text="🎮 GodMode9")

        self.nold_tab = NoldTab(nb, self.cfg, gg, self.console)
        nb.add(self.nold_tab, text="💽 Nold (Wii)")

        self.anon_tab = AnonTab(nb, self.cfg, gg, self.console)
        nb.add(self.anon_tab, text="💿 Anonymous (WiiU)")

        self.cdn_tab  = CdnTab(nb, self.cfg, gg, self.console)
        nb.add(self.cdn_tab, text="📡 cdn2nsp")

        self.deps_tab = DepsTab(nb, self.cfg, self.console, self.cfg_tab)
        nb.add(self.deps_tab, text="🛠 Setup & Deps")

        self.hist_tab = HistoryTab(nb, self.cfg)
        nb.add(self.hist_tab, text="📋 History")

        nb.bind("<<NotebookTabChanged>>", self._on_tab_change)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        sb = tk.Frame(self, bg=BG2, pady=2)
        sb.pack(fill="x", side="bottom")
        tk.Label(sb, text=f"  Config: {CONFIG_FILE}",
                 bg=BG2, fg=BG4, font=("Segoe UI", 8)).pack(side="left")
        tk.Label(sb, text=f"  Venv: {VENV_DIR}",
                 bg=BG2, fg=BG4, font=("Segoe UI", 8)).pack(side="left", padx=20)

    def _collect_all_state(self):
        """Pull current field values from every tab into self.cfg and write to disk."""
        # Global Config tab
        self.cfg["scripts_dir"]     = self.cfg_tab.scripts_dir.get()
        self.cfg["hactoolnet_path"] = self.cfg_tab.hactoolnet.get()
        self.cfg["keys_path"]       = self.cfg_tab.keys.get()
        self.cfg["cert_path"]       = self.cfg_tab.cert.get()
        self.cfg["default_outdir"]  = self.cfg_tab.outdir.get()
        self.cfg["dumper"]          = self.cfg_tab.dumper.get()
        self.cfg["project"]         = self.cfg_tab.project.get()
        self.cfg["tool"]            = self.cfg_tab.tool.get()
        self.cfg["section"]         = self.cfg_tab.section.get()
        self.cfg["region"]          = self.cfg_tab.region.get()
        self.cfg["num_threads"]     = self.cfg_tab.threads.get()
        self.cfg["use_venv"]        = self.cfg_tab.use_venv.get()
        # NSP tab
        self.cfg["nsp_nspdir"]          = self.nsp_tab.nspdir.get()
        self.cfg["nsp_exclude_nsp"]     = self.nsp_tab.excl_nsp.get()
        self.cfg["nsp_exclude_tik"]     = self.nsp_tab.excl_tik.get()
        self.cfg["nsp_exclude_comment"] = self.nsp_tab.excl_comment.get()
        self.cfg["nsp_cdate_as_ddate"]  = self.nsp_tab.cdate_ddate.get()
        self.cfg["nsp_dump_date"]       = self.nsp_tab.dump_date.get()
        self.cfg["nsp_release_date"]    = self.nsp_tab.release_date.get()
        # Galaxy tab
        self.cfg["galaxy_csvdir"]  = self.gal_tab.csvdir.get()
        self.cfg["galaxy_httpdir"] = self.gal_tab.httpdir.get()
        # GodMode9 tab
        self.cfg["gm9_indir"] = self.gm9_tab.indir.get()
        # Nold tab
        self.cfg["nold_indir"] = self.nold_tab.indir.get()
        # Anonymous tab
        self.cfg["anon_input"] = self.anon_tab.input.get()
        # CDN tab
        self.cfg["cdn_cdndir"]      = self.cdn_tab.cdndir.get()
        self.cfg["cdn_process_nsp"] = self.cdn_tab.process_nsp.get()
        self.cfg["cdn_keep_deltas"] = self.cdn_tab.keep_deltas.get()
        save_config(self.cfg)

    def _on_close(self):
        self._collect_all_state()
        self.destroy()

    def _update_venv_hdr(self):
        vp = _venv_python()
        if vp:
            self.venv_hdr.configure(text="🐍 venv ✔", fg=GREEN)
        else:
            self.venv_hdr.configure(text="🐍 no venv — see 🛠 Setup & Deps", fg=YELLOW)

    def _on_tab_change(self, event):
        nb  = event.widget
        tab = nb.tab(nb.select(), "text")
        if "History" in tab:
            self.hist_tab.refresh()
        if "Setup" in tab or "Deps" in tab:
            self.deps_tab._refresh_venv_ui()
        self._update_venv_hdr()


if __name__ == "__main__":
    app = App()
    app.mainloop()
