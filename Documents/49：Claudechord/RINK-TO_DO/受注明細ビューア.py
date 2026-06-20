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

CSV_PATH = "/Users/takanoakihito/Desktop/受注明細一覧_20260620.csv"

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
    rows = []
    with open(path, 'r', encoding='cp932', errors='replace') as f:
        reader = csv.reader(f)
        headers = next(reader)
        for row in reader:
            if any(c.strip() for c in row):
                rows.append(row)
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

def build_rows_html(rows):
    def sort_key(row):
        return (get(row, 2), get(row, 10))

    sorted_rows = sorted(rows, key=sort_key)
    parts = []
    for row in sorted_rows:
        kanryo = get(row, KANRYO_COL)
        is_done = bool(kanryo)

        raw_no = get(row, 0)
        # 0000123456-000 → 123456-000（ハイフン前の先頭ゼロを除去）
        if '-' in raw_no:
            prefix, suffix = raw_no.split('-', 1)
            juchu_no = esc(f'{int(prefix)}-{suffix}' if prefix.isdigit() else raw_no)
        else:
            juchu_no = esc(raw_no)
        juchu_date  = esc(get(row, 1))
        customer    = esc(get(row, 2))
        product1    = esc(get(row, 4))
        product2    = esc(get(row, 5))
        qty         = esc(get(row, 6))
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

        parts.append(f'''
<tr class="{row_cls}" data-done="{done_attr}" data-proc1="{proc1_val}">
  <td class="td-no">{juchu_no}</td>
  <td class="td-date">{juchu_date}</td>
  <td class="td-customer">{customer}</td>
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
    rows_html = build_rows_html(rows)
    total = len(rows)

    done_count = sum(1 for r in rows if get(r, KANRYO_COL))

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
  font-size: 12px;
  background: #f0f2f5;
  color: #222;
}}
header {{
  background: #1a3a5c;
  color: #fff;
  padding: 12px 20px;
  display: flex;
  align-items: center;
  gap: 20px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 6px rgba(0,0,0,.3);
}}
header h1 {{
  font-size: 16px;
  font-weight: bold;
  flex: 1;
}}
.stats {{ font-size: 12px; color: #acd; white-space: nowrap; }}
.controls {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  background: #fff;
  border-bottom: 1px solid #ddd;
  flex-wrap: wrap;
}}
.btn {{
  padding: 6px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  font-family: inherit;
  transition: opacity .15s;
}}
.btn:hover {{ opacity: .85; }}
.btn-hide {{
  background: #e8534a;
  color: #fff;
}}
.btn-show {{
  background: #4a90d9;
  color: #fff;
}}
.btn-all {{
  background: #555;
  color: #fff;
}}
.btn-sort-delivery {{
  background: #2e7d32;
  color: #fff;
}}
.btn-sort-default {{
  background: #6a4c93;
  color: #fff;
}}
.btn-load {{
  background: #e67e22;
  color: #fff;
  font-weight: bold;
}}
#csvFileInput {{ display: none; }}
label.filter-label {{
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  cursor: pointer;
  color: #333;
}}
label.filter-label input {{ cursor: pointer; }}
.search-box {{
  padding: 5px 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 12px;
  width: 200px;
}}
.count-info {{
  font-size: 12px;
  color: #666;
  margin-left: auto;
}}
.table-wrap {{
  overflow-x: auto;
  padding: 10px 20px 30px;
}}
table {{
  border-collapse: collapse;
  width: 100%;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,.1);
  border-radius: 4px;
  overflow: hidden;
}}
thead tr {{
  background: #2c5282;
  color: #fff;
  text-align: left;
  white-space: nowrap;
}}
thead th {{
  padding: 8px 10px;
  font-weight: 600;
  font-size: 11px;
  letter-spacing: .3px;
  cursor: pointer;
  user-select: none;
}}
thead th:hover {{ background: #2a4a72; }}
thead th.sort-asc::after {{ content: " ▲"; font-size: 9px; }}
thead th.sort-desc::after {{ content: " ▼"; font-size: 9px; }}
tbody tr {{
  border-bottom: 1px solid #e8eaf0;
  transition: background .1s;
}}
tbody tr:hover {{ background: #f0f4ff !important; }}
tbody tr.done {{
  background: #e8f5e9;
  color: #558;
}}
tbody tr.done td {{ color: #667; }}
tbody tr.done .td-kanryo {{
  color: #2e7d32;
  font-weight: bold;
}}
td {{
  padding: 7px 10px;
  vertical-align: top;
  font-size: 11.5px;
}}
.td-no {{ white-space: nowrap; font-family: monospace; font-size: 11px; color: #555; }}
.td-date {{ white-space: nowrap; }}
.td-customer {{ font-weight: 600; white-space: nowrap; min-width: 120px; }}
.td-product {{ min-width: 160px; max-width: 240px; }}
.product2 {{ color: #888; font-size: 10px; }}
.td-qty {{ white-space: nowrap; text-align: right; }}
.unit {{ color: #888; margin-left: 2px; }}
.td-amount {{ white-space: nowrap; text-align: right; font-variant-numeric: tabular-nums; }}
.td-delivery {{ white-space: nowrap; font-weight: 600; color: #c0392b; }}
.td-reply {{ white-space: nowrap; }}
.td-version {{ white-space: nowrap; }}
.td-process {{ min-width: 200px; max-width: 380px; }}
.td-kanryo {{ white-space: nowrap; min-width: 90px; }}
.proc {{
  display: inline-block;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  margin: 2px 2px 2px 0;
  line-height: 1.6;
  white-space: nowrap;
}}
.proc-done {{
  background: #ffcdd2;
  color: #b71c1c;
  border: 1px solid #000;
  font-weight: 600;
}}
.proc-shin {{
  background: #fff9c4;
  color: #f57f17;
  border: 1px solid #000;
}}
.proc-mi {{
  background: #eceff1;
  color: #546e7a;
  border: 1px solid #000;
}}
.proc-date {{
  display: block;
  font-size: 9px;
  color: #555;
  margin-top: 1px;
}}
.no-proc {{ color: #bbb; }}
</style>
</head>
<body>
<header>
  <h1>受注明細一覧</h1>
  <span class="stats">全 {total} 件 ／ 完了 {done_count} 件 ／ 進行中 {total - done_count} 件</span>
  <span style="font-size:11px;color:#9bc">{esc(filename)}</span>
</header>
<div class="controls">
  <button class="btn btn-load" onclick="document.getElementById('csvFileInput').click()">📂 CSVを読み込む</button>
  <input type="file" id="csvFileInput" accept=".csv" onchange="onCsvSelected(event)">
  <span style="width:1px;height:24px;background:#ddd;display:inline-block;"></span>
  <button class="btn btn-hide" onclick="hideDone()">完了済みを非表示</button>
  <button class="btn btn-show" onclick="showDone()">完了済みを表示</button>
  <button class="btn btn-all" onclick="showAll()">すべて表示</button>
  <span style="width:1px;height:24px;background:#ddd;display:inline-block;"></span>
  <button class="btn btn-sort-delivery" onclick="sortByDelivery()">納期順 ▲</button>
  <button class="btn btn-sort-default" onclick="sortByDefault()">得意先＋納期順</button>
  <span style="width:1px;height:24px;background:#ddd;display:inline-block;"></span>
  <label style="font-size:12px;color:#333;display:flex;align-items:center;gap:6px;">
    工程１
    <select id="proc1Select" onchange="applyFilters()" style="padding:5px 8px;border:1px solid #ccc;border-radius:4px;font-size:12px;font-family:inherit;">
      {proc1_options}
    </select>
  </label>
  <span style="width:1px;height:24px;background:#ddd;display:inline-block;"></span>
  <input class="search-box" type="text" id="searchBox" placeholder="得意先・製品名で絞込..." oninput="filterTable()">
  <span class="count-info" id="countInfo">表示中: {total} 件</span>
</div>
<div class="table-wrap">
<table id="mainTable">
<thead>
<tr>
  <th onclick="sortTable(0)">受注No</th>
  <th onclick="sortTable(1)">受注日</th>
  <th onclick="sortTable(2)">得意先</th>
  <th onclick="sortTable(3)">製品名</th>
  <th onclick="sortTable(4)">数量</th>
  <th onclick="sortTable(5)">納期</th>
  <th>納期返事</th>
  <th>版区</th>
  <th>工程進捗</th>
  <th onclick="sortTable(9)">最終納品日</th>
</tr>
</thead>
<tbody id="tableBody">
{rows_html}
</tbody>
</table>
</div>
<script>
let hidingDone = false;
let searchText = '';

function hideDone() {{
  hidingDone = true;
  applyFilters();
}}
function showDone() {{
  hidingDone = false;
  applyFilters();
}}
function showAll() {{
  hidingDone = false;
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
    const matchDone = !hidingDone || !done;
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
  ths[5].classList.add('sort-asc');
  sortCol = 5;
  sortAsc = true;
  rows.sort((a, b) => {{
    const av = a.cells[5] ? a.cells[5].textContent.trim() : '';
    const bv = b.cells[5] ? b.cells[5].textContent.trim() : '';
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
    const ac = a.cells[2] ? a.cells[2].textContent.trim() : '';
    const bc = b.cells[2] ? b.cells[2].textContent.trim() : '';
    const ad = a.cells[5] ? a.cells[5].textContent.trim() : '';
    const bd = b.cells[5] ? b.cells[5].textContent.trim() : '';
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
  const lines = text.replace(/\r\n/g,'\n').replace(/\r/g,'\n').split('\n');
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
    return isNaN(n) ? s : n + '-' + suf;
  }}
  return s;
}}

function buildTr(row) {{
  const kanryo  = (row[54]||'').trim();
  const isDone  = !!kanryo;
  const proc1   = escHtml((row[14]||'').trim());
  const product2 = (row[5]||'').trim();
  const p2 = product2 ? `<br><small class="product2">${{escHtml(product2)}}</small>` : '';
  return `<tr class="${{isDone?'done':''}}" data-done="${{isDone?1:0}}" data-proc1="${{proc1}}">
  <td class="td-no">${{escHtml(fmtJuchuNo(row[0]))}}</td>
  <td class="td-date">${{escHtml((row[1]||'').trim())}}</td>
  <td class="td-customer">${{escHtml((row[2]||'').trim())}}</td>
  <td class="td-product">${{escHtml((row[4]||'').trim())}}${{p2}}</td>
  <td class="td-qty">${{escHtml((row[6]||'').trim())}}<span class="unit">${{escHtml((row[7]||'').trim())}}</span></td>
  <td class="td-delivery">${{escHtml((row[10]||'').trim())}}</td>
  <td class="td-reply">${{escHtml((row[11]||'').trim())}}</td>
  <td class="td-version">${{escHtml((row[12]||'').trim())}}</td>
  <td class="td-process">${{buildProcessBadges(row)}}</td>
  <td class="td-kanryo">${{escHtml(kanryo)}}</td>
</tr>`;
}}

function renderCSVData(dataRows) {{
  // 得意先→納期順でソート
  dataRows.sort((a,b) => {{
    const ac=(a[2]||'').trim(), bc=(b[2]||'').trim();
    const ad=(a[10]||'').trim(), bd=(b[10]||'').trim();
    return ac.localeCompare(bc,'ja') || ad.localeCompare(bd,'ja');
  }});

  document.getElementById('tableBody').innerHTML = dataRows.map(buildTr).join('\n');

  // 工程１ドロップダウン更新
  const vals = [...new Set(dataRows.map(r=>(r[14]||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'ja'));
  const sel = document.getElementById('proc1Select');
  sel.innerHTML = '<option value="">すべて</option>' + vals.map(v=>`<option value="${{escHtml(v)}}">${{escHtml(v)}}</option>`).join('');

  // ヘッダー統計更新
  const total = dataRows.length;
  const done  = dataRows.filter(r=>(r[54]||'').trim()).length;
  document.querySelector('.stats').textContent = `全 ${{total}} 件 ／ 完了 ${{done}} 件 ／ 進行中 ${{total-done}} 件`;

  // フィルター・ソートをリセット
  hidingDone = false; searchText = ''; sortCol = -1;
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
    renderCSVData(data);
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
