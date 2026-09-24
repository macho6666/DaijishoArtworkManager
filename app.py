import os, re, io, json, shutil, subprocess, threading, webbrowser, sys, posixpath, tempfile, hashlib
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageGrab
import requests

APP_NAME="Daijisho Artwork Manager"
CONFIG=Path.home()/".daijisho_artwork_manager.json"

def load_cfg():
    try:return json.loads(CONFIG.read_text(encoding="utf-8"))
    except:return {}

def save_cfg(c):
    try:CONFIG.write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding="utf-8")
    except:pass

def clean_search_name(filename):
    s=Path(filename).stem
    for pat in [
        r"\((?:K|J|U|E|USA|Japan|Korea|Europe|World|En|Ko|Ja)\)",
        r"\((?:K|k)\d{4,}(?:\s+color)?\)", r"\((?:v|ver\.?)\s*[\d.]+\)",
        r"\(\d+(?:\.\d+)?ver\)", r"\[(?:!|a|b|f|h|o|p|t|T|\+|-|0-9)+\]"
    ]: s=re.sub(pat," ",s,flags=re.I)
    s=re.sub(r"\b(?:KOR|JPN|USA|EUR|translated|translation|patched|hack|colorized)\b"," ",s,flags=re.I)
    return re.sub(r"\s+"," ",s.replace("_"," ")).strip(" -_")

