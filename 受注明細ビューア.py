#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""受注明細一覧ビューア - 得意先別・納期順ソート"""

import csv
import os
import sys
import webbrowser
import html as html_mod
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox

CSV_PATH = os.path.expanduser("~/Desktop/受注明細一覧_20260620.csv")

KANRYO_COL = 54  # 最終納品日

PROCESS_DEFS = [
    {'name': 14 + i * 4, 'machine': 15 + i * 4, 'date': 16 + i * 4, 'count': 17 + i * 4}
    for i in range(10)
]

def get(row, idx, default=''):
    try:
        return row[idx].strip()
    except IndexError:
        return default

def esc(s):
    return html_mod.escape(str(s))

def read_csv(path):
    for enc in ('utf-8-sig', 'cp932', 'utf-8', 'shift-jis'):
        try:
            with open(path, 'r', encoding=enc) as f:
                reader = csv.reader(f)
                headers = next(reader)
                rows = [row for row in reader if any(c.strip() for c in row)]
            return headers, rows
        except (UnicodeDecodeError, UnicodeError):
            continue
    # どのエンコーディングでも読めない場合はreplaceで強行
    with open(path, 'r', encoding='cp932', errors='replace') as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = [row for row in reader if any(c.strip() for c in row)]
    return headers, rows

def format_amount(s):
    try:
        return f'{int(s.strip()):,}'
    except Exception:
        return s

def proc_class(date):
    if not date:
        return 'proc-mi'
    if '完' in date or '確' in date:
        return 'proc-done'   # 完了・確定 → 赤
    if '進' in date:
        return 'proc-shin'   # 進行中 → オレンジ
    return 'proc-mi'         # 未・削・その他 → グレー

def build_process_html(row):
    parts = []
    for p in PROCESS_DEFS:
        name = get(row, p['name'])
        if not name:
            continue
        date = get(row, p['date'])
        machine = get(row, p['machine'])
        cls = proc_class(date)
        title = esc(machine) if machine else ''
        date_span = f'<span class="proc-date">{esc(date)}</span>' if date else ''
        parts.append(
            f'<span class="proc {cls}" title="{title}">'
            f'{esc(name)}{date_span}'
            f'</span>'
        )
    return ''.join(parts) if parts else '<span class="no-proc">-</span>'

def build_rows_html(rows, tanto_col=-1):
    def sort_key(row):
        return (get(row, 2), get(row, 10))

    sorted_rows = sorted(rows, key=sort_key)
    parts = []
    for row in sorted_rows:
        kanryo = get(row, KANRYO_COL)
        # アクティブな工程（工程名あり）の完了日リスト
        active_dates = [get(row, 16 + i * 4) for i in range(10) if get(row, 14 + i * 4)]
        # 「未」が一つでもあれば完了にしない
        has_mi = any('未' in d for d in active_dates)
        # 最終納品日あり、またはすべての工程が「完」なら完了
        all_kan = bool(active_dates) and all('完' in d for d in active_dates)
        is_done = (bool(kanryo) or all_kan) and not has_mi

        raw_no = get(row, 0)
        # 0000123456-000 → 6桁を大きく、-000を2行目右寄せ
        if '-' in raw_no:
            prefix, suffix = raw_no.split('-', 1)
            main = str(int(prefix)) if prefix.isdigit() else prefix
            juchu_no = f'<span class="no-main">{esc(main)}</span><span class="no-sub">{esc(suffix)}</span>'
        else:
            juchu_no = f'<span class="no-main">{esc(raw_no)}</span>'
        juchu_date  = esc(get(row, 1))
        customer    = esc(get(row, 2))
        product1    = esc(get(row, 4))
        product2    = esc(get(row, 5))
        qty         = esc(format_amount(get(row, 6)))
        unit        = esc(get(row, 7))
        amount      = format_amount(get(row, 9))
        delivery    = esc(get(row, 10))
        d_reply     = esc(get(row, 11))
        version     = esc(get(row, 12))
        nyuhi       = esc(get(row, 13))
        kanryo_esc  = esc(kanryo)
        state1      = esc(get(row, 57))
        state2      = esc(get(row, 58))

        proc_html   = build_process_html(row)
        row_cls     = 'done' if is_done else ''
        done_attr   = '1' if is_done else '0'
        proc1_val   = esc(get(row, 14))

        p2 = f'<br><small class="product2">{product2}</small>' if product2 else ''
        tanto_val = esc(get(row, tanto_col)) if tanto_col >= 0 else ''
        tanto_td = f'<td class="td-tanto"><span class="tanto-badge">{tanto_val}</span></td>' if tanto_col >= 0 else ''

        parts.append(f'''
<tr class="{row_cls}" data-done="{done_attr}" data-proc1="{proc1_val}">
  <td class="td-no">{juchu_no}</td>
  <td class="td-date">{juchu_date}</td>
  <td class="td-customer">{customer}</td>
  {tanto_td}
  <td class="td-product">{product1}{p2}</td>
  <td class="td-qty">{qty}<span class="unit">{unit}</span></td>
  <td class="td-delivery">{delivery}</td>
  <td class="td-reply">{d_reply}</td>
  <td class="td-version">{version}</td>
  <td class="td-process">{proc_html}</td>
  <td class="td-kanryo">{kanryo_esc}</td>
</tr>''')

    return '\n'.join(parts)

