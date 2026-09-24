import os, re, io, json, base64, shutil, subprocess, threading, webbrowser
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
    # Search only: remove common dump/region tags, never alter final output filename.
    s = re.sub(r"\s*[\(\[]\s*(K|J|U|E|USA|Japan|Korea|Europe|World|En|Ko|Ja|Rev[^)\]]*|v\d[^)\]]*)\s*[\)\]]", "", s, flags=re.I)
    s = re.sub(r"\s*\[[!a-z0-9+_-]+\]\s*", " ", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME + " v0.1")
        self.geometry("1180x760")
        self.minsize(980,650)
        self.cfg = load_cfg()
        self.roms = []
        self.current = None
        self.selected_image = None
        self.preview_photo = None
        self.search_photos = []
        self._ui()
        self.after(300, self.check_adb)

    def _ui(self):
        top=ttk.Frame(self,padding=8); top.pack(fill="x")
        ttk.Label(top,text="플랫폼").pack(side="left")
        self.platform=tk.StringVar(value="GB")
        ttk.Combobox(top,textvariable=self.platform,values=list(PLATFORMS),state="readonly",width=10).pack(side="left",padx=5)
        ttk.Button(top,text="ADB 연결 확인",command=self.check_adb).pack(side="left",padx=4)
        ttk.Button(top,text="ROM 목록 읽기",command=self.load_roms).pack(side="left",padx=4)
        ttk.Button(top,text="경로 설정",command=self.path_settings).pack(side="left",padx=4)
        self.status=tk.StringVar(value="준비")
        ttk.Label(top,textvariable=self.status).pack(side="right")

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
        ttk.Button(controls,text="앱 안에서 Google 후보 검색",command=self.google_api_search).pack(side="left",padx=4)
        ttk.Button(controls,text="내 이미지 선택",command=self.pick_image).pack(side="left",padx=4)
        ttk.Button(controls,text="Google API 설정",command=self.api_settings).pack(side="right")

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
        local=Path(__file__).resolve().parent/"adb.exe"
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

    def paths(self):
        p=self.platform.get()
        default_rom, default_media, label=PLATFORMS[p]
        custom=self.cfg.get("paths",{}).get(p,{})
        return custom.get("rom",default_rom), custom.get("media",default_media), label

    def path_settings(self):
        rom,media,_=self.paths()
        r=simpledialog.askstring("ROM 경로","휴대폰 ROM 경로",initialvalue=rom,parent=self)
        if r is None:return
        m=simpledialog.askstring("미디어 경로","휴대폰 DaijishoMedia 경로",initialvalue=media,parent=self)
        if m is None:return
        self.cfg.setdefault("paths",{})[self.platform.get()]={"rom":r.strip(),"media":m.strip()}
        save_cfg(self.cfg)

    def load_roms(self):
        try:
            rom,_,_=self.paths()
            # One entry per line, preserving spaces.
            out=self.runadb(["shell","find",rom,"-maxdepth","1","-type","f","-printf","%f\n"])
            names=[x.strip("\r") for x in out.splitlines() if Path(x.strip()).suffix.lower() in ROM_EXTS]
            names=sorted(set(names),key=str.casefold)
            self.roms=[{"name":n,"checked":False} for n in names]
            self.refresh_tree(); self.status.set(f"{len(names)}개 ROM")
        except Exception as e: messagebox.showerror("ROM 읽기 실패",str(e))

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
        self.output.set("저장 결과: "+Path(n).stem+".jpg")

    def google_query(self):
        if self.current is None:return None
        _,_,label=self.paths()
        return f'{clean_search_name(self.roms[self.current]["name"])} {label} box art'

    def google_browser(self):
        q=self.google_query()
        if not q:return messagebox.showinfo("선택","먼저 ROM을 선택하세요.")
        from urllib.parse import quote_plus
        webbrowser.open("https://www.google.com/search?tbm=isch&q="+quote_plus(q))

    def api_settings(self):
        key=simpledialog.askstring("Google API","Google Custom Search JSON API key",initialvalue=self.cfg.get("google_key",""),show="*",parent=self)
        if key is None:return
        cx=simpledialog.askstring("Google API","Programmable Search Engine ID (cx)\n이미지 검색 허용 엔진",initialvalue=self.cfg.get("google_cx",""),parent=self)
        if cx is None:return
        self.cfg["google_key"]=key.strip(); self.cfg["google_cx"]=cx.strip(); save_cfg(self.cfg)

    def google_api_search(self):
        q=self.google_query()
        if not q:return messagebox.showinfo("선택","먼저 ROM을 선택하세요.")
        key,cx=self.cfg.get("google_key"),self.cfg.get("google_cx")
        if not key or not cx:
            messagebox.showinfo("Google API","처음 한 번 API Key와 Search Engine ID(cx)가 필요합니다.\n'Google API 설정'에서 입력하세요.\n\nAPI 없이도 'Google 이미지 검색' 버튼으로 브라우저 검색 후 이미지를 저장하여 '내 이미지 선택'을 사용할 수 있습니다.")
            return
        self.status.set("이미지 검색 중...")
        threading.Thread(target=self._search_worker,args=(q,key,cx),daemon=True).start()

    def _search_worker(self,q,key,cx):
        try:
            r=requests.get("https://www.googleapis.com/customsearch/v1",params={"key":key,"cx":cx,"q":q,"searchType":"image","num":6,"safe":"active"},timeout=15)
            r.raise_for_status()
            items=r.json().get("items",[])
            data=[]
            for it in items:
                url=it.get("link")
                try:
                    rr=requests.get(url,timeout=10,headers={"User-Agent":"Mozilla/5.0"}); rr.raise_for_status()
                    im=Image.open(io.BytesIO(rr.content)); im.load(); data.append((im.copy(),url))
                except: pass
            self.after(0,lambda:self.show_candidates(data))
        except Exception as e:self.after(0,lambda:messagebox.showerror("검색 실패",str(e)))
        finally:self.after(0,lambda:self.status.set("준비"))

    def show_candidates(self,data):
        for w in self.candidates.winfo_children():w.destroy()
        self.search_photos=[]
        for idx,(im,url) in enumerate(data[:6]):
            thumb=im.copy(); thumb.thumbnail((130,130))
            ph=ImageTk.PhotoImage(thumb); self.search_photos.append(ph)
            btn=ttk.Button(self.candidates,image=ph,command=lambda im=im:self.choose_pil(im))
            btn.grid(row=idx//3,column=idx%3,padx=4,pady=4)
        if not data: ttk.Label(self.candidates,text="불러올 수 있는 후보가 없습니다. 브라우저 검색 또는 내 이미지 선택을 사용하세요.").pack()

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
