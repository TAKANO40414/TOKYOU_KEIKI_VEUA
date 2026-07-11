#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PC5 ファイルビューア
検品機データ (.pc5) を閲覧するアプリケーション
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import zipfile
import xml.etree.ElementTree as ET
import os
import io
import re
from datetime import datetime
from PIL import Image, ImageTk


# ===== データ解析 =====

def parse_diffgram_rows(xml_bytes):
    """diffgramフォーマットのXMLからデータ行を抽出"""
    root = ET.fromstring(xml_bytes)

    rows = []
    headers = []
    seen_headers = False

    # <DataTable> → <diffgram> → <Dataset> → <Row>
    for child in root:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag != "diffgram":
            continue
        for dataset in child:
            for row_elem in dataset:
                row = {}
                for field in row_elem:
                    ftag = field.tag.split("}")[-1] if "}" in field.tag else field.tag
                    row[ftag] = field.text or ""
                if row:
                    if not seen_headers:
                        headers = list(row.keys())
                        seen_headers = True
                    rows.append(row)

    return headers, rows


def parse_pc5(path):
    """PC5ファイルを解析して全テーブルを返す"""
    tables = {}
    images = {}

    with zipfile.ZipFile(path, "r") as z:
        for name in z.namelist():
            if name.endswith(".xml"):
                data = z.read(name)
                key = os.path.basename(name).replace(".xml", "")
                headers, rows = parse_diffgram_rows(data)
                tables[key] = {"headers": headers, "rows": rows}
            elif name.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                images[name] = z.read(name)

    return tables, images


def parse_filename(filename):
    """ファイル名からメタ情報を抽出"""
    base = os.path.basename(filename)
    m = re.match(r"(\d+)-#(\d+)@(\d{4}\w+\d+)-(\d+)h(\d+)m(\d+)", base)
    if m:
        lot = m.group(1)
        seq = m.group(2)
        date_str = m.group(3)
        h, mi, s = m.group(4), m.group(5), m.group(6)
        return {
            "lot": lot,
            "seq": int(seq),
            "date_str": date_str,
            "time_str": f"{h}:{mi}:{s}",
            "display": f"#{seq}  {date_str} {h}:{mi}:{s}  [Lot:{lot}]",
        }
    return {"lot": "", "seq": 0, "date_str": "", "time_str": "", "display": base}


# ===== GUIウィジェット =====

class TableView(ttk.Frame):
    """汎用テーブル表示ウィジェット"""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self._build()

    def _build(self):
        self.tree = ttk.Treeview(self, show="headings", selectmode="browse")
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
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
            width = max(80, min(200, len(h) * 10))
            self.tree.column(h, width=width, minwidth=50)
        for i, row in enumerate(rows):
            values = [row.get(h, "") for h in headers]
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", "end", values=values, tags=(tag,))
        self.tree.tag_configure("even", background="#f5f5f5")
        self.tree.tag_configure("odd", background="#ffffff")


class ImagePanel(ttk.Frame):
    """画像表示パネル"""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self._build()
        self._images = {}
        self._current_raw = None
        self._photo = None

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=4, pady=4)
        ttk.Label(top, text="画像:").pack(side="left")
        self.combo = ttk.Combobox(top, state="readonly", width=40)
        self.combo.pack(side="left", padx=4)
        self.combo.bind("<<ComboboxSelected>>", self._on_select)

        self.canvas = tk.Canvas(self, bg="#2b2b2b")
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.canvas.bind("<Configure>", self._fit)

    def load(self, images):
        self._images = images
        keys = list(images.keys())
        self.combo["values"] = keys
        if keys:
            self.combo.current(0)
            self._show(keys[0])
        else:
            self.canvas.delete("all")
            self._current_raw = None

    def _on_select(self, _event):
        key = self.combo.get()
        if key:
            self._show(key)

    def _show(self, key):
        data = self._images.get(key)
        if data is None:
            return
        img = Image.open(io.BytesIO(data))
        self._current_raw = img
        self._render(img)

    def _fit(self, _event=None):
        if self._current_raw:
            self._render(self._current_raw)

    def _render(self, img):
        cw = max(self.canvas.winfo_width(), 100)
        ch = max(self.canvas.winfo_height(), 100)
        iw, ih = img.size
        scale = min(cw / iw, ch / ih, 1.0)
        nw, nh = int(iw * scale), int(ih * scale)
        resized = img.resize((nw, nh), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(resized)
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self._photo, anchor="center")
        self.canvas.configure(scrollregion=(0, 0, cw, ch))


