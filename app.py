import os, re, io, json, base64, shutil, subprocess, threading, webbrowser, sys, posixpath
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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME + " v0.5.1")
        self.geometry("1180x760")
        self.minsize(980,650)
        self.cfg = load_cfg()
        self.roms = []
        self.current = None
        self.selected_image = None
        self.preview_photo = None
        self.search_photos = []
        self.search_urls = []
        self.rom_path = tk.StringVar(value=self.cfg.get("last_rom_path", "/sdcard"))
        self.media_name = tk.StringVar(value=self.cfg.get("last_media_name", ""))
        self._ui()
        self.after(300, self.check_adb)

    def _ui(self):
        top=ttk.Frame(self,padding=8); top.pack(fill="x")
        ttk.Button(top,text="ADB 연결 확인",command=self.check_adb).pack(side="left",padx=4)
        ttk.Label(top,text="ROM 폴더").pack(side="left",padx=(10,4))
        ttk.Entry(top,textvariable=self.rom_path,width=48,state="readonly").pack(side="left",fill="x",expand=True)
        ttk.Button(top,text="휴대폰 폴더 선택",command=self.path_settings).pack(side="left",padx=4)
        ttk.Button(top,text="ROM 목록 읽기",command=self.load_roms).pack(side="left",padx=4)
        self.status=tk.StringVar(value="준비")
        ttk.Label(top,textvariable=self.status).pack(side="right")

        media=ttk.Frame(self,padding=(8,0,8,8)); media.pack(fill="x")
        ttk.Label(media,text="이미지 저장: /sdcard/DaijishoMedia/").pack(side="left")
        ttk.Entry(media,textvariable=self.media_name,width=24).pack(side="left")
        ttk.Label(media,text="  (ROM 폴더명 자동 사용 · 필요하면 수정 가능)").pack(side="left")

        pan=ttk.Panedwindow(self,orient="horizontal"); pan.pack(fill="both",expand=True,padx=8,pady=(0,8))
        left=ttk.Frame(pan,padding=6); right=ttk.Frame(pan,padding=6); pan.add(left,weight=2); pan.add(right,weight=3)

        lf=ttk.Frame(left); lf.pack(fill="x")
        ttk.Label(lf,text="휴대폰 ROM 목록").pack(side="left")
        ttk.Button(lf,text="전체 선택",command=lambda:self.set_all(True)).pack(side="right")
        ttk.Button(lf,text="전체 해제",command=lambda:self.set_all(False)).pack(side="right",padx=4)

        cols=("use","name")
        self.tree=ttk.Treeview(left,columns=cols,show="headings",selectmode="browse")
        self.tree.heading("use",text="선택"); self.tree.column("use",width=55,anchor="center",stretch=False)
        self.tree.heading("name",text="ROM 파일명"); self.tree.column("name",width=420)
        self.tree.pack(fill="both",expand=True,pady=5)
        self.tree.bind("<Double-1>",self.toggle_row); self.tree.bind("<<TreeviewSelect>>",self.on_select)

        ttk.Label(right,text="선택 게임",font=("",12,"bold")).pack(anchor="w")
        self.game=tk.StringVar(value="-"); ttk.Label(right,textvariable=self.game).pack(anchor="w",pady=(2,8))

        controls=ttk.Frame(right); controls.pack(fill="x")
        ttk.Button(controls,text="Google 이미지 검색",command=self.google_browser).pack(side="left")
        ttk.Button(controls,text="Google 후보 이미지 보기",command=self.google_api_search).pack(side="left",padx=4)
        ttk.Button(controls,text="내 이미지 선택",command=self.pick_image).pack(side="left",padx=4)
        ttk.Button(controls,text="검색어 확인",command=self.api_settings).pack(side="right")

        self.hint=tk.StringVar(value="이미지 파일은 아래 영역에 드래그해도 됩니다(Windows, tkinterdnd2 설치 시).")
        ttk.Label(right,textvariable=self.hint).pack(anchor="w",pady=6)

        self.preview=ttk.Label(right,text="선택한 이미지 미리보기",anchor="center",relief="groove")
        self.preview.pack(fill="x",ipady=80)

        ttk.Label(right,text="검색 후보 (클릭하여 선택)").pack(anchor="w",pady=(8,2))
        self.candidates=ttk.Frame(right); self.candidates.pack(fill="x")

        out=ttk.Frame(right); out.pack(fill="x",pady=10)
        self.output=tk.StringVar(value="저장 결과: -"); ttk.Label(out,textvariable=self.output).pack(anchor="w")
        b=ttk.Frame(right); b.pack(fill="x")
        ttk.Button(b,text="선택 이미지 적용 → 휴대폰 전송",command=self.apply_current).pack(side="left")
        ttk.Button(b,text="다음 선택 게임",command=self.next_checked).pack(side="left",padx=5)

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
        if not q:return messagebox.showinfo("선택","먼저 ROM을 선택하세요.")
        self.status.set("Google 후보 이미지 검색 중...")
        threading.Thread(target=self._google_candidate_worker,args=(q,),daemon=True).start()

    def _google_candidate_worker(self,q):
        try:
            from urllib.parse import quote_plus, unquote
            url="https://www.google.com/search?tbm=isch&hl=en&safe=active&q="+quote_plus(q)
            headers={
                "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
                "Accept-Language":"en-US,en;q=0.9"
            }
            r=requests.get(url,timeout=20,headers=headers)
            r.raise_for_status()
            html=r.text

            originals=[]
            # Try several Google result encodings for original images.
            pats=[
                r'\["(https?://[^"]+?\.(?:jpg|jpeg|png|webp)(?:\?[^"]*)?)",\d+,\d+\]',
                r'"ou":"(https?://[^"]+)"',
                r'\\"(https?://[^"\\]+?\.(?:jpg|jpeg|png|webp)(?:\?[^"\\]*)?)',
                r'https?://[^"\'<> ]+?\.(?:jpg|jpeg|png|webp)(?:\?[^"\'<> ]*)?'
            ]
            for pat in pats:
                for m in re.findall(pat,html,flags=re.I):
                    u=m if isinstance(m,str) else m[0]
                    u=(u.replace("\\u003d","=").replace("\\u0026","&")
                        .replace("\\/","/").replace("&amp;","&"))
                    if u.startswith("//"): u="https:"+u
                    if "google.com/search" in u: continue
                    if u not in originals: originals.append(u)
                    if len(originals)>=60: break
                if len(originals)>=60: break

            # Google-hosted thumbnails are still Google Image Search result thumbnails,
            # and are a useful fallback when original URLs are hidden in changed markup.
            thumbs=[]
            for u in re.findall(r'https://encrypted-tbn\d+\.gstatic\.com/images\?[^"\'<> ]+',html,flags=re.I):
                u=u.replace("&amp;","&")
                if u not in thumbs: thumbs.append(u)
                if len(thumbs)>=30: break

            candidates=originals+thumbs
            data=[]
            seen=set()
            for u in candidates:
                if u in seen: continue
                seen.add(u)
                try:
                    rr=requests.get(u,timeout=10,headers={"User-Agent":headers["User-Agent"],"Referer":"https://www.google.com/"})
                    rr.raise_for_status()
                    ctype=rr.headers.get("content-type","").lower()
                    if "image" not in ctype: continue
                    im=Image.open(io.BytesIO(rr.content)); im.load()
                    if im.width < 80 or im.height < 80: continue
                    data.append((im.copy(),u))
                    if len(data)>=9: break
                except Exception:
                    pass

            self.after(0,lambda:self.show_candidates(data))
            if not data:
                self.after(0,lambda:messagebox.showinfo(
                    "Google 후보 검색",
                    "Google 이미지 검색 결과 페이지는 열렸지만 프로그램에서 후보 이미지를 추출하지 못했습니다.\n\n"
                    "'Google 이미지 검색' 버튼으로 동일한 검색어의 결과를 브라우저에서 확인하거나 "
                    "'내 이미지 선택'을 사용할 수 있습니다."
                ))
        except Exception as e:
            self.after(0,lambda:messagebox.showerror(
                "Google 후보 검색 실패",
                f"{e}\n\n'Google 이미지 검색' 버튼은 계속 사용할 수 있습니다."
            ))
        finally:
            self.after(0,lambda:self.status.set("준비"))

    def show_candidates(self,data):
        for w in self.candidates.winfo_children():w.destroy()
        self.search_photos=[]; self.search_urls=[]
        for idx,(im,url) in enumerate(data[:9]):
            thumb=im.copy(); thumb.thumbnail((125,145))
            ph=ImageTk.PhotoImage(thumb)
            self.search_photos.append(ph); self.search_urls.append(url)
            ttk.Button(
                self.candidates,image=ph,
                command=lambda im=im:self.choose_pil(im)
            ).grid(row=idx//3,column=idx%3,padx=4,pady=4)
        if not data:
            ttk.Label(
                self.candidates,
                text="Google 후보를 불러오지 못했습니다. 'Google 이미지 검색' 또는 '내 이미지 선택'을 사용하세요."
            ).pack()

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
    App().mainloop()
