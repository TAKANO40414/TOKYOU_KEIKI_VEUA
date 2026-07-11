#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検品機データ ブラウザ
- 検品機保存フォルダ内の全日付フォルダを管理
- 品名検索（全ファイルをスキャン）
- 画像サムネイル一覧
"""

import tkinter as tk
from tkinter import ttk, messagebox
import zipfile
import xml.etree.ElementTree as ET
import os
import io
import re
import threading
from datetime import datetime
from PIL import Image, ImageTk

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
THUMB_W, THUMB_H = 160, 120

# =====================================================================
# データ解析
# =====================================================================

def _parse_diffgram(xml_bytes):
    root = ET.fromstring(xml_bytes)
    rows, headers, seen = [], [], False
    for child in root:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag != "diffgram":
            continue
        for dataset in child:
            for row_elem in dataset:
                row = {(f.tag.split("}")[-1] if "}" in f.tag else f.tag): (f.text or "")
                       for f in row_elem}
                if row:
                    if not seen:
                        headers = list(row.keys())
                        seen = True
                    rows.append(row)
    return headers, rows


def parse_pc5(path):
    tables, images = {}, {}
    with zipfile.ZipFile(path, "r") as z:
        for name in z.namelist():
            if name.endswith(".xml"):
                key = os.path.basename(name).replace(".xml", "")
                try:
                    h, r = _parse_diffgram(z.read(name))
                    tables[key] = {"headers": h, "rows": r}
                except Exception:
                    pass
            elif name.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                images[name] = z.read(name)
    return tables, images


def parse_filename(filename):
    base = os.path.basename(filename)
    m = re.match(r"(\d+)-#(\d+)@(\d{4}\w+\d+)-(\d+)h(\d+)m(\d+)", base)
    if m:
        return {"lot": m.group(1), "seq": int(m.group(2)),
                "date": m.group(3),
                "time": f"{m.group(4)}:{m.group(5)}:{m.group(6)}"}
    return {"lot": "", "seq": 0, "date": "", "time": ""}


def list_date_folders(root):
    result = []
    if not os.path.isdir(root):
        return result
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        if os.path.isdir(full) and not name.startswith("."):
            pc5s = [f for f in os.listdir(full) if f.lower().endswith(".pc5")]
            if pc5s:
                result.append({"name": name, "path": full, "count": len(pc5s)})
    return result


def list_pc5_files(folder):
    if not os.path.isdir(folder):
        return []
    files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".pc5"))
    result = []
    for f in files:
        meta = parse_filename(f)
        meta["filename"] = f
        meta["path"] = os.path.join(folder, f)
        result.append(meta)
    return result


def quick_product_name(path):
    try:
        with zipfile.ZipFile(path, "r") as z:
            if "LogTable.xml" in z.namelist():
                _, rows = _parse_diffgram(z.read("LogTable.xml"))
                if rows:
                    return rows[0].get("IdInfo_1", "")
    except Exception:
        pass
    return ""


# =====================================================================
# ウィジェット
# =====================================================================

class TableView(ttk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.tree = ttk.Treeview(self, show="headings", selectmode="browse")
        vsb = ttk.Scrollbar(self, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def load(self, headers, rows):
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = headers
        for h in headers:
            self.tree.heading(h, text=h)
            self.tree.column(h, width=max(80, min(200, len(h) * 10)), minwidth=50)
        for i, row in enumerate(rows):
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", "end",
                             values=[row.get(h, "") for h in headers],
                             tags=(tag,))
        self.tree.tag_configure("even", background="#f5f5f5")
        self.tree.tag_configure("odd",  background="#ffffff")


class SummaryPanel(ttk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.text = tk.Text(self, state="disabled", wrap="word",
                            font=("Helvetica", 13), bg="#fafafa",
                            relief="flat", padx=12, pady=12)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=vsb.set)
        self.text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.text.tag_configure("sec", font=("Helvetica", 14, "bold"),
                                foreground="#1a5276", spacing1=12, spacing3=4)
        self.text.tag_configure("key", font=("Helvetica", 12, "bold"),
                                foreground="#2c3e50")
        self.text.tag_configure("val", font=("Helvetica", 12),
                                foreground="#1a1a1a")

    def ins(self, text, tag):
        self.text.insert("end", text, tag)

    def load(self, tables, path):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")

        self.ins("■ ファイル情報\n", "sec")
        self.ins("  ファイル名: ", "key")
        self.ins(os.path.basename(path) + "\n", "val")

        mt = (tables.get("MachineTable", {}).get("rows") or [{}])[0]
        if mt:
            self.ins("\n■ 機械情報\n", "sec")
            for k, lbl in [("MachineID","機械ID"), ("MachineName","機械名"),
                            ("UserName","ユーザー名"),
                            ("SystemName0","システム0"), ("SystemName1","システム1")]:
                if mt.get(k):
                    self.ins(f"  {lbl}: ", "key"); self.ins(mt[k]+"\n", "val")

        lt = (tables.get("LogTable", {}).get("rows") or [{}])[0]
        if lt:
            self.ins("\n■ ジョブ情報\n", "sec")
            for k, lbl in [("IdInfo_0","ロット番号"), ("IdInfo_1","製品名"),
                            ("IdInfo_2","号機"), ("IdInfo_3","品番"),
                            ("IdInfo_4","FOR"), ("IdInfo_5","刷り面"),
                            ("IdInfo_6","得意先"), ("IdInfo_7","枚数")]:
                if lt.get(k):
                    self.ins(f"  {lbl}: ", "key"); self.ins(lt[k]+"\n", "val")

        ct = (tables.get("ChapterTable", {}).get("rows") or [{}])[0]
        if ct:
            self.ins("\n■ 検品情報\n", "sec")
            for k, lbl in [("BeginTime","開始時刻"), ("EndTime","終了時刻"),
                            ("Length","長さ(m)"),
                            ("DefectsR0","欠陥数R0"), ("DefectsR1","欠陥数R1")]:
                val = ct.get(k, "")
                if val and k in ("BeginTime", "EndTime"):
                    try:
                        val = datetime.fromisoformat(val).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pass
                if val:
                    self.ins(f"  {lbl}: ", "key"); self.ins(val+"\n", "val")

        et = (tables.get("EnvironmentTable", {}).get("rows") or [{}])[0]
        if et:
            self.ins("\n■ 環境設定\n", "sec")
            for k, lbl in [("Title","タイトル"), ("LutGain","LUTゲイン"),
                            ("SpeedWarningLevel","速度警告レベル")]:
                if et.get(k):
                    self.ins(f"  {lbl}: ", "key"); self.ins(et[k]+"\n", "val")

        self.text.configure(state="disabled")


class ImagePanel(ttk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        top = ttk.Frame(self)
        top.pack(fill="x", padx=4, pady=4)
        ttk.Label(top, text="画像:").pack(side="left")
        self.combo = ttk.Combobox(top, state="readonly", width=50)
        self.combo.pack(side="left", padx=4)
        self.combo.bind("<<ComboboxSelected>>", lambda _: self._show_selected())

        self.canvas = tk.Canvas(self, bg="#2b2b2b")
        vsb = ttk.Scrollbar(self, orient="vertical",   command=self.canvas.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.canvas.bind("<Configure>", lambda _: self._fit())

        self._images = {}
        self._raw = None
        self._photo = None

    def load(self, images):
        self._images = images
        keys = list(images.keys())
        self.combo["values"] = keys
        if keys:
            self.combo.current(0)
            self._show(keys[0])
        else:
            self.canvas.delete("all")
            self._raw = None

    def _show_selected(self):
        k = self.combo.get()
        if k:
            self._show(k)

    def _show(self, key):
        data = self._images.get(key)
        if data is None:
            return
        self._raw = Image.open(io.BytesIO(data))
        self._fit()

    def _fit(self):
        if self._raw is None:
            return
        cw = max(self.canvas.winfo_width(), 100)
        ch = max(self.canvas.winfo_height(), 100)
        iw, ih = self._raw.size
        scale = min(cw / iw, ch / ih, 1.0)
        nw, nh = int(iw * scale), int(ih * scale)
        resized = self._raw.resize((nw, nh), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(resized)
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self._photo, anchor="center")
        self.canvas.configure(scrollregion=(0, 0, cw, ch))


# =====================================================================
# メインアプリ
# =====================================================================

class PC5Browser(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("検品機データ ブラウザ")
        self.geometry("1400x860")
        self.minsize(900, 600)

        self._folders = []
        self._all_files = []
        self._current_folder = None
        self._gallery_loaded = False
        self._gallery_photos = []
        self._loading = False

        self._build_ui()

        # フォルダ一覧を読み込む
        self._load_folders()

    # ------------------------------------------------------------------
    def _build_ui(self):
        # ---- ツールバー ----
        tb = tk.Frame(self, bg="#1565c0", pady=6)
        tb.pack(fill="x")

        tk.Label(tb, text="検品機データ ブラウザ",
                 bg="#1565c0", fg="white",
                 font=("Helvetica", 16, "bold")).pack(side="left", padx=12)

        tk.Label(tb, text="品名検索:", bg="#1565c0", fg="white",
                 font=("Helvetica", 13)).pack(side="left", padx=(20, 4))
        self.search_var = tk.StringVar()
        search_e = tk.Entry(tb, textvariable=self.search_var,
                            font=("Helvetica", 13), width=26)
        search_e.pack(side="left")
        search_e.bind("<Return>", lambda _: self._search())

        tk.Button(tb, text="検索", font=("Helvetica", 12, "bold"),
                  command=self._search,
                  bg="#ffffff", fg="#1565c0", relief="flat",
                  padx=8, pady=2).pack(side="left", padx=4)
        tk.Button(tb, text="クリア", font=("Helvetica", 12),
                  command=self._clear_search,
                  bg="#bbdefb", fg="#1565c0", relief="flat",
                  padx=8, pady=2).pack(side="left")

        self.search_info = tk.StringVar(value="")
        tk.Label(tb, textvariable=self.search_info,
                 bg="#1565c0", fg="#fffde7",
                 font=("Helvetica", 11)).pack(side="left", padx=12)

        # ---- 3 ペイン ----
        main = tk.Frame(self)
        main.pack(fill="both", expand=True)

        # 左: フォルダ
        left = tk.Frame(main, width=200, bg="#eceff1")
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        self._build_folder_panel(left)

        # 区切り
        tk.Frame(main, width=1, bg="#b0bec5").pack(side="left", fill="y")

        # 中: ファイル
        mid = tk.Frame(main, width=270, bg="#fafafa")
        mid.pack(side="left", fill="y")
        mid.pack_propagate(False)
        self._build_file_panel(mid)

        # 区切り
        tk.Frame(main, width=1, bg="#b0bec5").pack(side="left", fill="y")

        # 右: 詳細
        right = tk.Frame(main, bg="#ffffff")
        right.pack(side="left", fill="both", expand=True)
        self._build_detail_panel(right)

        # ステータスバー
        self.status_var = tk.StringVar(value="起動完了")
        tk.Label(self, textvariable=self.status_var, relief="sunken",
                 anchor="w", font=("Helvetica", 11),
                 bg="#f5f5f5").pack(fill="x", side="bottom")

    def _build_folder_panel(self, parent):
        tk.Label(parent, text="日付フォルダ",
                 font=("Helvetica", 13, "bold"),
                 bg="#eceff1", fg="#1a237e").pack(pady=(8, 4), padx=8, anchor="w")

        frame = tk.Frame(parent, bg="#eceff1")
        frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.folder_lb = tk.Listbox(frame, font=("Helvetica", 13),
                                    selectmode="browse",
                                    activestyle="none",
                                    selectbackground="#1565c0",
                                    selectforeground="white",
                                    relief="flat", bd=0,
                                    bg="#eceff1")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.folder_lb.yview)
        self.folder_lb.configure(yscrollcommand=vsb.set)
        self.folder_lb.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.folder_lb.bind("<<ListboxSelect>>", self._on_folder_select)

    def _build_file_panel(self, parent):
        tk.Label(parent, text="ファイル一覧",
                 font=("Helvetica", 13, "bold"),
                 bg="#fafafa", fg="#1a237e").pack(pady=(8, 4), padx=8, anchor="w")

        frame = tk.Frame(parent, bg="#fafafa")
        frame.pack(fill="both", expand=True, padx=4, pady=4)

        cols = ("seq", "lot", "time")
        self.file_tree = ttk.Treeview(frame, columns=cols, show="headings",
                                      selectmode="browse", height=40)
        self.file_tree.heading("seq",  text="#")
        self.file_tree.heading("lot",  text="ロット番号")
        self.file_tree.heading("time", text="時刻")
        self.file_tree.column("seq",  width=38,  minwidth=30)
        self.file_tree.column("lot",  width=120, minwidth=80)
        self.file_tree.column("time", width=80,  minwidth=60)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=vsb.set)
        self.file_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.file_tree.bind("<<TreeviewSelect>>", self._on_file_select)
        self.file_tree.tag_configure("match", background="#fff9c4")

        self.file_count_var = tk.StringVar(value="")
        tk.Label(parent, textvariable=self.file_count_var,
                 font=("Helvetica", 11), fg="#555", bg="#fafafa").pack(pady=2)

    def _build_detail_panel(self, parent):
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True)

        self.summary = SummaryPanel(self.notebook)
        self.notebook.add(self.summary, text="  概要  ")

        self.tables = {}
        for key, lbl in [("LogTable","ログ"), ("ChapterTable","チャプター"),
                         ("EventTable","イベント"), ("DefectTable","欠陥"),
                         ("ResultTable","結果"), ("MachineTable","機械"),
                         ("EnvironmentTable","環境")]:
            tv = TableView(self.notebook)
            self.notebook.add(tv, text=f"  {lbl}  ")
            self.tables[key] = tv

        self.img_panel = ImagePanel(self.notebook)
        self.notebook.add(self.img_panel, text="  画像  ")

        # 画像一覧タブ
        self._gallery_frame = ttk.Frame(self.notebook)
        self.notebook.add(self._gallery_frame, text="  画像一覧  ")
        self._build_gallery_ui(self._gallery_frame)

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

    def _build_gallery_ui(self, parent):
        top = tk.Frame(parent)
        top.pack(fill="x", padx=6, pady=4)
        tk.Label(top, text="絞り込み:", font=("Helvetica", 12)).pack(side="left")
        self.gallery_search_var = tk.StringVar()
        self.gallery_search_var.trace_add("write", lambda *_: self._filter_gallery())
        tk.Entry(top, textvariable=self.gallery_search_var,
                 font=("Helvetica", 12), width=28).pack(side="left", padx=4)
        tk.Label(top, text="(品名・ファイル名で絞込)",
                 font=("Helvetica", 10), fg="#888").pack(side="left")
        self.gallery_count_var = tk.StringVar(value="")
        tk.Label(top, textvariable=self.gallery_count_var,
                 font=("Helvetica", 11), fg="#1565c0").pack(side="right")

        cont = tk.Frame(parent)
        cont.pack(fill="both", expand=True)

        self.gallery_canvas = tk.Canvas(cont, bg="#e0e0e0")
        vsb = ttk.Scrollbar(cont, orient="vertical", command=self.gallery_canvas.yview)
        self.gallery_canvas.configure(yscrollcommand=vsb.set)
        self.gallery_canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.gallery_canvas.bind("<MouseWheel>",
            lambda e: self.gallery_canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units"))
        self.gallery_canvas.bind("<Configure>", lambda _: self._relayout_gallery())

        self.gallery_inner = tk.Frame(self.gallery_canvas, bg="#e0e0e0")
        self._gallery_window = self.gallery_canvas.create_window(
            (0, 0), window=self.gallery_inner, anchor="nw")
        self.gallery_inner.bind("<Configure>", lambda e: self.gallery_canvas.configure(
            scrollregion=self.gallery_canvas.bbox("all")))

        self._gallery_all_items = []
        self._gallery_visible_items = []

    # ------------------------------------------------------------------
    # フォルダ読み込み
    # ------------------------------------------------------------------

    def _load_folders(self):
        self._folders = list_date_folders(ROOT_DIR)
        self.folder_lb.delete(0, "end")
        for f in self._folders:
            self.folder_lb.insert("end", f"  {f['name']}  ({f['count']}件)")
        if self._folders:
            self.folder_lb.selection_set(0)
            self.folder_lb.activate(0)
            self._load_folder(self._folders[0]["path"])

    def _on_folder_select(self, _event=None):
        sel = self.folder_lb.curselection()
        if not sel:
            return
        self._load_folder(self._folders[sel[0]]["path"])

    def _load_folder(self, path):
        self._current_folder = path
        self._all_files = list_pc5_files(path)
        self._render_file_list(self._all_files)
        self.search_var.set("")
        self.search_info.set("")
        self.status_var.set(f"フォルダ: {path}  ({len(self._all_files)} ファイル)")

        # 画像一覧はタブを開いたときに再生成
        self._gallery_loaded = False
        self._clear_gallery()

        if self._all_files:
            first = self._all_files[0]["path"]
            self.file_tree.selection_set(first)
            self.file_tree.see(first)
            self._load_pc5(first)

    # ------------------------------------------------------------------
    # ファイル読み込み
    # ------------------------------------------------------------------

    def _on_file_select(self, _event=None):
        sel = self.file_tree.selection()
        if sel:
            self._load_pc5(sel[0])

    def _load_pc5(self, path):
        if self._loading:
            return
        self._loading = True
        self.status_var.set(f"読み込み中: {os.path.basename(path)}")
        self.update_idletasks()

        def worker():
            try:
                tables, images = parse_pc5(path)
                self.after(0, lambda: self._apply_pc5(path, tables, images))
            except Exception as e:
                self.after(0, lambda: (
                    messagebox.showerror("エラー", f"読み込み失敗:\n{e}"),
                    setattr(self, "_loading", False)
                ))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_pc5(self, path, tables, images):
        self.summary.load(tables, path)
        for key, tv in self.tables.items():
            t = tables.get(key, {})
            tv.load(t.get("headers", []), t.get("rows", []))
        self.img_panel.load(images)
        self.status_var.set(f"表示中: {os.path.basename(path)}")
        self._loading = False

    # ------------------------------------------------------------------
    # ファイル一覧描画
    # ------------------------------------------------------------------

    def _render_file_list(self, files, highlight=None):
        self.file_tree.delete(*self.file_tree.get_children())
        hi = set(highlight or [])
        for f in files:
            tag = "match" if f["path"] in hi else ""
            self.file_tree.insert("", "end", iid=f["path"],
                                  values=(f"#{f['seq']}", f["lot"], f["time"]),
                                  tags=(tag,) if tag else ())
        self.file_count_var.set(f"合計 {len(files)} ファイル")

    # ------------------------------------------------------------------
    # 品名検索
    # ------------------------------------------------------------------

    def _search(self):
        kw = self.search_var.get().strip()
        if not kw:
            self._clear_search()
            return
        self.search_info.set("検索中...")
        self.update_idletasks()

        matched = []
        for f in self._all_files:
            product = quick_product_name(f["path"])
            if (kw.lower() in product.lower()
                    or kw.lower() in f["lot"].lower()
                    or kw.lower() in f["filename"].lower()):
                matched.append(f["path"])

        self._render_file_list(self._all_files, highlight=matched)

        if matched:
            self.search_info.set(f"「{kw}」→ {len(matched)} 件ヒット（黄色）")
            self.file_tree.selection_set(matched[0])
            self.file_tree.see(matched[0])
            self._load_pc5(matched[0])
        else:
            self.search_info.set(f"「{kw}」→ 該当なし")

    def _clear_search(self):
        self.search_var.set("")
        self.search_info.set("")
        self._render_file_list(self._all_files)

    # ------------------------------------------------------------------
    # 画像一覧（タブ切り替え時にロード）
    # ------------------------------------------------------------------

    def _on_tab_change(self, _event=None):
        try:
            cur = self.notebook.select()
            if cur == str(self._gallery_frame) and not self._gallery_loaded:
                self._gallery_loaded = True
                self._load_gallery()
        except Exception:
            pass

    def _load_gallery(self):
        self.gallery_count_var.set("読み込み中...")
        self.update_idletasks()

        files = self._all_files

        def worker():
            items = []
            for f in files:
                try:
                    with zipfile.ZipFile(f["path"], "r") as z:
                        img_names = [n for n in z.namelist()
                                     if n.lower().endswith((".png",".jpg",".jpeg",".bmp"))]
                        product = ""
                        if "LogTable.xml" in z.namelist():
                            try:
                                _, rows = _parse_diffgram(z.read("LogTable.xml"))
                                if rows:
                                    product = rows[0].get("IdInfo_1", "")
                            except Exception:
                                pass
                        for img_name in img_names:
                            raw = z.read(img_name)
                            img = Image.open(io.BytesIO(raw))
                            img.thumbnail((THUMB_W, THUMB_H), Image.LANCZOS)
                            items.append({
                                "img": img,
                                "path": f["path"],
                                "filename": f["filename"],
                                "img_name": img_name,
                                "lot": f.get("lot", ""),
                                "seq": f.get("seq", 0),
                                "product": product,
                            })
                except Exception:
                    pass
            self.after(0, lambda: self._finish_gallery(items))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_gallery(self, items):
        self._gallery_all_items = items
        self.gallery_search_var.set("")
        self._filter_gallery()

    def _filter_gallery(self):
        kw = self.gallery_search_var.get().strip().lower()
        if kw:
            self._gallery_visible_items = [
                it for it in self._gallery_all_items
                if kw in it["filename"].lower()
                or kw in it["product"].lower()
                or kw in it["lot"].lower()
                or kw in it["img_name"].lower()
            ]
        else:
            self._gallery_visible_items = list(self._gallery_all_items)
        self._relayout_gallery()

    def _relayout_gallery(self):
        for w in self.gallery_inner.winfo_children():
            w.destroy()
        self._gallery_photos.clear()

        items = self._gallery_visible_items
        self.gallery_count_var.set(f"{len(items)} 枚")

        cw = self.gallery_canvas.winfo_width()
        cols = max(1, cw // (THUMB_W + 20))

        for idx, it in enumerate(items):
            r, c = divmod(idx, cols)
            photo = ImageTk.PhotoImage(it["img"])
            self._gallery_photos.append(photo)

            cell = tk.Frame(self.gallery_inner, bg="#ffffff",
                            relief="solid", bd=1)
            cell.grid(row=r, column=c, padx=6, pady=6, sticky="nw")

            img_lbl = tk.Label(cell, image=photo, bg="#ffffff", cursor="hand2")
            img_lbl.pack()
            img_lbl.bind("<Button-1>", lambda e, p=it["path"]: self._gallery_click(p))

            tk.Label(cell, text=f"#{it['seq']}  {it['lot']}",
                     font=("Helvetica", 10, "bold"),
                     fg="#1565c0", bg="#ffffff").pack()
            if it["product"]:
                tk.Label(cell, text=it["product"],
                         font=("Helvetica", 9), fg="#555", bg="#ffffff").pack()

    def _clear_gallery(self):
        for w in self.gallery_inner.winfo_children():
            w.destroy()
        self._gallery_photos.clear()
        self._gallery_all_items = []
        self._gallery_visible_items = []
        self.gallery_count_var.set("")

    def _gallery_click(self, path):
        """サムネイルクリック → 概要タブでそのファイルを表示"""
        if self.file_tree.exists(path):
            self.file_tree.selection_set(path)
            self.file_tree.see(path)
        self.notebook.select(0)
        self._load_pc5(path)


# =====================================================================
# 起動
# =====================================================================

if __name__ == "__main__":
    app = PC5Browser()
    app.mainloop()
