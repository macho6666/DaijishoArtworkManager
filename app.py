import os, re, io, json, base64, shutil, subprocess, threading, webbrowser, sys, posixpath, tempfile, multiprocessing, time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import requests

APP_NAME = "Daijisho Artwork Manager"
CONFIG = Path.home() / ".daijisho_artwork_manager.json"

PLATFORMS = {
    "GB":      ("/sdcard/Roms/GB",      "/sdcard/DaijishoMedia/GB",      "Game Boy"),
    "GBC":     ("/sdcard/Roms/GBC",     "/sdcard/DaijishoMedia/GBC",     "Game Boy Color"),
    "GBA":     ("/sdcard/Roms/GBA",     "/sdcard/DaijishoMedia/GBA",     "Game Boy Advance"),
    "NES":     ("/sdcard/Roms/NES",     "/sdcard/DaijishoMedia/NES",     "NES Famicom"),
    "NDS":     ("/sdcard/Roms/NDS",     "/sdcard/DaijishoMedia/NDS",     "Nintendo DS"),
    "SNES":    ("/sdcard/Roms/SNES",    "/sdcard/DaijishoMedia/SNES",    "Super Nintendo"),
    "Genesis": ("/sdcard/Roms/MD",      "/sdcard/DaijishoMedia/Genesis", "Sega Genesis Mega Drive"),
}
ROM_EXTS = {".zip",".7z",".gb",".gbc",".gba",".nes",".nds",".sfc",".smc",".md",".gen",".bin"}

def load_cfg():
    try: return json.loads(CONFIG.read_text(encoding="utf-8"))
    except: return {}

def save_cfg(c):
    try: CONFIG.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    except: pass

def clean_search_name(filename):
    s = Path(filename).stem
    # Search-only cleanup. The actual ROM/output filename is never changed.
    patterns = [
        r"\((?:K|J|U|E|USA|Japan|Korea|Europe|World|En|Ko|Ja)\)",
        r"\((?:K|k)\d{4,}(?:\s+color)?\)",
        r"\((?:v|ver\.?)\s*[\d.]+\)",
        r"\(\d+(?:\.\d+)?ver\)",
        r"\[(?:!|a|b|f|h|o|p|t|T|\+|-|0-9)+\]",
    ]
    for pat in patterns:
        s = re.sub(pat, " ", s, flags=re.I)
    s = re.sub(r"\b(?:KOR|JPN|USA|EUR)\b", " ", s, flags=re.I)
    s = re.sub(r"\b(?:translated|translation|patched|hack|colorized)\b", " ", s, flags=re.I)
    s = s.replace("_", " ")
    s = re.sub(r"\s+", " ", s).strip(" -_")
    return s

PLATFORM_SEARCH_NAMES = {
    "gb": "Game Boy",
    "gameboy": "Game Boy",
    "gbc": "Game Boy Color",
    "gba": "Game Boy Advance",
    "nes": "Nintendo Entertainment System Famicom",
    "fc": "Nintendo Entertainment System Famicom",
    "famicom": "Nintendo Entertainment System Famicom",
    "snes": "Super Nintendo",
    "sfc": "Super Famicom",
    "md": "Sega Mega Drive Genesis",
    "megadrive": "Sega Mega Drive Genesis",
    "genesis": "Sega Genesis Mega Drive",
    "nds": "Nintendo DS",
    "ds": "Nintendo DS",
    "n64": "Nintendo 64",
    "ps1": "PlayStation",
    "psx": "PlayStation",
    "psp": "PlayStation Portable",
    "neogeo": "Neo Geo",
    "neo geo": "Neo Geo",
}


