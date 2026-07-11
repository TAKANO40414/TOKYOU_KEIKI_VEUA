#!/usr/bin/env node
'use strict';

const express  = require('express');
const AdmZip   = require('adm-zip');
const fs       = require('fs');
const path     = require('path');
const os       = require('os');
const zlib     = require('zlib');

// ─── ZIPから必要エントリだけ選択読み込み（ネットワーク対応） ─────────────────
const READ_TIMEOUT_MS = 30000;  // 30秒（catで0.1秒なので十分）

// グローバルI/Oセマフォ: 同時にオープンするZIPファイルを最大2本に制限
// → スレッドプール(4本)を詰まらせずに/api/fileが常にスレッドを取得できる
const _ioSlots = { count: 0, max: 4, queue: [] };
function acquireIoSlot() {
  return new Promise(resolve => {
    if (_ioSlots.count < _ioSlots.max) {
      _ioSlots.count++;
      resolve();
    } else {
      _ioSlots.queue.push(resolve);
    }
  });
}
function releaseIoSlot() {
  if (_ioSlots.queue.length > 0) {
    _ioSlots.queue.shift()();  // 待機中の次の処理を起動
  } else {
    _ioSlots.count--;
  }
}

async function readZipAsync(filePath, filterFn) {
  await acquireIoSlot();
  try {
    return await Promise.race([
      _readZipEntries(filePath, filterFn),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error(`タイムアウト(${READ_TIMEOUT_MS/1000}秒): ${path.basename(filePath)}`)), READ_TIMEOUT_MS)
      ),
    ]);
  } finally {
    releaseIoSlot();
  }
}

async function _readZipEntries(filePath, filterFn) {
  const fh = await fs.promises.open(filePath, 'r');
  try {
    const { size: fileSize } = await fh.stat();

    // ① 末尾から大きめに読む（EOCD+CD+XMLエントリが1回の読み込みに収まるよう1MBを目標）
    // ネットワークファイルはread()の往復回数を最小化するほど速い
    const scanSize = Math.min(1024 * 1024, fileSize);
    const tail = Buffer.alloc(scanSize);
    await fh.read(tail, 0, scanSize, fileSize - scanSize);
    let eocdPos = -1;
    for (let i = scanSize - 22; i >= 0; i--) {
      if (tail.readUInt32LE(i) === 0x06054b50) { eocdPos = i; break; }
    }
    if (eocdPos < 0) throw new Error('EOCD not found');

    // ② セントラルディレクトリを読む（tailに収まっていれば追加読み込み不要）
    const cdSize   = tail.readUInt32LE(eocdPos + 12);
    const cdOffset = tail.readUInt32LE(eocdPos + 16);
    const tailStart = fileSize - scanSize;
    let cd;
    if (cdOffset >= tailStart) {
      // CDはすでにtailに含まれている（ネットワーク往復なし）
      cd = tail.slice(cdOffset - tailStart, cdOffset - tailStart + cdSize);
    } else {
      // CDがtailの外にある場合のみ追加読み込み
      cd = Buffer.alloc(cdSize);
      await fh.read(cd, 0, cdSize, cdOffset);
    }

    // ③ エントリ一覧をパース
    const toRead = [], allNames = [];
    let pos = 0;
    while (pos + 46 <= cd.length) {
      if (cd.readUInt32LE(pos) !== 0x02014b50) break;
      const compression    = cd.readUInt16LE(pos + 10);
      const compressedSize = cd.readUInt32LE(pos + 20);
      const fnLen          = cd.readUInt16LE(pos + 28);
      const extraLen       = cd.readUInt16LE(pos + 30);
      const commentLen     = cd.readUInt16LE(pos + 32);
      const localOffset    = cd.readUInt32LE(pos + 42);
      const entryName      = cd.slice(pos + 46, pos + 46 + fnLen).toString('utf8');
      allNames.push(entryName);
      if (filterFn(entryName)) toRead.push({ entryName, compression, compressedSize, localOffset, fnLen });
      pos += 46 + fnLen + extraLen + commentLen;
    }

    // ④ 対象エントリのみ順番に読む（LH+データを1回のread()に統合してネットワーク往復を半減）
    const data = {};
    for (const e of toRead) {
      // LH(30) + filename(fnLen) + extra(可変) + data を一括読み込み
      // extraLenは最大65535だが実際は短い。LHを含む十分なバッファを確保
      const HEADER_ESTIMATE = 30 + e.fnLen + 256;
      const oneShotSize = HEADER_ESTIMATE + e.compressedSize;
      const oneShot = Buffer.alloc(oneShotSize);
      const { bytesRead } = await fh.read(oneShot, 0, oneShotSize, e.localOffset);
      if (oneShot.readUInt32LE(0) !== 0x04034b50) continue;
      const lhFnLen    = oneShot.readUInt16LE(26);
      const lhExtraLen = oneShot.readUInt16LE(28);
      const dataStart  = 30 + lhFnLen + lhExtraLen;
      if (dataStart + e.compressedSize > bytesRead) {
        // extraLenが予想より大きかった場合のみ再読み込み（まれなケース）
        const fallback = Buffer.alloc(e.compressedSize);
        await fh.read(fallback, 0, e.compressedSize, e.localOffset + dataStart);
        if      (e.compression === 0) data[e.entryName] = fallback;
        else if (e.compression === 8) data[e.entryName] = zlib.inflateRawSync(fallback);
      } else {
        const compressed = oneShot.slice(dataStart, dataStart + e.compressedSize);
        if      (e.compression === 0) data[e.entryName] = Buffer.from(compressed);
        else if (e.compression === 8) data[e.entryName] = zlib.inflateRawSync(compressed);
      }
    }
    return { data, allNames };
  } finally {
    await fh.close();
  }
}