class SummaryPanel(ttk.Frame):
    """概要パネル（主要項目を一覧表示）"""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.text = tk.Text(self, state="disabled", wrap="word",
                            font=("Helvetica", 13), bg="#fafafa",
                            relief="flat", padx=10, pady=10)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=vsb.set)
        self.text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.text.tag_configure("section", font=("Helvetica", 14, "bold"),
                                foreground="#1a5276", spacing1=12, spacing3=4)
        self.text.tag_configure("key", font=("Helvetica", 12, "bold"),
                                foreground="#2c3e50")
        self.text.tag_configure("value", font=("Helvetica", 12),
                                foreground="#1a1a1a")

    def _write(self, text, *tags):
        self.text.insert("end", text, tags)

    def load(self, tables, filename):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")

        meta = parse_filename(filename)
        self._write("■ ファイル情報\n", "section")
        self._write("  ファイル名: ", "key")
        self._write(f"{os.path.basename(filename)}\n", "value")

        # --- Machine ---
        mt = tables.get("MachineTable", {})
        rows = mt.get("rows", [])
        if rows:
            r = rows[0]
            self._write("\n■ 機械情報\n", "section")
            for k, label in [("MachineID", "機械ID"), ("MachineName", "機械名"),
                              ("UserName", "ユーザー名"), ("SystemName0", "システム0"),
                              ("SystemName1", "システム1")]:
                if k in r:
                    self._write(f"  {label}: ", "key")
                    self._write(f"{r[k]}\n", "value")

        # --- Log ---
        lt = tables.get("LogTable", {})
        rows = lt.get("rows", [])
        if rows:
            r = rows[0]
            self._write("\n■ ジョブ情報\n", "section")
            id_labels = {
                "IdInfo_0": "ロット番号", "IdInfo_1": "製品名",
                "IdInfo_2": "号機", "IdInfo_3": "品番",
                "IdInfo_4": "FOR", "IdInfo_5": "刷り面",
                "IdInfo_6": "得意先", "IdInfo_7": "枚数",
            }
            for k, label in id_labels.items():
                if k in r and r[k]:
                    self._write(f"  {label}: ", "key")
                    self._write(f"{r[k]}\n", "value")

        # --- Chapter ---
        ct = tables.get("ChapterTable", {})
        rows = ct.get("rows", [])
        if rows:
            r = rows[0]
            self._write("\n■ 検品情報\n", "section")
            for k, label in [("BeginTime", "開始時刻"), ("EndTime", "終了時刻"),
                              ("Length", "長さ(m)"), ("DefectsR0", "欠陥数R0"),
                              ("DefectsR1", "欠陥数R1")]:
                if k in r:
                    val = r[k]
                    if k in ("BeginTime", "EndTime") and val:
                        try:
                            dt = datetime.fromisoformat(val)
                            val = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            pass
                    self._write(f"  {label}: ", "key")
                    self._write(f"{val}\n", "value")

        # --- Environment ---
        et = tables.get("EnvironmentTable", {})
        rows = et.get("rows", [])
        if rows:
            r = rows[0]
            self._write("\n■ 環境設定\n", "section")
            for k, label in [("Title", "タイトル"), ("LutGain", "LUTゲイン"),
                              ("SpeedWarningLevel", "速度警告レベル")]:
                if k in r:
                    self._write(f"  {label}: ", "key")
                    self._write(f"{r[k]}\n", "value")

        self.text.configure(state="disabled")


# ===== メインアプリ =====