def google_image_picker_process(query, result_file):
    """Open real Google Images in a WebView and save the clicked/selected image locally."""
    try:
        import webview
        from urllib.parse import quote_plus
        import requests as _requests

        class PickerAPI:
            def __init__(self):
                self.window = None

            def select_image(self, url):
                try:
                    if not url:
                        return {"ok": False, "error": "이미지 URL을 찾지 못했습니다."}
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                                      "Chrome/153.0.0.0 Safari/537.36",
                        "Referer": "https://www.google.com/"
                    }
                    r = _requests.get(url, timeout=25, headers=headers)
                    r.raise_for_status()
                    ctype = r.headers.get("content-type", "").lower()
                    if "image" not in ctype:
                        return {"ok": False, "error": "선택한 항목이 이미지가 아닙니다."}
                    Path(result_file).write_bytes(r.content)
                    if self.window:
                        self.window.destroy()
                    return {"ok": True}
                except Exception as e:
                    return {"ok": False, "error": str(e)}

        api = PickerAPI()
        url = "https://www.google.com/search?tbm=isch&hl=ko&q=" + quote_plus(query)
        window = webview.create_window(
            "Google 이미지에서 선택",
            url=url,
            js_api=api,
            width=1180,
            height=820,
            min_size=(900, 650),
            background_color="#0b0b0b"
        )
        api.window = window

        def inject_picker():
            # A fixed black/white helper bar. User clicks a Google result first,
            # then this script automatically captures the largest visible image.
            js = r"""
            (() => {
              if (window.__daijishoPickerInstalled) return;
              window.__daijishoPickerInstalled = true;

              const bar = document.createElement('div');
              bar.id = '__daijisho_picker_bar';
              bar.style.cssText =
                'position:fixed;z-index:2147483647;top:12px;left:50%;transform:translateX(-50%);' +
                'background:#0b0b0b;color:#fff;border:1px solid #555;border-radius:10px;' +
                'padding:10px 16px;font:600 14px Arial,sans-serif;box-shadow:0 8px 30px rgba(0,0,0,.45);';
              bar.textContent = '원하는 이미지를 클릭하세요 · 큰 미리보기가 뜨면 자동으로 가져옵니다';
              document.documentElement.appendChild(bar);

              let busy = false;
              document.addEventListener('click', (ev) => {
                const img = ev.target && ev.target.closest ? ev.target.closest('img') : null;
                if (!img || busy) return;
                busy = true;
                bar.textContent = '이미지 확인 중...';

                setTimeout(async () => {
                  try {
                    const imgs = Array.from(document.images).filter(x => {
                      const r = x.getBoundingClientRect();
                      const s = getComputedStyle(x);
                      return r.width >= 120 && r.height >= 100 &&
                             r.bottom > 0 && r.top < innerHeight &&
                             s.display !== 'none' && s.visibility !== 'hidden';
                    });

                    imgs.sort((a,b) => {
                      const ar = a.getBoundingClientRect(), br = b.getBoundingClientRect();
                      const aScore = ar.width * ar.height + (a.naturalWidth * a.naturalHeight / 20);
                      const bScore = br.width * br.height + (b.naturalWidth * b.naturalHeight / 20);
                      return bScore - aScore;
                    });

                    const best = imgs[0] || img;
                    const src = best.currentSrc || best.src || img.currentSrc || img.src;
                    if (!src || !src.startsWith('http')) throw new Error('이미지 주소를 찾지 못했습니다.');
                    bar.textContent = '이미지 가져오는 중...';
                    const res = await window.pywebview.api.select_image(src);
                    if (!res || !res.ok) throw new Error((res && res.error) || '가져오기 실패');
                  } catch (e) {
                    bar.textContent = '가져오기 실패 · 다른 이미지를 클릭해 보세요';
                    busy = false;
                  }
                }, 1100);
              }, true);
            })();
            """
            try:
                window.run_js(js)
            except Exception:
                pass

        window.events.loaded += inject_picker
        webview.start(debug=False)
    except Exception:
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME + " v0.6")
        self.geometry("1180x760")
        self.minsize(980,650)
        self.cfg = load_cfg()
        self.roms = []
        self.current = None
        self.selected_image = None
        self.preview_photo = None
        self.search_photos = []
        self.search_urls = []
        self.rom_path = tk.StringVar(value="/sdcard")
        self.media_name = tk.StringVar(value="")
        self._ui()
        self.after(300, self.check_adb)

    def _style_ui(self):
        self.configure(bg="#0b0b0b")
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure(".", background="#0b0b0b", foreground="#f5f5f5",
                    fieldbackground="#141414", bordercolor="#2f2f2f",
                    lightcolor="#2f2f2f", darkcolor="#2f2f2f",
                    font=("Segoe UI", 10))
        s.configure("TFrame", background="#0b0b0b")
        s.configure("Card.TFrame", background="#111111")
        s.configure("TLabel", background="#0b0b0b", foreground="#d9d9d9")
        s.configure("Title.TLabel", background="#0b0b0b", foreground="#ffffff",
                    font=("Segoe UI Semibold", 18))
        s.configure("Section.TLabel", background="#111111", foreground="#ffffff",
                    font=("Segoe UI Semibold", 11))
        s.configure("Muted.TLabel", background="#111111", foreground="#8f8f8f",
                    font=("Segoe UI", 9))
        s.configure("TButton", background="#171717", foreground="#ffffff",
                    bordercolor="#3a3a3a", padding=(12, 8), relief="flat")
        s.map("TButton", background=[("active","#262626"),("pressed","#333333")])
        s.configure("Primary.TButton", background="#f2f2f2", foreground="#0b0b0b",
                    bordercolor="#f2f2f2", padding=(14, 9),
                    font=("Segoe UI Semibold", 10))
        s.map("Primary.TButton", background=[("active","#ffffff"),("pressed","#d9d9d9")])
        s.configure("TEntry", fieldbackground="#151515", foreground="#ffffff",
                    insertcolor="#ffffff", bordercolor="#353535", padding=7)
        s.configure("Treeview", background="#101010", fieldbackground="#101010",
                    foreground="#e8e8e8", bordercolor="#292929", rowheight=29)
        s.configure("Treeview.Heading", background="#171717", foreground="#bdbdbd",
                    bordercolor="#292929", font=("Segoe UI Semibold", 9))
        s.map("Treeview", background=[("selected","#f2f2f2")],
              foreground=[("selected","#0b0b0b")])
        s.configure("TPanedwindow", background="#0b0b0b")
        s.configure("Vertical.TScrollbar", background="#171717", troughcolor="#0b0b0b",
                    bordercolor="#0b0b0b", arrowcolor="#ffffff")

    def _ui(self):
        self._style_ui()

        header = ttk.Frame(self, padding=(18,16,18,10))
        header.pack(fill="x")
        titlebox = ttk.Frame(header)
        titlebox.pack(side="left")
        ttk.Label(titlebox, text="DAIJISHO  ARTWORK  MANAGER", style="Title.TLabel").pack(anchor="w")
        ttk.Label(titlebox, text="ROM artwork matching & Android transfer", foreground="#777777").pack(anchor="w")
        self.status=tk.StringVar(value="준비")
        ttk.Label(header,textvariable=self.status,foreground="#bdbdbd").pack(side="right",padx=(10,0))
        ttk.Button(header,text="ADB 연결 확인",command=self.check_adb).pack(side="right")

        pathcard = ttk.Frame(self, style="Card.TFrame", padding=14)
        pathcard.pack(fill="x", padx=18, pady=(0,12))
        row1=ttk.Frame(pathcard,style="Card.TFrame"); row1.pack(fill="x")
        ttk.Label(row1,text="ROM FOLDER",style="Section.TLabel").pack(side="left")
        ttk.Entry(row1,textvariable=self.rom_path,state="readonly").pack(side="left",fill="x",expand=True,padx=12)
        ttk.Button(row1,text="휴대폰 폴더 선택",command=self.path_settings).pack(side="left",padx=(0,6))
        ttk.Button(row1,text="ROM 목록 읽기",command=self.load_roms).pack(side="left")

        row2=ttk.Frame(pathcard,style="Card.TFrame"); row2.pack(fill="x",pady=(10,0))
        ttk.Label(row2,text="MEDIA",style="Section.TLabel").pack(side="left")
        ttk.Label(row2,text="/sdcard/DaijishoMedia/",style="Muted.TLabel").pack(side="left",padx=(22,0))
        ttk.Entry(row2,textvariable=self.media_name,width=24).pack(side="left",padx=6)
        ttk.Label(row2,text="ROM 폴더명을 자동 사용하며 필요하면 수정할 수 있습니다.",style="Muted.TLabel").pack(side="left",padx=8)

        pan=ttk.Panedwindow(self,orient="horizontal")
        pan.pack(fill="both",expand=True,padx=18,pady=(0,18))
        left=ttk.Frame(pan,style="Card.TFrame",padding=14)
        right=ttk.Frame(pan,style="Card.TFrame",padding=14)
        pan.add(left,weight=5); pan.add(right,weight=6)

        lf=ttk.Frame(left,style="Card.TFrame"); lf.pack(fill="x",pady=(0,10))
        ttk.Label(lf,text="ROM LIBRARY",style="Section.TLabel").pack(side="left")
        ttk.Button(lf,text="전체 해제",command=lambda:self.set_all(False)).pack(side="right")
        ttk.Button(lf,text="전체 선택",command=lambda:self.set_all(True)).pack(side="right",padx=6)

        cols=("use","name")
        self.tree=ttk.Treeview(left,columns=cols,show="headings",selectmode="browse")
        self.tree.heading("use",text="✓"); self.tree.column("use",width=45,anchor="center",stretch=False)
        self.tree.heading("name",text="ROM FILE"); self.tree.column("name",width=440)
        self.tree.pack(fill="both",expand=True)
        self.tree.bind("<Double-1>",self.toggle_row)
        self.tree.bind("<<TreeviewSelect>>",self.on_select)

        ttk.Label(right,text="SELECTED GAME",style="Section.TLabel").pack(anchor="w")
        self.game=tk.StringVar(value="-")
        ttk.Label(right,textvariable=self.game,background="#111111",foreground="#ffffff",
                  font=("Segoe UI Semibold",12)).pack(anchor="w",pady=(6,14))

        controls=ttk.Frame(right,style="Card.TFrame"); controls.pack(fill="x")
        ttk.Button(controls,text="Google에서 이미지 선택",style="Primary.TButton",
                   command=self.google_api_search).pack(side="left")
        ttk.Button(controls,text="브라우저에서 Google 열기",
                   command=self.google_browser).pack(side="left",padx=7)
        ttk.Button(controls,text="내 이미지 선택",command=self.pick_image).pack(side="left")
        ttk.Button(controls,text="검색어 확인",command=self.api_settings).pack(side="right")

        self.hint=tk.StringVar(value="Google 결과에서 원하는 이미지를 클릭하면 자동으로 이 프로그램의 미리보기로 가져옵니다.")
        ttk.Label(right,textvariable=self.hint,style="Muted.TLabel").pack(anchor="w",pady=(10,8))

        preview_frame=tk.Frame(right,bg="#080808",highlightbackground="#333333",
                               highlightthickness=1,height=330)
        preview_frame.pack(fill="both",expand=True)
        preview_frame.pack_propagate(False)
        self.preview=tk.Label(preview_frame,text="NO IMAGE SELECTED",bg="#080808",
                              fg="#666666",font=("Segoe UI Semibold",11),anchor="center")
        self.preview.pack(fill="both",expand=True,padx=10,pady=10)

        out=ttk.Frame(right,style="Card.TFrame"); out.pack(fill="x",pady=(12,8))
        self.output=tk.StringVar(value="저장 결과: -")
        ttk.Label(out,textvariable=self.output,style="Muted.TLabel").pack(anchor="w")

        b=ttk.Frame(right,style="Card.TFrame"); b.pack(fill="x")
        ttk.Button(b,text="선택 이미지 적용 → 휴대폰 전송",style="Primary.TButton",
                   command=self.apply_current).pack(side="left")
        ttk.Button(b,text="다음 선택 게임",command=self.next_checked).pack(side="left",padx=8)

    def adb(self):
        base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        local = base / "adb.exe"
        return str(local) if local.exists() else (shutil.which("adb") or "adb")

    def runadb(self,args,check=True):
        p=subprocess.run([self.adb()]+args,capture_output=True,text=True,encoding="utf-8",errors="replace")
        if check and p.returncode: raise RuntimeError(p.stderr.strip() or p.stdout.strip())
        return p.stdout

    def check_adb(self):
        try:
            out=self.runadb(["devices"])
            dev=[x for x in out.splitlines()[1:] if "\tdevice" in x]
            self.status.set("ADB 연결됨" if dev else "ADB 장치 없음")
            if not dev: messagebox.showinfo("ADB","휴대폰에서 USB 디버깅을 켜고 PC 연결 허용을 눌러주세요.\nadb.exe는 PATH 또는 프로그램 폴더에 있어야 합니다.")
        except Exception as e:
            self.status.set("ADB 실행 불가")
            messagebox.showerror("ADB",f"ADB를 실행할 수 없습니다.\n\n{e}\n\nAndroid Platform Tools의 adb.exe를 프로그램 폴더에 넣어도 됩니다.")

    def shell_quote(self, s):
        return "'" + s.replace("'", "'\\''") + "'"

    def paths(self):
        rom = self.rom_path.get().strip().rstrip("/") or "/sdcard"
        folder = posixpath.basename(rom) or "Media"
        media_name = self.media_name.get().strip() or folder
        return rom, f"/sdcard/DaijishoMedia/{media_name}", folder

    def list_remote_dirs(self, path):
        # Avoid `sh -c for ... do` because some Android/ADB combinations
        # split the remote command and produce "unexpected do".
        # Android toybox ls -p appends "/" to directory names.
        p = path.rstrip("/") or "/"
        out = self.runadb(["shell", "ls", "-1p", p])
        dirs = []
        for line in out.splitlines():
            name = line.rstrip("\r")
            if name.endswith("/"):
                name = name[:-1]
                if name:
                    dirs.append(name)
        return sorted(dirs, key=str.casefold)

    def path_settings(self):
        try:
            self.check_adb()
            start = "/sdcard"
            win = tk.Toplevel(self)
            win.title("휴대폰 ROM 폴더 선택")
            win.geometry("700x560")
            win.transient(self)
            win.grab_set()

            current = tk.StringVar(value=start)
            top = ttk.Frame(win,padding=8); top.pack(fill="x")
            ttk.Label(top,text="현재 위치").pack(side="left")
            ttk.Entry(top,textvariable=current,state="readonly").pack(side="left",fill="x",expand=True,padx=6)

            tree = ttk.Treeview(win,columns=("folder",),show="headings",selectmode="browse")
            tree.heading("folder",text="폴더")
            tree.column("folder",width=620)
            tree.pack(fill="both",expand=True,padx=8,pady=4)

            def refresh():
                try:
                    dirs=self.list_remote_dirs(current.get())
                    tree.delete(*tree.get_children())
                    for i,n in enumerate(dirs):
                        tree.insert("","end",iid=str(i),values=(n,))
                except Exception as e:
                    messagebox.showerror("폴더 읽기 실패",str(e),parent=win)

            def enter_folder(event=None):
                sel=tree.selection()
                if not sel:return
                name=tree.item(sel[0],"values")[0]
                current.set(posixpath.join(current.get().rstrip("/") or "/",name))
                refresh()

            def up():
                p=current.get().rstrip("/")
                current.set(posixpath.dirname(p) or "/")
                refresh()

            def choose():
                p=current.get().rstrip("/") or "/"
                folder=posixpath.basename(p) or "Media"
                self.rom_path.set(p)
                self.media_name.set(folder)
                self.cfg["last_rom_path"]=p
                self.cfg["last_media_name"]=folder
                save_cfg(self.cfg)
                win.destroy()
                self.load_roms()

            tree.bind("<Double-1>",enter_folder)
            buttons=ttk.Frame(win,padding=8); buttons.pack(fill="x")
            ttk.Button(buttons,text="상위 폴더",command=up).pack(side="left")
            ttk.Label(buttons,text="폴더를 더블클릭해서 들어가세요.").pack(side="left",padx=10)
            ttk.Button(buttons,text="취소",command=win.destroy).pack(side="right")
            ttk.Button(buttons,text="현재 폴더 선택",command=choose).pack(side="right",padx=6)
            refresh()
        except Exception as e:
            messagebox.showerror("폴더 선택",str(e))

    def load_roms(self):
        try:
            rom, _, folder = self.paths()
            # Use the exact ls form verified on the user's Android device.
            out = self.runadb(["shell", "ls", "-1p", rom])
            # `ls -p` marks directories with trailing "/", so all other entries are files.
            file_names = []
            for line in out.splitlines():
                name = line.rstrip("\r")
                if name and not name.endswith("/"):
                    file_names.append(name)
            file_names = sorted(file_names, key=str.casefold)
            self.roms=[{"name":n,"checked":False} for n in file_names]
            if not self.media_name.get().strip():
                self.media_name.set(folder)
            self.cfg["last_rom_path"]=rom
            self.cfg["last_media_name"]=self.media_name.get().strip()
            save_cfg(self.cfg)
            self.refresh_tree()
            self.status.set(f"{len(file_names)}개 파일")
        except Exception as e:
            messagebox.showerror("ROM 읽기 실패",str(e))

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for i,r in enumerate(self.roms):
            self.tree.insert("", "end", iid=str(i), values=("✓" if r["checked"] else "",r["name"]))

    def set_all(self,v):
        for r in self.roms:r["checked"]=v
        self.refresh_tree()

    def toggle_row(self,e=None):
        sel=self.tree.selection()
        if sel:
            i=int(sel[0]); self.roms[i]["checked"]=not self.roms[i]["checked"]; self.refresh_tree(); self.tree.selection_set(str(i))

    def on_select(self,e=None):
        sel=self.tree.selection()
        if not sel:return
        self.current=int(sel[0]); n=self.roms[self.current]["name"]; self.game.set(n)
        self.output.set("저장 결과: "+self.paths()[1]+"/"+Path(n).stem+".jpg")

    def google_query(self):
        if self.current is None:return None
        _,_,folder=self.paths()
        platform = PLATFORM_SEARCH_NAMES.get(folder.strip().lower(), folder)
        game = clean_search_name(self.roms[self.current]["name"])
        return f'{game} {platform} box art'

    def google_browser(self):
        q=self.google_query()
        if not q:return messagebox.showinfo("선택","먼저 ROM을 선택하세요.")
        from urllib.parse import quote_plus
        webbrowser.open("https://www.google.com/search?tbm=isch&q="+quote_plus(q))

    def api_settings(self):
        q=self.google_query()
        if not q:
            return messagebox.showinfo("검색어","먼저 ROM을 선택하세요.")
        messagebox.showinfo("Google 검색어",q)

    def google_api_search(self):
        q=self.google_query()
        if not q:
            return messagebox.showinfo("선택","먼저 ROM을 선택하세요.")

        try:
            import webview  # availability check in the main process
        except Exception:
            return messagebox.showerror(
                "Google 이미지 선택",
                "내장 Google 창을 사용하려면 pywebview가 필요합니다.\n"
                "v0.6용 requirements.txt와 GitHub Actions 파일도 함께 교체해 주세요."
            )

        result_file = str(Path(tempfile.gettempdir()) / "daijisho_google_selected_image.bin")
        try:
            Path(result_file).unlink(missing_ok=True)
        except Exception:
            pass

        self.status.set("Google 이미지 창 여는 중...")
        self.hint.set("Google 창에서 원하는 이미지를 클릭하세요. 선택되면 자동으로 미리보기에 들어옵니다.")

        ctx = multiprocessing.get_context("spawn")
        self.google_picker_process = ctx.Process(
            target=google_image_picker_process,
            args=(q, result_file),
            daemon=True
        )
        self.google_picker_process.start()
        self._poll_google_picker(result_file)

    def _poll_google_picker(self, result_file):
        p = Path(result_file)
        if p.exists() and p.stat().st_size > 0:
            try:
                im=Image.open(p); im.load()
                self.choose_pil(im)
                self.status.set("Google 이미지 선택 완료")
                self.hint.set("이미지를 확인한 뒤 휴대폰으로 전송하세요.")
            except Exception as e:
                messagebox.showerror("이미지 가져오기",str(e))
                self.status.set("준비")
            finally:
                try:p.unlink(missing_ok=True)
                except Exception:pass
            return

        proc=getattr(self,"google_picker_process",None)
        if proc is not None and proc.is_alive():
            self.after(400,lambda:self._poll_google_picker(result_file))
        else:
            self.status.set("준비")
            self.hint.set("Google 이미지 선택이 취소되었습니다. 다시 시도하거나 내 이미지를 선택할 수 있습니다.")

    def choose_pil(self,im):
        self.selected_image=im.copy(); self.show_preview(im)

    def pick_image(self):
        p=filedialog.askopenfilename(filetypes=[("Images","*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tif *.tiff"),("All files","*.*")])
        if not p:return
        try:
            im=Image.open(p); im.load(); self.choose_pil(im)
        except Exception as e:messagebox.showerror("이미지",str(e))

    def show_preview(self,im):
        p=im.copy(); p.thumbnail((420,260)); self.preview_photo=ImageTk.PhotoImage(p)
        self.preview.configure(image=self.preview_photo,text="")

    def apply_current(self):
        if self.current is None:return messagebox.showinfo("선택","ROM을 선택하세요.")
        if self.selected_image is None:return messagebox.showinfo("이미지","이미지를 선택하세요.")
        name=self.roms[self.current]["name"]; _,media,_=self.paths()
        outfile=Path(name).stem+".jpg"
        tmp=Path(os.environ.get("TEMP","."))/"daijisho_artwork_tmp.jpg"
        try:
            im=self.selected_image
            if im.mode in ("RGBA","LA"):
                bg=Image.new("RGB",im.size,"white"); bg.paste(im,mask=im.getchannel("A")); im=bg
            else: im=im.convert("RGB")
            im.save(tmp,"JPEG",quality=94,optimize=True)
            self.runadb(["shell","mkdir","-p",media])
            self.runadb(["push",str(tmp),media.rstrip("/")+"/"+outfile])
            self.output.set(f"전송 완료: {media}/{outfile}")
            self.roms[self.current]["checked"]=False; self.refresh_tree()
            self.status.set("전송 완료")
        except Exception as e:messagebox.showerror("전송 실패",str(e))

    def next_checked(self):
        start=(self.current+1) if self.current is not None else 0
        ids=list(range(start,len(self.roms)))+list(range(0,start))
        for i in ids:
            if self.roms[i]["checked"]:
                self.tree.selection_set(str(i)); self.tree.see(str(i)); self.on_select(); return
        messagebox.showinfo("완료","선택된 게임이 더 없습니다.")

if __name__=="__main__":
    multiprocessing.freeze_support()
    App().mainloop()