def generate_html(csv_path):
    headers, rows = read_csv(csv_path)
    filename = os.path.basename(csv_path)

    # 担当者列を検出
    tanto_col = next((i for i, h in enumerate(headers) if '担当' in h), -1)
    has_tanto = tanto_col >= 0

    rows_html = build_rows_html(rows, tanto_col)
    total = len(rows)

    done_count = sum(1 for r in rows if get(r, KANRYO_COL))

    tanto_th = '<th>担当</th>' if has_tanto else ''
    has_tanto_js = 'true' if has_tanto else 'false'
    tanto_col_js = tanto_col
    _o = 1 if has_tanto else 0  # column offset when tanto exists
    col_product  = 3 + _o
    col_qty      = 4 + _o
    col_delivery = 5 + _o
    col_kanryo   = 9 + _o

    # 工程１の選択肢（ソート済み・重複なし）
    proc1_values = sorted(set(get(r, 14) for r in rows if get(r, 14)))
    proc1_options = '<option value="">すべて</option>' + ''.join(
        f'<option value="{esc(v)}">{esc(v)}</option>' for v in proc1_values
    )

    return f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>受注明細一覧 | {esc(filename)}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", sans-serif;
  font-size: 13px;
  background: #eaeded;
  color: #0f1111;
}}
header {{
  background: #232f3e;
  color: #fff;
  padding: 10px 24px;
  display: flex;
  align-items: center;
  gap: 20px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 6px rgba(0,0,0,.4);
}}
header h1 {{
  font-size: 17px;
  font-weight: 700;
  letter-spacing: .5px;
  flex: 1;
}}
.stats {{ font-size: 12px; color: #febd69; white-space: nowrap; }}
.controls {{
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 24px;
  background: #fff;
  border-bottom: 1px solid #ddd;
  flex-wrap: wrap;
  box-shadow: 0 1px 3px rgba(0,0,0,.07);
  position: sticky;
  top: 46px;
  z-index: 99;
}}
.btn {{
  padding: 5px 13px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 12px;
  font-family: inherit;
  font-weight: 600;
  border: 1px solid;
  transition: filter .1s;
  white-space: nowrap;
}}
.btn:hover {{ filter: brightness(.92); }}
.btn-load {{
  background: #FF9900;
  border-color: #E47911;
  color: #111;
}}
.btn-hide {{
  background: #fff3f3;
  border-color: #e57373;
  color: #c0392b;
}}
.btn-show {{
  background: #f0f8ff;
  border-color: #5b9bd5;
  color: #007185;
}}
.btn-all {{
  background: #f7f7f7;
  border-color: #bbb;
  color: #444;
}}
.btn-sort-delivery {{
  background: #f0faf0;
  border-color: #6abf69;
  color: #1e7e34;
}}
.btn-sort-default {{
  background: #f5f0ff;
  border-color: #9b73d8;
  color: #5a3e82;
}}
.sep {{ width: 1px; height: 22px; background: #ddd; display: inline-block; flex-shrink: 0; }}
.search-box {{
  padding: 5px 10px;
  border: 1px solid #aaa;
  border-radius: 3px;
  font-size: 12px;
  width: 210px;
  background: #fff;
  color: #0f1111;
}}
.search-box:focus {{ outline: none; border-color: #FF9900; box-shadow: 0 0 0 2px rgba(255,153,0,.2); }}
.count-info {{
  font-size: 12px;
  color: #767676;
  margin-left: auto;
  white-space: nowrap;
}}
.table-wrap {{
  overflow-x: auto;
  padding: 14px 24px 40px;
}}
table {{
  border-collapse: collapse;
  width: 100%;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,.1);
  border-radius: 4px;
  overflow: hidden;
  font-size: 12px;
}}
thead tr {{
  background: #f3f3f3;
  color: #0f1111;
  text-align: left;
  border-bottom: 2px solid #ddd;
}}
thead th {{
  padding: 9px 11px;
  font-weight: 700;
  font-size: 11.5px;
  letter-spacing: .2px;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  border-right: 1px solid #e0e0e0;
}}
thead th:last-child {{ border-right: none; }}
thead th:hover {{ background: #e8e8e8; }}
thead th.sort-asc::after {{ content: " ▲"; font-size: 9px; color: #007185; }}
thead th.sort-desc::after {{ content: " ▼"; font-size: 9px; color: #007185; }}
tbody tr {{
  border-bottom: 1px solid #f0f0f0;
  transition: background .1s;
}}
tbody tr:nth-child(even) {{ background: #fafafa; }}
tbody tr:hover {{ background: #f0f7ff !important; }}
tbody tr.done {{
  background: #f0faf0;
}}
tbody tr.done:nth-child(even) {{ background: #e8f5e8; }}
tbody tr.done td {{ color: #2d7a2d; }}
tbody tr.done .td-kanryo {{
  color: #27ae60;
  font-weight: 700;
}}
tbody tr.done:hover {{ background: #d8f0d8 !important; }}
td {{
  padding: 8px 11px;
  vertical-align: top;
  border-right: 1px solid #f0f0f0;
}}
td:last-child {{ border-right: none; }}
.td-no {{ white-space: nowrap; font-family: monospace; text-align: right; }}
.no-main {{ font-size: 14px; font-weight: 700; color: #007185; display: block; text-align: right; }}
.no-sub  {{ font-size: 12px; font-weight: 600; color: #aaa; display: block; text-align: right; }}
.td-date {{ white-space: nowrap; color: #555; font-size: 11px; }}
.td-customer {{ font-weight: 700; white-space: nowrap; min-width: 120px; color: #0f1111; }}
.td-tanto {{ white-space: nowrap; min-width: 60px; text-align: center; }}
.tanto-badge {{
  display: inline-block;
  padding: 2px 9px;
  border-radius: 12px;
  background: #e8f4fd;
  color: #1a6fa8;
  font-size: 11px;
  font-weight: 700;
  border: 1px solid #b8d9f0;
}}
.td-product {{ min-width: 160px; max-width: 240px; }}
.product2 {{ color: #999; font-size: 10px; }}
.td-qty {{ white-space: nowrap; text-align: right; }}
.unit {{ color: #999; margin-left: 2px; font-size: 11px; }}
.td-delivery {{ white-space: nowrap; font-weight: 700; color: #c0392b; }}
.td-reply {{ white-space: nowrap; color: #555; }}
.td-version {{ white-space: nowrap; color: #555; }}
.td-process {{ min-width: 200px; max-width: 380px; }}
.td-kanryo {{ white-space: nowrap; min-width: 90px; }}
.proc {{
  display: inline-block;
  font-size: 10.5px;
  padding: 2px 8px;
  border-radius: 10px;
  margin: 2px 2px 2px 0;
  line-height: 1.6;
  white-space: nowrap;
  font-weight: 600;
}}
.proc-done {{
  background: #fde8e8;
  color: #c0392b;
  border: 1px solid #f5a8a8;
}}
.proc-shin {{
  background: #fff4e0;
  color: #b45309;
  border: 1px solid #f6c975;
}}
.proc-mi {{
  background: #f3f3f3;
  color: #767676;
  border: 1px solid #ccc;
}}
.proc-date {{
  display: block;
  font-size: 9px;
  color: #999;
  margin-top: 1px;
  font-weight: 400;
}}
.no-proc {{ color: #ccc; font-size: 11px; }}
</style>
</head>
<body>
<header>
  <h1>受注明細一覧</h1>
  <span class="stats">全 {total} 件 &nbsp;｜&nbsp; 完了 {done_count} 件 &nbsp;｜&nbsp; 進行中 {total - done_count} 件</span>
  <span style="font-size:11px;color:#febd69;opacity:.7;">{esc(filename)}</span>
</header>
<div class="controls">
  <label class="btn btn-load" style="cursor:pointer;">
    📂 CSV読込
    <input type="file" id="csvFileInput" accept=".csv" onchange="onCsvSelected(event)" style="display:none;">
  </label>
  <span class="sep"></span>
  <button class="btn btn-hide" onclick="hideDone()">完了を非表示</button>
  <button class="btn btn-show" onclick="showDone()">完了のみ表示</button>
  <button class="btn btn-all" onclick="showAll()">すべて表示</button>
  <span class="sep"></span>
  <button class="btn btn-sort-delivery" onclick="sortByDelivery()">納期順 ↑</button>
  <button class="btn btn-sort-default" onclick="sortByDefault()">得意先＋納期順</button>
  <span class="sep"></span>
  <label style="font-size:12px;color:#444;display:flex;align-items:center;gap:5px;">
    工程１
    <select id="proc1Select" onchange="applyFilters()" style="padding:4px 8px;border:1px solid #aaa;border-radius:3px;font-size:12px;font-family:inherit;background:#fff;color:#0f1111;">
      {proc1_options}
    </select>
  </label>
  <span class="sep"></span>
  <input class="search-box" type="text" id="searchBox" placeholder="得意先・製品名で検索..." oninput="filterTable()">
  <span class="count-info" id="countInfo">表示中: {total} 件</span>
</div>
<div class="table-wrap">
<table id="mainTable">
<thead>
<tr>
  <th onclick="sortTable(0)">受注No</th>
  <th onclick="sortTable(1)">受注日</th>
  <th onclick="sortTable(2)">得意先</th>
  {tanto_th}
  <th onclick="sortTable({col_product})">製品名</th>
  <th onclick="sortTable({col_qty})">数量</th>
  <th onclick="sortTable({col_delivery})">納期</th>
  <th>納期返事</th>
  <th>版区</th>
  <th>工程進捗</th>
  <th onclick="sortTable({col_kanryo})">最終納品日</th>
</tr>
</thead>
<tbody id="tableBody">
{rows_html}
</tbody>
</table>
</div>
<script>
// 担当列の有無に応じた列インデックス
const HAS_TANTO   = {has_tanto_js};
const TANTO_CSV   = {tanto_col_js};  // CSVの元列番号（-1=なし）
const COL_DELIVERY = {col_delivery};
const COL_CUSTOMER = 2;
const COL_KANRYO   = {col_kanryo};

let doneFilter = 'all'; // 'all' | 'hide_done' | 'only_done'
let searchText = '';

function hideDone() {{
  doneFilter = 'hide_done';
  applyFilters();
}}
function showDone() {{
  doneFilter = 'only_done';
  applyFilters();
}}
function showAll() {{
  doneFilter = 'all';
  searchText = '';
  document.getElementById('searchBox').value = '';
  document.getElementById('proc1Select').value = '';
  applyFilters();
}}
function filterTable() {{
  searchText = document.getElementById('searchBox').value.toLowerCase();
  applyFilters();
}}

function applyFilters() {{
  const proc1Filter = document.getElementById('proc1Select').value;
  const rows = document.querySelectorAll('#tableBody tr');
  let visible = 0;
  rows.forEach(tr => {{
    const done = tr.dataset.done === '1';
    const text = tr.textContent.toLowerCase();
    const proc1 = tr.dataset.proc1 || '';
    const matchSearch = !searchText || text.includes(searchText);
    const matchDone = doneFilter === 'all' ||
                      (doneFilter === 'hide_done' && !done) ||
                      (doneFilter === 'only_done' && done);
    const matchProc1 = !proc1Filter || proc1 === proc1Filter;
    const show = matchSearch && matchDone && matchProc1;
    tr.style.display = show ? '' : 'none';
    if (show) visible++;
  }});
  document.getElementById('countInfo').textContent = '表示中: ' + visible + ' 件';
}}

let sortCol = -1;
let sortAsc = true;

function sortTable(col) {{
  const tbody = document.getElementById('tableBody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const ths = document.querySelectorAll('thead th');

  if (sortCol === col) {{
    sortAsc = !sortAsc;
  }} else {{
    sortCol = col;
    sortAsc = true;
  }}

  ths.forEach((th, i) => {{
    th.classList.remove('sort-asc', 'sort-desc');
    if (i === col) th.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');
  }});

  rows.sort((a, b) => {{
    const av = a.cells[col] ? a.cells[col].textContent.trim() : '';
    const bv = b.cells[col] ? b.cells[col].textContent.trim() : '';
    const cmp = av.localeCompare(bv, 'ja', {{numeric: true}});
    return sortAsc ? cmp : -cmp;
  }});

  rows.forEach(r => tbody.appendChild(r));
  applyFilters();
}}

function sortByDelivery() {{
  const tbody = document.getElementById('tableBody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const ths = document.querySelectorAll('thead th');
  ths.forEach(th => th.classList.remove('sort-asc', 'sort-desc'));
  if (ths[COL_DELIVERY]) ths[COL_DELIVERY].classList.add('sort-asc');
  sortCol = COL_DELIVERY;
  sortAsc = true;
  rows.sort((a, b) => {{
    const av = a.cells[COL_DELIVERY] ? a.cells[COL_DELIVERY].textContent.trim() : '';
    const bv = b.cells[COL_DELIVERY] ? b.cells[COL_DELIVERY].textContent.trim() : '';
    return av.localeCompare(bv, 'ja', {{numeric: true}});
  }});
  rows.forEach(r => tbody.appendChild(r));
  applyFilters();
}}

function sortByDefault() {{
  const tbody = document.getElementById('tableBody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const ths = document.querySelectorAll('thead th');
  ths.forEach(th => th.classList.remove('sort-asc', 'sort-desc'));
  sortCol = -1;
  rows.sort((a, b) => {{
    const ac = a.cells[COL_CUSTOMER] ? a.cells[COL_CUSTOMER].textContent.trim() : '';
    const bc = b.cells[COL_CUSTOMER] ? b.cells[COL_CUSTOMER].textContent.trim() : '';
    const ad = a.cells[COL_DELIVERY] ? a.cells[COL_DELIVERY].textContent.trim() : '';
    const bd = b.cells[COL_DELIVERY] ? b.cells[COL_DELIVERY].textContent.trim() : '';
    return ac.localeCompare(bc, 'ja') || ad.localeCompare(bd, 'ja');
  }});
  rows.forEach(r => tbody.appendChild(r));
  applyFilters();
}}

// ── CSV読み込み（ブラウザ内） ───────────────────────────────────
function escHtml(s) {{
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

function parseCSV(text) {{
  const rows = [];
  const lines = text.replace(/\\r\\n/g,'\\n').replace(/\\r/g,'\\n').split('\\n');
  for (const line of lines) {{
    if (!line.trim()) continue;
    const row = [];
    let field = '', inQ = false;
    for (let i = 0; i < line.length; i++) {{
      const c = line[i];
      if (c === '"') {{
        if (inQ && line[i+1] === '"') {{ field += '"'; i++; }}
        else inQ = !inQ;
      }} else if (c === ',' && !inQ) {{
        row.push(field); field = '';
      }} else {{
        field += c;
      }}
    }}
    row.push(field);
    rows.push(row);
  }}
  return rows;
}}

function csvProcClass(date) {{
  if (!date) return 'proc-mi';
  if (date.includes('完') || date.includes('確')) return 'proc-done';
  if (date.includes('進')) return 'proc-shin';
  return 'proc-mi';
}}

function buildProcessBadges(row) {{
  const parts = [];
  for (let i = 0; i < 10; i++) {{
    const name = (row[14+i*4]||'').trim();
    if (!name) continue;
    const date    = (row[16+i*4]||'').trim();
    const machine = (row[15+i*4]||'').trim();
    const cls     = csvProcClass(date);
    const tip     = machine ? ` title="${{escHtml(machine)}}"` : '';
    const ds      = date ? `<span class="proc-date">${{escHtml(date)}}</span>` : '';
    parts.push(`<span class="proc ${{cls}}"${{tip}}>${{escHtml(name)}}${{ds}}</span>`);
  }}
  return parts.length ? parts.join('') : '<span class="no-proc">-</span>';
}}

function fmtAmount(s) {{
  const v = parseInt((s||'').trim());
  return isNaN(v) ? (s||'') : v.toLocaleString('ja-JP');
}}

function fmtJuchuNo(s) {{
  s = (s||'').trim();
  if (s.includes('-')) {{
    const [pre, suf] = s.split('-');
    const n = parseInt(pre);
    const main = isNaN(n) ? escHtml(pre) : n.toString();
    return `<span class="no-main">${{main}}</span><span class="no-sub">${{escHtml(suf)}}</span>`;
  }}
  return `<span class="no-main">${{escHtml(s)}}</span>`;
}}

let csvTantoCol = TANTO_CSV; // CSV読込時に更新

function buildTr(row) {{
  const kanryo      = (row[54]||'').trim();
  const activeDates = Array.from({{length:10}}, (_,i) => (row[14+i*4]||'').trim())
                        .map((name,i) => name ? (row[16+i*4]||'').trim() : null)
                        .filter(d => d !== null);
  const hasMi   = activeDates.some(d => d.includes('未'));
  const allKan  = activeDates.length > 0 && activeDates.every(d => d.includes('完'));
  const isDone  = (!!kanryo || allKan) && !hasMi;
  const proc1   = escHtml((row[14]||'').trim());
  const product2 = (row[5]||'').trim();
  const p2 = product2 ? `<br><small class="product2">${{escHtml(product2)}}</small>` : '';
  const tantoVal = csvTantoCol >= 0 ? (row[csvTantoCol]||'').trim() : '';
  const tantoTd = csvTantoCol >= 0
    ? `<td class="td-tanto"><span class="tanto-badge">${{escHtml(tantoVal)}}</span></td>`
    : '';
  return `<tr class="${{isDone?'done':''}}" data-done="${{isDone?1:0}}" data-proc1="${{proc1}}">
  <td class="td-no">${{fmtJuchuNo(row[0])}}</td>
  <td class="td-date">${{escHtml((row[1]||'').trim())}}</td>
  <td class="td-customer">${{escHtml((row[2]||'').trim())}}</td>
  ${{tantoTd}}
  <td class="td-product">${{escHtml((row[4]||'').trim())}}${{p2}}</td>
  <td class="td-qty">${{fmtAmount(row[6])}}<span class="unit">${{escHtml((row[7]||'').trim())}}</span></td>
  <td class="td-delivery">${{escHtml((row[10]||'').trim())}}</td>
  <td class="td-reply">${{escHtml((row[11]||'').trim())}}</td>
  <td class="td-version">${{escHtml((row[12]||'').trim())}}</td>
  <td class="td-process">${{buildProcessBadges(row)}}</td>
  <td class="td-kanryo">${{escHtml(kanryo)}}</td>
</tr>`;
}}

function renderCSVData(dataRows, headerRow) {{
  // 担当列を検出（CSV読込時）
  if (headerRow) {{
    const idx = headerRow.findIndex(h => h.includes('担当'));
    csvTantoCol = idx >= 0 ? idx : -1;
    // テーブルヘッダーに担当列を追加/削除
    const ths = document.querySelectorAll('thead th');
    const hasTantoTh = Array.from(ths).some(th => th.textContent.trim() === '担当');
    if (csvTantoCol >= 0 && !hasTantoTh) {{
      const customerTh = ths[2];
      const tantoTh = document.createElement('th');
      tantoTh.textContent = '担当';
      customerTh.parentNode.insertBefore(tantoTh, customerTh.nextSibling);
    }} else if (csvTantoCol < 0 && hasTantoTh) {{
      Array.from(ths).find(th => th.textContent.trim() === '担当').remove();
    }}
  }}

  // 得意先→納期順でソート
  dataRows.sort((a,b) => {{
    const ac=(a[2]||'').trim(), bc=(b[2]||'').trim();
    const ad=(a[10]||'').trim(), bd=(b[10]||'').trim();
    return ac.localeCompare(bc,'ja') || ad.localeCompare(bd,'ja');
  }});

  document.getElementById('tableBody').innerHTML = dataRows.map(buildTr).join('');

  // 工程１ドロップダウン更新
  const vals = [...new Set(dataRows.map(r=>(r[14]||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'ja'));
  const sel = document.getElementById('proc1Select');
  sel.innerHTML = '<option value="">すべて</option>' + vals.map(v=>`<option value="${{escHtml(v)}}">${{escHtml(v)}}</option>`).join('');

  // ヘッダー統計更新
  const total = dataRows.length;
  const done  = dataRows.filter(r=>(r[54]||'').trim()).length;
  document.querySelector('.stats').textContent = `全 ${{total}} 件　｜　完了 ${{done}} 件　｜　進行中 ${{total-done}} 件`;

  // フィルター・ソートをリセット
  doneFilter = 'all'; searchText = ''; sortCol = -1;
  document.getElementById('searchBox').value = '';
  document.querySelectorAll('thead th').forEach(th=>th.classList.remove('sort-asc','sort-desc'));
  applyFilters();
}}

function onCsvSelected(event) {{
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {{
    const buf = e.target.result;
    // UTF-8で試し、文字化けがあればShift-JISで再試行
    let text = new TextDecoder('utf-8').decode(buf);
    if (text.includes('�')) text = new TextDecoder('shift-jis').decode(buf);
    const rows = parseCSV(text);
    if (rows.length < 2) {{ alert('データが読み込めませんでした。'); return; }}
    const header = rows[0];
    const data   = rows.slice(1).filter(r => r.some(c=>c.trim()));
    document.querySelector('header span:last-child').textContent = file.name;
    renderCSVData(data, header);
  }};
  reader.readAsArrayBuffer(file);
  event.target.value = ''; // 同じファイルを再選択できるようリセット
}}
</script>
</body>
</html>'''

SAMPLE_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "サンプルデータ.csv")

def pick_csv():
    """ファイル選択ダイアログでCSVを選ぶ。キャンセル時はNoneを返す。"""
    root = tk.Tk()
    root.withdraw()          # メインウィンドウを非表示
    root.attributes('-topmost', True)
    path = filedialog.askopenfilename(
        title="受注明細CSVを選択してください",
        filetypes=[("CSVファイル", "*.csv"), ("すべてのファイル", "*.*")],
        initialdir=os.path.expanduser("~/Desktop"),
    )
    root.destroy()
    return path if path else None

def main():
    # コマンドライン引数があればそれを使用
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        # ファイル選択ダイアログを表示
        csv_path = pick_csv()
        if not csv_path:
            # キャンセル → デフォルトCSV → サンプルの順でフォールバック
            if os.path.exists(CSV_PATH):
                csv_path = CSV_PATH
            elif os.path.exists(SAMPLE_CSV):
                print(f"サンプルデータを使用: {SAMPLE_CSV}")
                csv_path = SAMPLE_CSV
            else:
                print("CSVが選択されませんでした。終了します。")
                sys.exit(0)

    # 指定CSVが存在しなければサンプルデータにフォールバック
    if not os.path.exists(csv_path):
        if os.path.exists(SAMPLE_CSV):
            print(f"元CSVが見つからないためサンプルデータを使用: {SAMPLE_CSV}")
            csv_path = SAMPLE_CSV
        else:
            print(f"エラー: ファイルが見つかりません: {csv_path}")
            sys.exit(1)

    print(f"読み込み中: {csv_path}")
    html = generate_html(csv_path)

    out_path = os.path.splitext(csv_path)[0] + '_ビューア.html'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"出力: {out_path}")
    import subprocess
    subprocess.run(['open', out_path])
    print("ブラウザで開きました。")

if __name__ == '__main__':
    main()