class PC5Viewer(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("PC5 ファイルビューア  ─  検品機データ閲覧")
        self.geometry("1280x800")
        self.minsize(900, 600)
        self._files = []
        self._current_path = None
        self._build_ui()
        self._apply_style()

    def _apply_style(self):
        style = ttk.Style(self)
        style.theme_use("aqua")
        style.configure("Treeview", rowheight=22, font=("Helvetica", 12))
        style.configure("Treeview.Heading", font=("Helvetica", 12, "bold"))
        style.configure("TNotebook.Tab", font=("Helvetica", 12), padding=[8, 4])

    def _build_ui(self):
        # ---- メニュー ----
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="フォルダを開く...", command=self._open_folder,
                             accelerator="Cmd+O")
        filemenu.add_separator()
        filemenu.add_command(label="終了", command=self.quit)
        menubar.add_cascade(label="ファイル", menu=filemenu)
        self.config(menu=menubar)
        self.bind("<Command-o>", lambda _: self._open_folder())

        # ---- レイアウト ----
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=6, pady=6)

        # 左: ファイルリスト
        left = ttk.Frame(paned, width=280)
        paned.add(left, weight=0)
        self._build_file_list(left)

        # 右: タブ表示
        right = ttk.Frame(paned)
        paned.add(right, weight=1)
        self._build_detail(right)

        # ---- ステータスバー ----
        self.status_var = tk.StringVar(value="フォルダを開いてください  (メニュー → ファイル → フォルダを開く)")
        sb = ttk.Label(self, textvariable=self.status_var, relief="sunken",
                       anchor="w", font=("Helvetica", 11))
        sb.pack(fill="x", side="bottom", padx=4, pady=2)

    def _build_file_list(self, parent):
        ttk.Label(parent, text="PC5 ファイル一覧", font=("Helvetica", 13, "bold")).pack(
            pady=(4, 2), padx=4, anchor="w")

        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, padx=4, pady=4)

        cols = ("#seq", "#lot", "#time")
        self.file_tree = ttk.Treeview(frame, columns=cols, show="headings",
                                      selectmode="browse")
        self.file_tree.heading("#seq", text="#")
        self.file_tree.heading("#lot", text="ロット番号")
        self.file_tree.heading("#time", text="時刻")
        self.file_tree.column("#seq", width=36, minwidth=30)
        self.file_tree.column("#lot", width=100, minwidth=80)
        self.file_tree.column("#time", width=100, minwidth=80)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=vsb.set)
        self.file_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.file_tree.bind("<<TreeviewSelect>>", self._on_file_select)

        self.file_count_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.file_count_var,
                  font=("Helvetica", 11), foreground="#555").pack(pady=2)

    def _build_detail(self, parent):
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True)

        # 概要タブ
        self.summary_panel = SummaryPanel(self.notebook)
        self.notebook.add(self.summary_panel, text="  概要  ")

        # 各テーブルタブ
        self.table_views = {}
        tab_defs = [
            ("LogTable",         "ログ"),
            ("ChapterTable",     "チャプター"),
            ("EventTable",       "イベント"),
            ("DefectTable",      "欠陥"),
            ("ResultTable",      "結果"),
            ("MachineTable",     "機械"),
            ("EnvironmentTable", "環境"),
        ]
        for key, label in tab_defs:
            tv = TableView(self.notebook)
            self.notebook.add(tv, text=f"  {label}  ")
            self.table_views[key] = tv

        # 画像タブ
        self.image_panel = ImagePanel(self.notebook)
        self.notebook.add(self.image_panel, text="  画像  ")

    # ---- 操作 ----

    def _open_folder(self):
        folder = filedialog.askdirectory(title="PC5ファイルが入ったフォルダを選択")
        if not folder:
            return
        files = sorted([
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith(".pc5")
        ])
        if not files:
            messagebox.showinfo("情報", "PC5ファイルが見つかりませんでした。")
            return
        self._load_file_list(files)

    def _load_file_list(self, files):
        self._files = files
        self.file_tree.delete(*self.file_tree.get_children())
        for path in files:
            meta = parse_filename(path)
            self.file_tree.insert("", "end", iid=path,
                                  values=(f"#{meta['seq']}", meta["lot"],
                                          meta["time_str"]))
        self.file_count_var.set(f"合計 {len(files)} ファイル")
        self.status_var.set(f"フォルダ: {os.path.dirname(files[0])}")
        if files:
            self.file_tree.selection_set(files[0])
            self.file_tree.focus(files[0])
            self._load_pc5(files[0])

    def _on_file_select(self, _event):
        sel = self.file_tree.selection()
        if sel:
            self._load_pc5(sel[0])

    def _load_pc5(self, path):
        self._current_path = path
        self.status_var.set(f"読み込み中: {os.path.basename(path)}")
        self.update_idletasks()
        try:
            tables, images = parse_pc5(path)
        except Exception as e:
            messagebox.showerror("エラー", f"ファイルの読み込みに失敗しました:\n{e}")
            return

        # 概要
        self.summary_panel.load(tables, path)

        # テーブルビュー
        for key, tv in self.table_views.items():
            t = tables.get(key, {})
            tv.load(t.get("headers", []), t.get("rows", []))

        # 画像
        self.image_panel.load(images)

        self.status_var.set(f"表示中: {os.path.basename(path)}")


if __name__ == "__main__":
    app = PC5Viewer()
    app.mainloop()