PLATFORM_SEARCH_NAMES={
"gb":"Game Boy","gameboy":"Game Boy","gbc":"Game Boy Color","gba":"Game Boy Advance",
"nes":"Nintendo Entertainment System Famicom","fc":"Nintendo Entertainment System Famicom",
"famicom":"Nintendo Entertainment System Famicom","snes":"Super Nintendo","sfc":"Super Famicom",
"md":"Sega Mega Drive Genesis","megadrive":"Sega Mega Drive Genesis","genesis":"Sega Genesis Mega Drive",
"nds":"Nintendo DS","ds":"Nintendo DS","n64":"Nintendo 64","ps1":"PlayStation","psx":"PlayStation",
"psp":"PlayStation Portable","neogeo":"Neo Geo","neo geo":"Neo Geo"
}

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME+" v0.7")
        self.geometry("1180x760"); self.minsize(1000,680)
        self.cfg=load_cfg(); self.state_db=self.cfg.get("rom_status",{})
        self.roms=[]; self.current=None; self.selected_image=None; self.preview_photo=None
        self.manual_remote=set(); self.clipboard_last=""; self.clipboard_busy=False
        self.rom_path=tk.StringVar(value="/sdcard"); self.media_name=tk.StringVar(value="")
        self._ui()
        self.after(400,self.check_adb); self.after(1000,self.poll_clipboard)

    def _style(self):
        self.configure(bg="#eeeeee")
        s=ttk.Style(self)
        try:s.theme_use("clam")
        except:pass
        s.configure(".",font=("Segoe UI",10),background="#eeeeee",foreground="#333")
        s.configure("TFrame",background="#eeeeee"); s.configure("Card.TFrame",background="#fff")
        s.configure("Card.TLabel",background="#fff",foreground="#333")
        s.configure("Section.TLabel",background="#fff",foreground="#34383d",font=("Segoe UI Semibold",11))
        s.configure("Muted.TLabel",background="#fff",foreground="#777",font=("Segoe UI",9))
        s.configure("TButton",background="#e5e5e5",foreground="#333",bordercolor="#c7c7c7",padding=(10,7))
        s.map("TButton",background=[("active","#d6d6d6")])
        s.configure("Dark.TButton",background="#3a3f44",foreground="#fff",bordercolor="#3a3f44",
                    padding=(12,8),font=("Segoe UI Semibold",10))
        s.map("Dark.TButton",background=[("active","#50565c")])
        s.configure("TEntry",fieldbackground="#fff",foreground="#222",bordercolor="#ccc",padding=6)
        s.configure("Treeview",background="#fff",fieldbackground="#fff",foreground="#333",
                    bordercolor="#d5d5d5",rowheight=29)
        s.configure("Treeview.Heading",background="#e9e9e9",foreground="#444",bordercolor="#d0d0d0")
        s.map("Treeview",background=[("selected","#42474c")],foreground=[("selected","#fff")])

    def _ui(self):
        self._style()
        head=tk.Frame(self,bg="#34383d",height=68); head.pack(fill="x"); head.pack_propagate(False)
        tk.Label(head,text="DAIJISHO ARTWORK MANAGER",bg="#34383d",fg="white",
                 font=("Segoe UI Semibold",17)).pack(side="left",padx=20)
        self.status=tk.StringVar(value="준비")
        tk.Label(head,textvariable=self.status,bg="#34383d",fg="#ddd").pack(side="right",padx=20)
        ttk.Button(head,text="ADB 연결 확인",style="Dark.TButton",command=self.check_adb).pack(side="right",pady=14)

        card=ttk.Frame(self,style="Card.TFrame",padding=14); card.pack(fill="x",padx=18,pady=14)
        r=ttk.Frame(card,style="Card.TFrame"); r.pack(fill="x")
        ttk.Label(r,text="ROM 폴더",style="Section.TLabel").pack(side="left")
        ttk.Entry(r,textvariable=self.rom_path,state="readonly").pack(side="left",fill="x",expand=True,padx=12)
        ttk.Button(r,text="휴대폰 폴더 선택",command=self.path_settings).pack(side="left",padx=(0,6))
        ttk.Button(r,text="ROM 목록 읽기",style="Dark.TButton",command=self.load_roms).pack(side="left")
        r2=ttk.Frame(card,style="Card.TFrame"); r2.pack(fill="x",pady=(9,0))
        ttk.Label(r2,text="수동 이미지 폴더",style="Section.TLabel").pack(side="left")
        ttk.Label(r2,text="/sdcard/DaijishoMedia/",style="Card.TLabel").pack(side="left",padx=(12,0))
        ttk.Entry(r2,textvariable=self.media_name,width=22).pack(side="left",padx=5)

        pan=ttk.Panedwindow(self,orient="horizontal"); pan.pack(fill="both",expand=True,padx=18,pady=(0,18))
        left=ttk.Frame(pan,style="Card.TFrame",padding=14); right=ttk.Frame(pan,style="Card.TFrame",padding=14)
        pan.add(left,weight=5); pan.add(right,weight=6)

        top=ttk.Frame(left,style="Card.TFrame"); top.pack(fill="x",pady=(0,8))
        ttk.Label(top,text="ROM 목록",style="Section.TLabel").pack(side="left")
        self.summary=tk.StringVar(value="미확인 0 · 정상 0 · 수동 0 · 보완 0")
        ttk.Label(top,textvariable=self.summary,style="Muted.TLabel").pack(side="right")
        self.tree=ttk.Treeview(left,columns=("status","name"),show="headings",selectmode="extended")
        self.tree.heading("status",text="상태"); self.tree.column("status",width=105,anchor="center",stretch=False)
        self.tree.heading("name",text="ROM 파일"); self.tree.column("name",width=430)
        self.tree.pack(fill="both",expand=True); self.tree.bind("<<TreeviewSelect>>",self.on_select)
        a=ttk.Frame(left,style="Card.TFrame"); a.pack(fill="x",pady=(9,0))
        ttk.Button(a,text="✓ 정상으로 표시",command=lambda:self.mark_selected("normal")).pack(side="left")
        ttk.Button(a,text="✕ 보완 필요",command=lambda:self.mark_selected("missing")).pack(side="left",padx=6)
        ttk.Button(a,text="? 미확인으로",command=lambda:self.mark_selected("unknown")).pack(side="left")
        ttk.Button(a,text="상태 새로고침",command=self.scan_manual_media).pack(side="right")

        ttk.Label(right,text="선택 게임",style="Section.TLabel").pack(anchor="w")
        self.game=tk.StringVar(value="-")
        ttk.Label(right,textvariable=self.game,style="Card.TLabel",font=("Segoe UI Semibold",12)).pack(anchor="w",pady=(5,4))
        self.current_state=tk.StringVar(value="상태: -")
        ttk.Label(right,textvariable=self.current_state,style="Muted.TLabel").pack(anchor="w",pady=(0,10))
        c=ttk.Frame(right,style="Card.TFrame"); c.pack(fill="x")
        ttk.Button(c,text="Google 이미지 검색",style="Dark.TButton",command=self.google_browser).pack(side="left")
        ttk.Button(c,text="내 이미지 선택",command=self.pick_image).pack(side="left",padx=7)
        ttk.Button(c,text="현재 수동 이미지 불러오기",command=self.load_existing_manual).pack(side="left")
        ttk.Button(c,text="검색어 확인",command=self.show_query).pack(side="right")
        self.clip_status=tk.StringVar(value="Google에서 이미지 우클릭 → 이미지 주소 복사 또는 이미지 복사")
        ttk.Label(right,textvariable=self.clip_status,style="Muted.TLabel").pack(anchor="w",pady=(10,8))
        pf=tk.Frame(right,bg="#f7f7f7",highlightbackground="#cfcfcf",highlightthickness=1,height=330)
        pf.pack(fill="both",expand=True); pf.pack_propagate(False)
        self.preview=tk.Label(pf,text="NO IMAGE SELECTED",bg="#f7f7f7",fg="#888",
                              font=("Segoe UI Semibold",11))
        self.preview.pack(fill="both",expand=True,padx=10,pady=10)
        self.output=tk.StringVar(value="저장 결과: -")
        ttk.Label(right,textvariable=self.output,style="Muted.TLabel").pack(anchor="w",pady=(10,8))
        b=ttk.Frame(right,style="Card.TFrame"); b.pack(fill="x")
        ttk.Button(b,text="이 이미지 사용 → 휴대폰 전송",style="Dark.TButton",
                   command=self.apply_current).pack(side="left")
        ttk.Button(b,text="다음 미확인/보완 게임",command=self.next_missing).pack(side="left",padx=8)

    def adb(self):
        base=Path(sys.executable).resolve().parent if getattr(sys,"frozen",False) else Path(__file__).resolve().parent
        local=base/"adb.exe"; return str(local) if local.exists() else (shutil.which("adb") or "adb")

    def runadb(self,args,check=True):
        p=subprocess.run([self.adb()]+args,capture_output=True,text=True,encoding="utf-8",errors="replace")
        if check and p.returncode:raise RuntimeError(p.stderr.strip() or p.stdout.strip())
        return p.stdout

    def check_adb(self):
        try:
            out=self.runadb(["devices"]); dev=[x for x in out.splitlines()[1:] if "\tdevice" in x]
            self.status.set("ADB 연결됨" if dev else "ADB 장치 없음")
        except Exception as e:self.status.set("ADB 실행 불가")

    def paths(self):
        rom=self.rom_path.get().strip().rstrip("/") or "/sdcard"
        folder=posixpath.basename(rom) or "Media"; media_name=self.media_name.get().strip() or folder
        return rom,f"/sdcard/DaijishoMedia/{media_name}",folder

    def list_remote_dirs(self,path):
        out=self.runadb(["shell","ls","-1p",path.rstrip("/") or "/"])
        return sorted([x.rstrip("\r")[:-1] for x in out.splitlines() if x.rstrip("\r").endswith("/")],key=str.casefold)

    def path_settings(self):
        try:
            start="/sdcard"; win=tk.Toplevel(self); win.title("휴대폰 ROM 폴더 선택"); win.geometry("700x560")
            win.transient(self); win.grab_set(); current=tk.StringVar(value=start)
            top=ttk.Frame(win,padding=8); top.pack(fill="x")
            ttk.Label(top,text="현재 위치").pack(side="left")
            ttk.Entry(top,textvariable=current,state="readonly").pack(side="left",fill="x",expand=True,padx=6)
            tree=ttk.Treeview(win,columns=("folder",),show="headings",selectmode="browse")
            tree.heading("folder",text="폴더"); tree.column("folder",width=620); tree.pack(fill="both",expand=True,padx=8,pady=4)
            def refresh():
                try:
                    tree.delete(*tree.get_children())
                    for i,n in enumerate(self.list_remote_dirs(current.get())):tree.insert("","end",iid=str(i),values=(n,))
                except Exception as e:messagebox.showerror("폴더 읽기 실패",str(e),parent=win)
            def enter(e=None):
                s=tree.selection()
                if s:current.set(posixpath.join(current.get().rstrip("/") or "/",tree.item(s[0],"values")[0])); refresh()
            def up():current.set(posixpath.dirname(current.get().rstrip("/")) or "/"); refresh()
            def choose():
                p=current.get().rstrip("/") or "/"; self.rom_path.set(p); self.media_name.set(posixpath.basename(p) or "Media")
                win.destroy(); self.load_roms()
            tree.bind("<Double-1>",enter)
            bt=ttk.Frame(win,padding=8); bt.pack(fill="x")
            ttk.Button(bt,text="상위 폴더",command=up).pack(side="left")
            ttk.Button(bt,text="취소",command=win.destroy).pack(side="right")
            ttk.Button(bt,text="현재 폴더 선택",command=choose).pack(side="right",padx=6)
            refresh()
        except Exception as e:messagebox.showerror("폴더 선택",str(e))

    def load_roms(self):
        try:
            rom,_,folder=self.paths(); out=self.runadb(["shell","ls","-1p",rom])
            names=sorted([x.rstrip("\r") for x in out.splitlines() if x.strip() and not x.rstrip("\r").endswith("/")],key=str.casefold)
            self.roms=[{"name":n} for n in names]
            if not self.media_name.get().strip():self.media_name.set(folder)
            self.current=None; self.refresh_tree(); self.scan_manual_media()
            self.status.set(f"{len(names)}개 ROM")
        except Exception as e:messagebox.showerror("ROM 읽기 실패",str(e))

    def key(self,name):return f"{self.paths()[2]}|{name}"
    def get_state(self,name):
        if name in self.manual_remote:return "manual"
        return self.state_db.get(self.key(name),"unknown")
    def state_text(self,s):return {"manual":"★ 수동 이미지","normal":"✓ 정상","missing":"✕ 보완 필요","unknown":"? 미확인"}.get(s,"? 미확인")

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        counts={"unknown":0,"normal":0,"manual":0,"missing":0}
        for i,r in enumerate(self.roms):
            st=self.get_state(r["name"]); counts[st]+=1
            self.tree.insert("","end",iid=str(i),values=(self.state_text(st),r["name"]))
        self.summary.set(f'미확인 {counts["unknown"]} · 정상 {counts["normal"]} · 수동 {counts["manual"]} · 보완 {counts["missing"]}')

    def mark_selected(self,state):
        for iid in self.tree.selection():
            name=self.roms[int(iid)]["name"]; self.state_db[self.key(name)]=state
        self.cfg["rom_status"]=self.state_db; save_cfg(self.cfg); self.refresh_tree()

    def scan_manual_media(self):
        if not self.roms:return
        _,media,_=self.paths(); out=self.runadb(["shell","ls","-1p",media],check=False)
        files={x.rstrip("\r") for x in out.splitlines() if x.strip() and not x.rstrip("\r").endswith("/")}
        self.manual_remote={r["name"] for r in self.roms if Path(r["name"]).stem+".jpg" in files}
        self.refresh_tree()
        if self.current is not None:self.on_select()

    def on_select(self,e=None):
        s=self.tree.selection()
        if not s:return
        self.current=int(s[0]); n=self.roms[self.current]["name"]; self.game.set(n)
        self.current_state.set("상태: "+self.state_text(self.get_state(n)))
        self.output.set("저장 예정: "+self.paths()[1]+"/"+Path(n).stem+".jpg")
        self.clip_status.set("★ 수동 이미지가 있습니다. 불러오거나 새 이미지로 교체할 수 있습니다." if n in self.manual_remote
                             else "Google에서 이미지 우클릭 → 이미지 주소 복사 또는 이미지 복사")

    def google_query(self):
        if self.current is None:return None
        folder=self.paths()[2]; platform=PLATFORM_SEARCH_NAMES.get(folder.lower(),folder)
        return f'{clean_search_name(self.roms[self.current]["name"])} {platform} box art'

    def google_browser(self):
        q=self.google_query()
        if not q:return messagebox.showinfo("선택","먼저 ROM을 선택하세요.")
        from urllib.parse import quote_plus
        webbrowser.open("https://www.google.com/search?tbm=isch&q="+quote_plus(q))

    def show_query(self):
        q=self.google_query()
        if q:messagebox.showinfo("Google 검색어",q)

    def choose_pil(self,im):
        self.selected_image=im.copy(); p=im.copy(); p.thumbnail((470,310))
        self.preview_photo=ImageTk.PhotoImage(p); self.preview.configure(image=self.preview_photo,text="")

    def pick_image(self):
        p=filedialog.askopenfilename(filetypes=[("Images","*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tif *.tiff"),("All files","*.*")])
        if p:
            try:
                im=Image.open(p); im.load(); self.choose_pil(im)
            except Exception as e:messagebox.showerror("이미지",str(e))

    def load_existing_manual(self):
        if self.current is None:return
        n=self.roms[self.current]["name"]
        if n not in self.manual_remote:return messagebox.showinfo("수동 이미지","이 ROM에는 수동 JPG가 없습니다.")
        remote=self.paths()[1]+"/"+Path(n).stem+".jpg"; tmp=Path(tempfile.gettempdir())/"daijisho_existing.jpg"
        try:
            self.runadb(["pull",remote,str(tmp)]); im=Image.open(tmp); im.load(); self.choose_pil(im)
        except Exception as e:messagebox.showerror("불러오기 실패",str(e))

    def poll_clipboard(self):
        try:
            if not self.clipboard_busy:
                try:value=self.clipboard_get().strip()
                except:value=""
                if value and value!=self.clipboard_last:
                    self.clipboard_last=value
                    if re.match(r"^https?://",value,re.I):
                        self.clipboard_busy=True
                        threading.Thread(target=self._load_url,args=(value,),daemon=True).start()
                try:
                    clip=ImageGrab.grabclipboard()
                    if isinstance(clip,Image.Image):
                        sig=hashlib.sha1(clip.convert("RGB").resize((32,32)).tobytes()).hexdigest()
                        if sig!=self.clipboard_last:
                            self.clipboard_last=sig; self.choose_pil(clip.copy())
                            self.clip_status.set("✓ 복사한 이미지를 자동으로 가져왔습니다.")
                except:pass
        finally:self.after(900,self.poll_clipboard)

    def _load_url(self,url):
        try:
            r=requests.get(url,timeout=20,headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.google.com/"})
            r.raise_for_status()
            if "image" not in r.headers.get("content-type","").lower():raise ValueError()
            im=Image.open(io.BytesIO(r.content)); im.load(); cp=im.copy()
            self.after(0,lambda:self._accept_url(cp))
        except:self.after(0,lambda:self.clip_status.set("주소에서 이미지를 못 가져왔습니다. '이미지 복사'를 사용해 보세요."))
        finally:self.clipboard_busy=False

    def _accept_url(self,im):
        self.choose_pil(im); self.clip_status.set("✓ 이미지 주소 감지 완료. 미리보기 확인 후 전송하세요.")

    def apply_current(self):
        if self.current is None:return messagebox.showinfo("선택","ROM을 선택하세요.")
        if self.selected_image is None:return messagebox.showinfo("이미지","이미지를 선택하세요.")
        n=self.roms[self.current]["name"]; _,media,_=self.paths(); outfile=Path(n).stem+".jpg"
        tmp=Path(tempfile.gettempdir())/"daijisho_artwork_tmp.jpg"
        try:
            im=self.selected_image
            if im.mode in ("RGBA","LA"):
                bg=Image.new("RGB",im.size,"white"); bg.paste(im,mask=im.getchannel("A")); im=bg
            else:im=im.convert("RGB")
            im.save(tmp,"JPEG",quality=94,optimize=True); self.runadb(["shell","mkdir","-p",media])
            self.runadb(["push",str(tmp),media+"/"+outfile])
            self.manual_remote.add(n); self.state_db[self.key(n)]="manual"; self.cfg["rom_status"]=self.state_db; save_cfg(self.cfg)
            self.output.set(f"전송 완료: {media}/{outfile}"); self.refresh_tree(); self.current_state.set("상태: ★ 수동 이미지")
            self.status.set("전송 완료")
        except Exception as e:messagebox.showerror("전송 실패",str(e))

    def next_missing(self):
        if not self.roms:return
        start=(self.current+1) if self.current is not None else 0
        for i in list(range(start,len(self.roms)))+list(range(0,start)):
            if self.get_state(self.roms[i]["name"]) in ("unknown","missing"):
                self.tree.selection_set(str(i)); self.tree.see(str(i)); self.on_select(); return
        messagebox.showinfo("완료","미확인/보완 필요 ROM이 없습니다.")

if __name__=="__main__":
    App().mainloop()