// 全体読み込みが必要な場合（画像取得など）
async function openZip(filePath) {
  await acquireIoSlot();
  try {
    const buf = await Promise.race([
      fs.promises.readFile(filePath),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error(`タイムアウト(${READ_TIMEOUT_MS/1000}秒): ${path.basename(filePath)}`)), READ_TIMEOUT_MS)
      ),
    ]);
    return new AdmZip(buf);
  } finally {
    releaseIoSlot();
  }
}

const app  = express();
const PORT = 8765;
const WATCH_FOLDER = process.argv[2] || process.cwd();

// ─── キャッシュ ───────────────────────────────────────────────────────────────
const CACHE_VERSION = 3;  // バージョンが変わると古いキャッシュは自動破棄
const CACHE_PATH = path.join(os.tmpdir(), 'pc5viewer_cache.json');
let _cache = {};
try {
  const raw = JSON.parse(fs.readFileSync(CACHE_PATH, 'utf8'));
  // バージョンチェック：古いキャッシュは使わない
  if (raw && raw.__version === CACHE_VERSION) {
    _cache = raw;
  }
} catch {}

let _saveCacheTimer = null;
function saveCache() {
  if (_saveCacheTimer) clearTimeout(_saveCacheTimer);
  _saveCacheTimer = setTimeout(() => {
    _saveCacheTimer = null;
    try {
      _cache.__version = CACHE_VERSION;
      fs.writeFileSync(CACHE_PATH, JSON.stringify(_cache), 'utf8');
    } catch {}
  }, 2000);
}
function cacheKey(filePath) {
  return filePath;  // 非同期環境では同期statを使わない（パスだけで一意識別）
}
function cacheKeyAsync(filePath) {
  // stat でネットワークスレッドを消費しないようパスのみでキー生成
  return Promise.resolve(filePath);
}

