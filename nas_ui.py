#!/usr/bin/env python3
import os, json, threading, subprocess, tkinter as tk
import customtkinter as ctk

ctk.set_appearance_mode("dark")

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "this.json")
CACHE_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nas_cache.json")

BG    = "#111111"
BG2   = "#1a1a1a"
BG3   = "#222222"
WHITE = "#ffffff"
GRAY  = "#888888"
BLUE  = "#2196F3"
GREEN = "#4CAF50"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f).get("GlobalSettings", {})
    return {}

def browse_folder(title="Chọn folder"):
    try:
        r = subprocess.run(
            ["zenity", "--file-selection", "--directory",
             "--filename=/home/mava/", f"--title={title}"],
            capture_output=True, text=True)
        return r.stdout.strip()
    except: return ""

def _build_raw_index(nas_paths, log_fn=None):
    import concurrent.futures, threading
    raw = {}
    lock = threading.Lock()

    def _scan_one(nas_dir):
        if not os.path.exists(nas_dir):
            if log_fn: log_fn(f"⚠️ NAS không tồn tại: {nas_dir}")
            return
        if log_fn: log_fn(f"📡 Quét: {nas_dir}...")
        proc = subprocess.Popen(["find", nas_dir, "-type", "f"],
                                stdout=subprocess.PIPE, text=True)
        local = {}
        c = 0
        for line in proc.stdout:
            path = line.strip()
            if path.lower().endswith(('.tmp', '.crdownload', '.txt')): continue
            fname = os.path.splitext(os.path.basename(path))[0].lower()
            local[fname] = path
            c += 1
            if c % 5000 == 0 and log_fn:
                log_fn(f"  [{os.path.basename(nas_dir)}] {c:,} file...")
        proc.wait()
        with lock:
            raw.update(local)
        if log_fn: log_fn(f"  ✅ {os.path.basename(nas_dir)}: {c:,} file")

    with concurrent.futures.ThreadPoolExecutor() as ex:
        list(ex.map(_scan_one, nas_paths))
    return raw

def _derive_index(raw):
    idx = dict(raw)
    for fname, path in raw.items():
        clean = fname.lstrip("-")
        if clean != fname: idx[clean] = path
        base = clean.split("_")[0]
        if base and base != clean: idx[base] = path
        if "-" in clean:
            after = clean.split("-", 1)[1]
            idx[after] = path
            base2 = after.split("_")[0]
            if base2 != after: idx[base2] = path
    return idx

def load_nas_cache(nas_raw):
    if not os.path.exists(CACHE_FILE): return None, None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("nas_paths") != nas_raw: return None, None
        ts = data.get("timestamp", "")
        return _derive_index(data["index"]), ts
    except: return None, None

def save_nas_cache(nas_raw, raw_index):
    import datetime
    try:
        ts = datetime.datetime.now().strftime("%d/%m %H:%M")
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"nas_paths": nas_raw, "timestamp": ts, "index": raw_index},
                      f, ensure_ascii=False)
        return ts
    except: return ""

class NasPullApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NAS Pull")
        self.geometry("750x740")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.cfg = load_config()
        self.export_var = tk.StringVar(value="")
        self.is_running = False
        self._build_ui()
        self._update_cache_label()

    def _build_ui(self):
        pad = {"padx": 20, "pady": 6}

        ctk.CTkLabel(self, text="NAS PULL", font=("Consolas", 22, "bold"),
                     text_color=WHITE).pack(pady=(20,2))
        ctk.CTkLabel(self, text="Kéo file từ NAS về local",
                     font=("Consolas", 11), text_color=GRAY).pack(pady=(0,14))

        # IDs input
        fi = ctk.CTkFrame(self, fg_color=BG2, corner_radius=10)
        fi.pack(fill="x", **pad)
        ctk.CTkLabel(fi, text="Danh sách file  (Tên file | ID, mỗi dòng 1 file)",
                     font=("Consolas", 12, "bold"), text_color=WHITE).pack(anchor="w", padx=14, pady=(10,3))
        self.ids_box = ctk.CTkTextbox(fi, height=200, font=("Consolas", 11),
                                       fg_color=BG3, text_color="#ccc")
        self.ids_box.pack(fill="x", padx=14, pady=(0,10))

        # Export folder
        fe = ctk.CTkFrame(self, fg_color=BG2, corner_radius=10)
        fe.pack(fill="x", **pad)
        ctk.CTkLabel(fe, text="Folder đích", font=("Consolas", 12, "bold"),
                     text_color=WHITE).pack(anchor="w", padx=14, pady=(10,3))
        r = ctk.CTkFrame(fe, fg_color="transparent"); r.pack(fill="x", padx=14, pady=(0,10))
        ctk.CTkEntry(r, textvariable=self.export_var, width=580,
                     font=("Consolas", 11), fg_color=BG3, border_color="#333").pack(side="left")
        ctk.CTkButton(r, text="...", width=55, command=self._browse,
                      fg_color="#333", hover_color="#555").pack(side="left", padx=(6,0))

        # Cache status row
        fc = ctk.CTkFrame(self, fg_color="transparent")
        fc.pack(fill="x", padx=20, pady=(2,0))
        self.cache_label = ctk.CTkLabel(fc, text="", font=("Consolas", 11), text_color=GRAY)
        self.cache_label.pack(side="left")
        self.btn_refresh = ctk.CTkButton(fc, text="🔄 Refresh Cache", width=140,
                                          height=28, font=("Consolas", 11),
                                          fg_color="#333", hover_color="#555",
                                          command=self._run_refresh)
        self.btn_refresh.pack(side="right")

        # Run button
        self.btn_run = ctk.CTkButton(self, text="▶  PULL FROM NAS", height=44,
                                      font=("Consolas", 15, "bold"),
                                      fg_color=BLUE, hover_color="#1565C0",
                                      text_color="white", command=self._run)
        self.btn_run.pack(fill="x", padx=20, pady=(8,6))

        # Log
        ctk.CTkLabel(self, text="Log", font=("Consolas", 12, "bold"),
                     text_color=GRAY).pack(anchor="w", padx=20, pady=(4,2))
        self.log_box = ctk.CTkTextbox(self, height=220, font=("Consolas", 11),
                                       fg_color=BG2, text_color="#ccc")
        self.log_box.pack(fill="x", padx=20, pady=(0,6))
        self.log_box.configure(state="disabled")

        # Status
        self.status_label = ctk.CTkLabel(self, text="Sẵn sàng",
                                          font=("Consolas", 11), text_color=GRAY)
        self.status_label.pack(anchor="w", padx=20, pady=(0,10))

    def _update_cache_label(self):
        nas_raw = self.cfg.get("nas_path", "")
        _, ts = load_nas_cache(nas_raw)
        if ts:
            self.cache_label.configure(text=f"Cache: {ts}", text_color=GREEN)
        else:
            self.cache_label.configure(text="Cache: chưa có", text_color=GRAY)

    def _log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _status(self, msg):
        self.status_label.configure(text=msg)

    def _browse(self):
        p = browse_folder("Chọn folder đích")
        if p: self.export_var.set(p)

    def _parse_entries(self, text):
        entries = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line: continue
            if "\t" in line:
                parts = line.split("\t", 1)
            elif "|" in line:
                parts = line.split("|", 1)
            else:
                parts = line.rsplit(" ", 1)
            dst_name = parts[0].strip()
            vid_id = parts[1].strip().lower() if len(parts) > 1 else parts[0].strip().lower()
            entries.append({"name": dst_name, "id": vid_id})
        return entries

    def _set_busy(self, busy, label="▶  PULL FROM NAS"):
        self.is_running = busy
        if busy:
            self.btn_run.configure(text="⏳  ĐANG CHẠY...", fg_color="#555", state="disabled")
            self.btn_refresh.configure(state="disabled")
        else:
            self.btn_run.configure(text=label, fg_color=BLUE, state="normal")
            self.btn_refresh.configure(state="normal")

    def _run_refresh(self):
        if self.is_running: return
        nas_raw = self.cfg.get("nas_path", "")
        if not nas_raw:
            self._status("❌ Không tìm thấy NAS path trong this.json"); return

        nas_paths = [p.strip() for p in nas_raw.split(",") if p.strip()]
        self._set_busy(True)
        self.log_box.configure(state="normal"); self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self._status("Đang refresh cache...")

        def worker():
            def _try_remount(d):
                try:
                    test = subprocess.run(["ls", d], capture_output=True, timeout=5)
                    if test.returncode != 0:
                        self.after(0, lambda: self._log("🔄 NAS stale — đang remount..."))
                        subprocess.run(["sudo", "systemctl", "daemon-reload"], timeout=10)
                        subprocess.run(["sudo", "systemctl", "restart", "remote-fs.target"], timeout=30)
                        import time; time.sleep(3)
                except: pass

            for d in nas_paths:
                _try_remount(d)

            raw = _build_raw_index(nas_paths,
                                   log_fn=lambda m: self.after(0, lambda msg=m: self._log(msg)))
            ts = save_nas_cache(nas_raw, raw)
            self.after(0, lambda: self._log(f"\n✅ Cache đã lưu ({len(raw)} file) lúc {ts}"))
            self.after(0, lambda: self._update_cache_label())
            self.after(0, lambda: self._status("✅ Cache xong!"))
            self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def _run(self):
        if self.is_running: return

        text = self.ids_box.get("1.0", "end").strip()
        export_dir = self.export_var.get().strip()

        if not text:
            self._status("❌ Chưa nhập danh sách"); return
        if not export_dir:
            self._status("❌ Chưa chọn folder đích"); return

        entries = self._parse_entries(text)
        if not entries:
            self._status("❌ Không parse được"); return

        nas_raw = self.cfg.get("nas_path", "")
        if not nas_raw:
            self._status("❌ Không tìm thấy NAS path trong this.json"); return

        nas_paths = [p.strip() for p in nas_raw.split(",") if p.strip()]
        os.makedirs(export_dir, exist_ok=True)

        self._set_busy(True)
        self.log_box.configure(state="normal"); self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self._status("Đang load index NAS...")

        def worker():
            # Thử load cache trước
            nas_index, ts = load_nas_cache(nas_raw)
            if nas_index is not None:
                self.after(0, lambda n=len(nas_index), t=ts:
                           self._log(f"⚡ Dùng cache ({n} key, lưu lúc {t})"))
            else:
                # Cache miss — quét NAS
                self.after(0, lambda: self._log("📡 Không có cache, đang quét NAS..."))

                def _try_remount(d):
                    try:
                        test = subprocess.run(["ls", d], capture_output=True, timeout=5)
                        if test.returncode != 0:
                            self.after(0, lambda: self._log("🔄 NAS stale — đang remount..."))
                            subprocess.run(["sudo", "systemctl", "daemon-reload"], timeout=10)
                            subprocess.run(["sudo", "systemctl", "restart", "remote-fs.target"], timeout=30)
                            import time; time.sleep(3)
                    except: pass

                for d in nas_paths:
                    _try_remount(d)

                raw = _build_raw_index(nas_paths,
                                       log_fn=lambda m: self.after(0, lambda msg=m: self._log(msg)))
                ts = save_nas_cache(nas_raw, raw)
                nas_index = _derive_index(raw)
                self.after(0, lambda t=ts: self._log(f"✅ Cache đã lưu lúc {t}"))
                self.after(0, lambda: self._update_cache_label())

            self.after(0, lambda: self._log(f"\n▶ Bắt đầu pull {len(entries)} file...\n"))
            success = failed = skipped = 0
            total = len(entries)

            for i, entry in enumerate(entries, 1):
                name   = entry["name"]
                vid_id = entry["id"]
                prefix = f"[{i}/{total}]"
                found  = nas_index.get(vid_id)

                if not found:
                    self.after(0, lambda p=prefix, v=vid_id: self._log(f"{p} ❌ Không tìm thấy: {v}"))
                    failed += 1
                    continue

                ext = os.path.splitext(found)[1]
                dst = os.path.join(export_dir, name + ext)

                if os.path.exists(dst):
                    self.after(0, lambda p=prefix, n=name+ext: self._log(f"{p} ⏭️  Đã có: {n}"))
                    skipped += 1
                    continue

                try:
                    size_mb = os.path.getsize(found) / 1024 / 1024
                    self.after(0, lambda p=prefix, n=name+ext, s=size_mb:
                               self._log(f"{p} ⬇️  Đang kéo: {n} ({s:.0f} MB)..."))
                    subprocess.run(
                        ["rsync", "--timeout=30", "--inplace", found, dst],
                        check=True, timeout=600
                    )
                    self.after(0, lambda p=prefix, n=name+ext: self._log(f"{p} ✅ {n}"))
                    success += 1
                except subprocess.TimeoutExpired:
                    if os.path.exists(dst): os.remove(dst)
                    self.after(0, lambda p=prefix, n=name: self._log(f"{p} ⏱️ Timeout: {n}"))
                    failed += 1
                except Exception as e:
                    self.after(0, lambda p=prefix, n=name, err=str(e): self._log(f"{p} ❌ {n}: {err}"))
                    failed += 1

                self.after(0, lambda s=success, f=failed, sk=skipped, t=total:
                           self._status(f"[{s+f+sk}/{t}] ✅{s} ❌{f} ⏭️{sk}"))

            self.after(0, lambda s=success, f=failed, sk=skipped:
                       self._log(f"\n🏁 Xong: {s} thành công, {f} thất bại, {sk} bỏ qua."))
            self.after(0, self._finish)

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self):
        self._set_busy(False)
        self._status("✅ Xong!")

if __name__ == "__main__":
    app = NasPullApp()
    app.mainloop()