// ─── XML パーサ（トークンベース・外部モジュール不要） ──────────────────────────
// 正規表現の致命的バックトラックを避けるため、1文字ずつ走査するトークナイザを使用
// 構造: <diffgr:diffgram><NewDataSet><RowTag><Field1>val</Field1>...</RowTag></NewDataSet></diffgr:diffgram>
function parseDiffgramRows(xmlStr) {
  try {
    // XMLエンティティをデコード
    function decodeEntities(s) {
      return s.replace(/&amp;/g,'&').replace(/&lt;/g,'<')
              .replace(/&gt;/g,'>').replace(/&quot;/g,'"')
              .replace(/&apos;/g,"'");
    }

    // 簡易トークナイザ: タグと内容を順番に返すイテレータ
    // yields: { type:'open'|'close'|'text', name, content }
    function* tokenize(xml) {
      let i = 0;
      const n = xml.length;
      while (i < n) {
        if (xml[i] !== '<') {
          // テキストノード
          const start = i;
          while (i < n && xml[i] !== '<') i++;
          yield { type: 'text', content: xml.slice(start, i) };
          continue;
        }
        // タグの開始
        i++; // '<' をスキップ
        if (i >= n) break;

        // コメント <!-- ... -->
        if (xml.startsWith('!--', i)) {
          const end = xml.indexOf('-->', i);
          i = end >= 0 ? end + 3 : n;
          continue;
        }
        // CDATA <![CDATA[ ... ]]>
        if (xml.startsWith('![CDATA[', i)) {
          i += 8;
          const end = xml.indexOf(']]>', i);
          const cdata = end >= 0 ? xml.slice(i, end) : xml.slice(i);
          i = end >= 0 ? end + 3 : n;
          yield { type: 'text', content: cdata };
          continue;
        }
        // 宣言・処理命令 <? ... ?> や <!...>
        if (xml[i] === '?' || xml[i] === '!') {
          const end = xml.indexOf('>', i);
          i = end >= 0 ? end + 1 : n;
          continue;
        }
        // 閉じタグ </name>
        if (xml[i] === '/') {
          i++;
          const start = i;
          while (i < n && xml[i] !== '>' && !/\s/.test(xml[i])) i++;
          const name = xml.slice(start, i).replace(/^[^:]+:/, ''); // ns: を除去
          while (i < n && xml[i] !== '>') i++;
          i++; // '>' をスキップ
          yield { type: 'close', name };
          continue;
        }
        // 開きタグ <name ...> または自己閉じ <name .../>
        const nameStart = i;
        while (i < n && xml[i] !== '>' && xml[i] !== '/' && !/\s/.test(xml[i])) i++;
        const tagName = xml.slice(nameStart, i).replace(/^[^:]+:/, ''); // ns: を除去
        // 属性をスキップ（引用符内の > を無視するため）
        while (i < n && xml[i] !== '>') {
          if (xml[i] === '"') { i++; while (i < n && xml[i] !== '"') i++; }
          else if (xml[i] === "'") { i++; while (i < n && xml[i] !== "'") i++; }
          i++;
        }
        if (i > 0 && xml[i - 1] === '/') {
          // 自己閉じタグ: open + close
          i++; // '>' をスキップ
          if (tagName) { yield { type: 'open', name: tagName }; yield { type: 'close', name: tagName }; }
        } else {
          i++; // '>' をスキップ
          if (tagName) yield { type: 'open', name: tagName };
        }
      }
    }

    // トークンストリームを DOM ツリー（簡易）に変換
    // depth=0: root  depth=1: diffgram  depth=2: dataset(NewDataSet)  depth=3: row  depth=4: field
    // ※ diffgr:before / diffgr:after セクションはスキップ（変更前データなので不要）
    const headers = [], rows = [];
    let depth = 0;
    let diffgramDepth = -1;   // diffgram タグの depth
    let datasetDepth  = -1;   // NewDataSet タグの depth
    let datasetDone   = false; // NewDataSet を1つ処理したら以後スキップ
    let currentRow = null, currentField = null, fieldText = '';

    for (const tok of tokenize(xmlStr)) {
      if (tok.type === 'open') {
        depth++;
        const lname = tok.name.toLowerCase();
        if (diffgramDepth < 0) {
          if (lname.includes('diffgram')) diffgramDepth = depth;
        } else if (datasetDepth < 0 && !datasetDone) {
          // diffgram 直下の最初の子要素 = データセット（before/after は名前で除外）
          if (!lname.includes('before') && !lname.includes('after') && !lname.includes('error')) {
            datasetDepth = depth;
          }
        } else if (datasetDepth >= 0) {
          if (depth === datasetDepth + 1) {
            // 行要素
            currentRow = {};
          } else if (depth === datasetDepth + 2 && currentRow !== null) {
            // フィールド要素
            currentField = tok.name;
            fieldText = '';
          }
        }
      } else if (tok.type === 'close') {
        if (datasetDepth >= 0) {
          if (depth === datasetDepth + 2 && currentRow !== null && currentField !== null) {
            currentRow[currentField] = decodeEntities(fieldText.trim());
            currentField = null; fieldText = '';
          } else if (depth === datasetDepth + 1 && currentRow !== null) {
            if (Object.keys(currentRow).length > 0) {
              if (!headers.length) headers.push(...Object.keys(currentRow));
              rows.push(currentRow);
            }
            currentRow = null;
          } else if (depth === datasetDepth) {
            datasetDepth = -1;
            datasetDone = true; // 2つ目以降の dataset（diffgr:before 等）をスキップ
          }
        }
        if (diffgramDepth >= 0 && depth === diffgramDepth) {
          diffgramDepth = -1;
        }
        depth--;
      } else if (tok.type === 'text') {
        if (datasetDepth >= 0 && depth === datasetDepth + 2 && currentField !== null) {
          fieldText += tok.content;
        }
      }
    }

    return { headers, rows };
  } catch (e) {
    return { headers: [], rows: [] };
  }
}

// ─── PC5 テーブル取得 ────────────────────────────────────────────────────────
async function parsePc5Tables(filePath) {
  // XMLのみ選択読み込み（画像を含む全体読み込みより大幅に高速）
  const { data, allNames } = await readZipAsync(filePath, n => /\.xml$/i.test(n));
  const tables = {}, defectImageKeys = {};
  // 画像キーはエントリ名一覧から収集（データ読み込みなし）
  for (const name of allNames) {
    const base = name.split('/').pop().split('\\').pop();
    const m = base.match(/^(\d+)([DRSdrs])\.(png|jpg|jpeg|bmp)$/i);
    if (m) {
      const num = m[1], type = m[2].toUpperCase();
      if (!defectImageKeys[num]) defectImageKeys[num] = [];
      defectImageKeys[num].push(type);
    }
  }
  for (const [name, buf] of Object.entries(data)) {
    const base = name.split('/').pop().split('\\').pop();
    tables[base.replace(/\.xml$/i, '')] = parseDiffgramRows(buf.toString('utf8'));
  }
  if (Object.keys(tables).length === 0) throw new Error('XMLデータが読み込めませんでした');
  return { tables, defect_image_keys: defectImageKeys };
}

// ─── PC5 画像取得 ─────────────────────────────────────────────────────────────
async function parsePc5Images(filePath, imageNums) {
  const numSet = imageNums ? new Set(imageNums.map(String)) : null;
  const zip = await openZip(filePath);
  const images = {}, defectImages = {};
  for (const entry of zip.getEntries()) {
    const name = entry.entryName;
    const base = name.split('/').pop().split('\\').pop();
    if (!/\.(png|jpg|jpeg|bmp)$/i.test(name)) continue;
    const m = base.match(/^(\d+)([DRSdrs])\.(png|jpg|jpeg|bmp)$/i);
    if (numSet && (!m || !numSet.has(m[1]))) continue;
    const b64 = zip.readFile(entry).toString('base64');
    images[name] = b64;
    if (m) {
      const num = m[1], type = m[2].toUpperCase();
      if (!defectImages[num]) defectImages[num] = {};
      defectImages[num][type] = b64;
    }
  }
  return { images, defect_images: defectImages };
}

// ─── ログ情報取得（キャッシュ付き） ──────────────────────────────────────────
const _inflight = new Map();
async function getLogInfo(filePath) {
  const key = await cacheKeyAsync(filePath);
  if (_cache[key]) return _cache[key];
  if (_inflight.has(key)) return _inflight.get(key);
  const promise = _getLogInfoInner(filePath, key);
  _inflight.set(key, promise);
  try { return await promise; } finally { _inflight.delete(key); }
}
async function _getLogInfoInner(filePath, key) {
  try {
    // LogTable.xml と DefectTable.xml のみ選択読み込み（全体の数%のデータ量）
    const { data } = await readZipAsync(filePath,
      n => /LogTable\.xml$/i.test(n) || /DefectTable\.xml$/i.test(n));
    let logRow = {};
    for (const [name, buf] of Object.entries(data)) {
      const base = name.split('/').pop().split('\\').pop().toLowerCase();
      const rows = parseDiffgramRows(buf.toString('utf8')).rows;
      if (base === 'logtable.xml') logRow = rows[0] || {};
      else if (base === 'defecttable.xml') {
        const pr = rows.filter(r => r.PrincipalFlag === 'true');
        logRow._defect_count = pr.length || rows.length;
      }
    }
    if (logRow._defect_count === undefined) logRow._defect_count = 0;
    _cache[key] = logRow;
    saveCache();
    return logRow;
  } catch { return { _defect_count: 0 }; }
}

// ─── ファイル名解析 ──────────────────────────────────────────────────────────
function parseFilename(filename) {
  const m = filename.match(/^(\d+)-#(\d+)@(\d{4}\w+\d+)-(\d+)h(\d+)m(\d+)/);
  if (m) return { lot: m[1], seq: parseInt(m[2]), date: m[3],
                  time: `${m[4]}:${m[5]}:${m[6]}` };
  return { lot: '', seq: 0, date: '', time: '' };
}

// ─── 日付フォルダ解析 ────────────────────────────────────────────────────────
const MONTH_MAP = { Jan:'01',Feb:'02',Mar:'03',Apr:'04',May:'05',Jun:'06',
                    Jul:'07',Aug:'08',Sep:'09',Oct:'10',Nov:'11',Dec:'12' };
function parseDateFolder(name) {
  const m = name.match(/^(\d{4})([A-Za-z]{3})(\d{1,2})$/);
  if (!m) return null;
  const [, y, mon, d] = m;
  const mo = MONTH_MAP[mon.charAt(0).toUpperCase() + mon.slice(1).toLowerCase()];
  if (!mo) return null;
  return { sortKey: `${y}${mo}${d.padStart(2,'0')}`,
           label:   `${y}年${parseInt(mo)}月${parseInt(d)}日`,
           folder:  name };
}

// 同時実行数を制限するセマフォ（スレッドプール枯渇防止）
// 2に絞ることで残りのスレッドを /api/file の概要読み込み用に確保する
const CONCURRENCY = 4;
async function runWithLimit(tasks) {
  const results = new Array(tasks.length);
  let idx = 0;
  async function worker() {
    while (idx < tasks.length) {
      const i = idx++;
      results[i] = await tasks[i]();
    }
  }
  const workers = Array.from({ length: Math.min(CONCURRENCY, tasks.length) }, worker);
  await Promise.all(workers);
  return results;
}

// ─── PC5ファイル一覧（直近 maxDays 日分） ────────────────────────────────────
// 1フォルダ内のpc5ファイル一覧＋ログ情報を並列取得（同時8件まで）
async function listPc5FilesInDir(dir, subfolder, folderLabel, folderSortKey) {
  let files;
  try { files = await fs.promises.readdir(dir); } catch { return []; }
  const pc5s = files.filter(f => f.toLowerCase().endsWith('.pc5')).sort();
  if (!pc5s.length) return [];

  const metas = pc5s.map(f => parseFilename(f));
  const logs = await runWithLimit(pc5s.map(f => () => getLogInfo(path.join(dir, f))));

  return pc5s.map((f, i) => ({
    filename:        f,
    subfolder:       subfolder,
    folder_label:    folderLabel,
    folder_sort_key: folderSortKey,
    product_name:    logs[i].IdInfo_1 || '',
    lot_no:          logs[i].IdInfo_0 || metas[i].lot,
    part_no:         logs[i].IdInfo_3 || '',
    customer:        logs[i].IdInfo_6 || '',
    defect_count:    logs[i]._defect_count || 0,
    ...metas[i],
  }));
}

async function listPc5Files(folder, maxDays = 7) {
  try { await fs.promises.access(folder); } catch { return []; }

  let entries;
  try { entries = await fs.promises.readdir(folder, { withFileTypes: true }); } catch { return []; }

  const dateFolders = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const info = parseDateFolder(entry.name);
    if (info) dateFolders.push({ info, dir: path.join(folder, entry.name) });
  }

  if (dateFolders.length > 0) {
    // 最新順にソート → maxDays件に絞る → 昇順に戻す
    dateFolders.sort((a, b) => b.info.sortKey.localeCompare(a.info.sortKey));
    const limited = maxDays > 0 ? dateFolders.slice(0, maxDays) : dateFolders;
    limited.sort((a, b) => a.info.sortKey.localeCompare(b.info.sortKey));

    // 日付フォルダ間も並列処理
    const perFolder = await Promise.all(
      limited.map(({ info, dir }) =>
        listPc5FilesInDir(dir, info.folder, info.label, info.sortKey)
      )
    );
    return perFolder.flat();
  }

  // 日付フォルダなし: ルート直下を処理
  return listPc5FilesInDir(folder, '', '', '');
}

// ─── バックグラウンドキャッシュウォームアップ ─────────────────────────────────
const _warmupRunning = new Set();
function startWarmup(folders) {
  for (const folder of folders) {
    if (_warmupRunning.has(folder)) continue;
    _warmupRunning.add(folder);
    setImmediate(async () => {
      try { await listPc5Files(folder, 0); } catch {}
      _warmupRunning.delete(folder);
    });
  }
}

// ─── HTML 読み込み ────────────────────────────────────────────────────────────
function getHTML() {
  const candidates = [
    path.join(path.dirname(process.execPath), 'viewer.html'),
    path.join(__dirname, 'viewer.html'),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return fs.readFileSync(p, 'utf8');
  }
  return '<h1>viewer.html が見つかりません</h1>';
}

// ─── ルーティング ────────────────────────────────────────────────────────────
app.get('/', (_req, res) => res.send(getHTML()));

app.get('/api/default_folder', (_req, res) =>
  res.json({ folder: WATCH_FOLDER }));

app.get('/api/files', async (req, res) => {
  const folders = Array.isArray(req.query.folder)
    ? req.query.folder : [req.query.folder || WATCH_FOLDER];
  const maxDays = parseInt(req.query.days || '7') || 7;

  const allFiles = [];
  for (const folder of folders) {
    try {
      const st = await fs.promises.stat(folder);
      if (!st.isDirectory()) continue;
    } catch { continue; }
    const machineName = path.basename(folder);
    const files = await listPc5Files(folder, maxDays);
    for (const f of files) {
      f.machine_name   = machineName;
      f.machine_folder = folder;
    }
    allFiles.push(...files);
  }

  // ウォームアップ無効化（スレッドプール枯渇の原因のため）

  if (!allFiles.length && folders.length) {
    return res.json({ error: `フォルダが見つかりません: ${folders[0]}` });
  }
  res.json({ files: allFiles });
});

// ─── Windowsドライブ一覧 ─────────────────────────────────────────────────────
app.get('/api/drives', (_req, res) => {
  if (process.platform === 'win32') {
    const { execSync } = require('child_process');
    const drives = [];
    // PowerShell でドライブ一覧取得（wmic は Windows11 で非推奨のため代替）
    try {
      const ps = `Get-PSDrive -PSProvider FileSystem | Select-Object Name,DisplayRoot,Description | ConvertTo-Csv -NoTypeInformation`;
      const out = execSync(`powershell -NoProfile -Command "${ps}"`,
                           { encoding: 'utf8', timeout: 8000 });
      for (const line of out.split('\n')) {
        const parts = line.trim().replace(/^"|"$/g,'').split('","');
        if (parts.length < 2 || parts[0] === 'Name') continue;
        const driveName = parts[0];
        const displayRoot = parts[1] || '';
        const desc = parts[2] || '';
        if (!driveName || driveName.length !== 1) continue;
        const drivePath = driveName + ':\\';
        const isNet = displayRoot.startsWith('\\\\') || desc.toLowerCase().includes('net');
        const label = isNet
          ? `${drivePath}  (${displayRoot || 'ネットワーク'})  [ネットワーク]`
          : `${drivePath}  ${desc ? '('+desc+')' : ''}  [ローカル]`.replace(/\s+/g,' ').trim();
        drives.push({ name: label, path: drivePath,
                      has_pc5: false, is_drive: true,
                      drive_type: isNet ? '4' : '3' });
      }
    } catch {}
    // PowerShell が失敗した場合は wmic フォールバック
    if (drives.length === 0) {
      try {
        const out = execSync('wmic logicaldisk get Name,DriveType,VolumeName /format:csv',
                             { encoding: 'utf8', timeout: 5000 });
        for (const line of out.split('\n')) {
          const parts = line.trim().split(',');
          if (parts.length < 4) continue;
          const [, driveType, name, volumeName] = parts;
          if (!name || !name.includes(':')) continue;
          const typeMap = {'2':'リムーバブル','3':'ローカル','4':'ネットワーク','5':'CD/DVD'};
          drives.push({
            name: `${name}  ${volumeName?'('+volumeName+')':''}  [${typeMap[driveType]||''}]`.trim(),
            path: name + '\\', has_pc5: false, is_drive: true, drive_type: driveType,
          });
        }
      } catch {}
    }
    return res.json({ drives });
  }
  // Mac
  const drives = [];
  try {
    for (const e of fs.readdirSync('/Volumes', { withFileTypes: true })) {
      if (e.isDirectory())
        drives.push({ name: e.name, path: path.join('/Volumes', e.name),
                      has_pc5: false, is_drive: true, drive_type: '3' });
    }
  } catch {}
  res.json({ drives });
});

app.get('/api/browse', async (req, res) => {
  let reqPath = req.query.path || os.homedir();
  // UNCパス（\\server\share）はそのまま使う（path.resolve するとCドライブのパスになる）
  const isUNC = reqPath.startsWith('\\\\') || reqPath.startsWith('//');
  if (!isUNC) {
    try { reqPath = path.resolve(reqPath); } catch {}
  }
  // UNCルート（\\server\share）は存在チェックをスキップ（アクセスできない場合がある）
  const isUNCRoot = isUNC && reqPath.replace(/\\/g,'/').split('/').filter(Boolean).length <= 2;
  if (!isUNCRoot) {
    try {
      const st = await fs.promises.stat(reqPath);
      if (!st.isDirectory())
        return res.json({ error: `フォルダが見つかりません: ${reqPath}` });
    } catch (e) {
      return res.json({ error: `アクセスエラー: ${reqPath} (${e.message})` });
    }
  }
  try {
    const entries = await fs.promises.readdir(reqPath, { withFileTypes: true });
    const dirs = entries
      .filter(e => e.isDirectory() && !e.name.startsWith('.'))
      .map(e => ({ name: e.name, path: path.join(reqPath, e.name), has_pc5: false }))
      .sort((a, b) => a.name.localeCompare(b.name, 'ja'));
    // 親フォルダを計算（UNCルートの場合は null）
    let parent = null;
    if (!isUNCRoot) {
      const parentPath = path.dirname(reqPath);
      if (parentPath !== reqPath) parent = parentPath;
    }
    res.json({ path: reqPath, parent, dirs });
  } catch (e) { res.json({ error: `読み込みエラー: ${String(e)}` }); }
});

// ファイルパスを解決するヘルパー
function resolveFilePath(folder, subfolder, filename) {
  folder    = folder    || WATCH_FOLDER;
  subfolder = subfolder || '';
  filename  = filename  || '';
  return subfolder ? path.join(folder, subfolder, filename)
                   : path.join(folder, filename);
}

// /api/file: テーブルのみ返す（軽量・高速）
app.get('/api/file', async (req, res) => {
  const filePath = resolveFilePath(req.query.folder, req.query.subfolder, req.query.filename);
  console.log('[/api/file] リクエスト:', filePath);
  try { await fs.promises.access(filePath); } catch (e) {
    console.error('[/api/file] アクセス不可:', filePath, e.message);
    return res.json({ error: `ファイルが見つかりません: ${filePath}\n(${e.message})` });
  }
  if (!filePath.toLowerCase().endsWith('.pc5'))
    return res.json({ error: 'PC5ファイルではありません' });
  try {
    const { tables, defect_image_keys } = await parsePc5Tables(filePath);
    let posScale = 0, lengthM = 0;
    const chRows = (tables.ChapterTable || {}).rows || [];
    if (chRows.length > 0) {
      lengthM      = parseFloat(chRows[0].Length      || 0);
      const endPos = parseFloat(chRows[0].EndPosition || 0);
      if (endPos > 0) {
        const scale = lengthM / endPos;
        if (scale > 0.000001 && scale < 0.01) posScale = scale;
      }
    }
    console.log('[/api/file] 成功:', filePath);
    res.json({ tables, defect_image_keys, pos_scale: posScale, length_m: lengthM });
  } catch (e) {
    console.error('[/api/file] 読み込みエラー:', filePath, e.stack || e.message);
    res.json({ error: `読み込みエラー: ${e.message}\nパス: ${filePath}` });
  }
});

// /api/images: 画像を返す（欠点タブ表示時に呼び出し）
// クエリ: folder, subfolder, filename, nums=0001,0002,... (省略時は全て)
app.get('/api/images', async (req, res) => {
  const filePath = resolveFilePath(req.query.folder, req.query.subfolder, req.query.filename);
  try { await fs.promises.access(filePath); } catch {
    return res.json({ error: `ファイルが見つかりません: ${filePath}` });
  }
  try {
    const nums = req.query.nums ? req.query.nums.split(',') : null;
    const { images, defect_images } = await parsePc5Images(filePath, nums);
    res.json({ images, defect_images });
  } catch (e) { res.json({ error: String(e) }); }
});

// ─── 起動 ────────────────────────────────────────────────────────────────────
function getLocalIPs() {
  const ips = [];
  for (const ifaces of Object.values(os.networkInterfaces())) {
    for (const iface of ifaces) {
      if (iface.family === 'IPv4' && !iface.internal) ips.push(iface.address);
    }
  }
  return ips;
}

app.listen(PORT, '0.0.0.0', () => {
  const localUrl = `http://localhost:${PORT}`;
  console.log('='.repeat(60));
  console.log('  PC5 ビューア v2.9 起動中...');
  console.log(`  監視フォルダ: ${WATCH_FOLDER}`);
  console.log('');
  console.log('  【このPC から開く】');
  console.log(`    ${localUrl}`);
  const ips = getLocalIPs();
  if (ips.length) {
    console.log('');
    console.log('  【他のPC・スマホ から開く】');
    for (const ip of ips) console.log(`    http://${ip}:${PORT}`);
  }
  console.log('');
  console.log('  終了: このウィンドウを閉じる');
  console.log('='.repeat(60));

  const start = process.platform === 'win32' ? 'start'
              : process.platform === 'darwin' ? 'open' : 'xdg-open';
  require('child_process').exec(`${start} ${localUrl}`);
});
