#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║   Data Redundancy Removal System                         ║
║   CodeAlpha Cloud Computing Internship - Task 1          ║
║   Intern: Gayathri B | ID: CA/DF1/79283                 ║
╚══════════════════════════════════════════════════════════╝
"""

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import hashlib
import json
import re
from datetime import datetime

app = Flask(__name__)
DB_PATH = "cloud_data.db"

# ─────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL,
            email     TEXT NOT NULL,
            phone     TEXT,
            data      TEXT,
            hash      TEXT UNIQUE NOT NULL,
            added_at  TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS rejected (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT,
            email        TEXT,
            phone        TEXT,
            data         TEXT,
            reason       TEXT,
            rejected_at  TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# ─────────────────────────────────────────
# CORE LOGIC
# ─────────────────────────────────────────
def generate_hash(record: dict) -> str:
    """Generate SHA-256 hash for a record (case-insensitive, stripped)."""
    normalized = json.dumps({
        k: str(v).strip().lower()
        for k, v in sorted(record.items())
        if k != "hash"
    }, sort_keys=True)
    return hashlib.sha256(normalized.encode()).hexdigest()

def is_valid_email(email: str) -> bool:
    return bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email))

def is_valid_phone(phone: str) -> bool:
    return bool(re.match(r'^\+?[\d\s\-]{7,15}$', phone)) if phone else True

def validate_record(record: dict) -> tuple[bool, str]:
    """Validate a record. Returns (is_valid, reason)."""
    if not record.get("name", "").strip():
        return False, "Name is empty"
    if not record.get("email", "").strip():
        return False, "Email is empty"
    if not is_valid_email(record["email"]):
        return False, f"Invalid email format: {record['email']}"
    if record.get("phone") and not is_valid_phone(record["phone"]):
        return False, f"Invalid phone format: {record['phone']}"
    return True, "OK"

def check_duplicate(conn, record_hash: str, email: str) -> tuple[bool, str]:
    """Check if record already exists by hash or email."""
    c = conn.cursor()
    c.execute("SELECT id FROM records WHERE hash = ?", (record_hash,))
    if c.fetchone():
        return True, "Exact duplicate (same data already exists)"
    c.execute("SELECT id FROM records WHERE LOWER(email) = LOWER(?)", (email,))
    if c.fetchone():
        return True, f"Email already registered: {email}"
    return False, ""

def add_record(record: dict) -> dict:
    """Main function: validate → deduplicate → insert."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Step 1: Validate
    valid, reason = validate_record(record)
    if not valid:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO rejected (name,email,phone,data,reason,rejected_at) VALUES (?,?,?,?,?,?)",
            (record.get("name"), record.get("email"), record.get("phone"),
             record.get("data"), reason, now)
        )
        conn.commit(); conn.close()
        return {"status": "rejected", "reason": reason}

    # Step 2: Generate hash
    record_hash = generate_hash(record)

    # Step 3: Check duplicate
    conn = sqlite3.connect(DB_PATH)
    is_dup, dup_reason = check_duplicate(conn, record_hash, record["email"])
    if is_dup:
        conn.execute(
            "INSERT INTO rejected (name,email,phone,data,reason,rejected_at) VALUES (?,?,?,?,?,?)",
            (record.get("name"), record.get("email"), record.get("phone"),
             record.get("data"), dup_reason, now)
        )
        conn.commit(); conn.close()
        return {"status": "duplicate", "reason": dup_reason}

    # Step 4: Insert unique record
    conn.execute(
        "INSERT INTO records (name,email,phone,data,hash,added_at) VALUES (?,?,?,?,?,?)",
        (record["name"].strip(), record["email"].strip().lower(),
         record.get("phone","").strip(), record.get("data","").strip(),
         record_hash, now)
    )
    conn.commit(); conn.close()
    return {"status": "success", "message": "Record added successfully ✅"}

def get_stats() -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM records")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM rejected")
    rejected = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM rejected WHERE reason LIKE '%duplicate%' OR reason LIKE '%already%'")
    duplicates = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM rejected WHERE reason NOT LIKE '%duplicate%' AND reason NOT LIKE '%already%'")
    invalid = c.fetchone()[0]
    conn.close()
    return {
        "total_unique": total,
        "total_rejected": rejected,
        "duplicates_blocked": duplicates,
        "invalid_blocked": invalid,
        "accuracy": round((total / (total + rejected) * 100), 1) if (total + rejected) > 0 else 0
    }

def get_all_records():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    records = conn.execute("SELECT * FROM records ORDER BY added_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in records]

def get_rejected():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    records = conn.execute("SELECT * FROM rejected ORDER BY rejected_at DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in records]

def clear_all():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM records")
    conn.execute("DELETE FROM rejected")
    conn.commit(); conn.close()

# ─────────────────────────────────────────
# HTML UI
# ─────────────────────────────────────────
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Data Redundancy Removal System — CodeAlpha</title>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
    :root{
      --bg:#0e1117;--surface:#161b22;--surface2:#21262d;
      --border:#30363d;--accent:#238636;--accent2:#1f6feb;
      --danger:#da3633;--warn:#e3b341;--text:#e6edf3;--muted:#8b949e;
      --success:#3fb950;
    }
    body{background:var(--bg);color:var(--text);font-family:'Space Grotesk',sans-serif;min-height:100vh;}
    body::before{
      content:'';position:fixed;inset:0;
      background:
        radial-gradient(ellipse 600px 400px at 5% 5%,rgba(31,111,235,0.08) 0%,transparent 70%),
        radial-gradient(ellipse 500px 400px at 95% 95%,rgba(35,134,54,0.08) 0%,transparent 70%);
      pointer-events:none;z-index:0;
    }
    .wrap{max-width:1100px;margin:0 auto;padding:24px 20px;position:relative;z-index:1;}

    /* Header */
    .header{
      background:var(--surface);border:1px solid var(--border);
      border-radius:16px;padding:20px 24px;margin-bottom:24px;
      display:flex;align-items:center;gap:16px;
    }
    .header-icon{
      width:50px;height:50px;
      background:linear-gradient(135deg,#1f6feb,#238636);
      border-radius:14px;display:flex;align-items:center;
      justify-content:center;font-size:24px;flex-shrink:0;
    }
    .header h1{font-size:20px;font-weight:700;letter-spacing:-0.3px;}
    .header p{font-size:12.5px;color:var(--muted);margin-top:3px;}
    .badge{
      margin-left:auto;background:rgba(35,134,54,0.15);
      border:1px solid rgba(35,134,54,0.3);color:var(--success);
      padding:5px 14px;border-radius:20px;font-size:12px;font-weight:600;
      white-space:nowrap;
    }

    /* Stats */
    .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px;}
    .stat{
      background:var(--surface);border:1px solid var(--border);
      border-radius:12px;padding:16px;text-align:center;
    }
    .stat .val{font-size:28px;font-weight:700;font-family:'JetBrains Mono',monospace;}
    .stat .lbl{font-size:11.5px;color:var(--muted);margin-top:4px;}
    .stat.green .val{color:var(--success);}
    .stat.red .val{color:var(--danger);}
    .stat.blue .val{color:#58a6ff;}
    .stat.yellow .val{color:var(--warn);}

    /* Grid */
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px;}
    @media(max-width:700px){.grid{grid-template-columns:1fr;}.stats{grid-template-columns:1fr 1fr;}}

    /* Cards */
    .card{
      background:var(--surface);border:1px solid var(--border);
      border-radius:14px;overflow:hidden;
    }
    .card-header{
      padding:14px 18px;border-bottom:1px solid var(--border);
      display:flex;align-items:center;gap:8px;
    }
    .card-header h2{font-size:15px;font-weight:600;}
    .card-body{padding:18px;}

    /* Form */
    .form-group{margin-bottom:14px;}
    label{display:block;font-size:12.5px;color:var(--muted);margin-bottom:6px;font-weight:500;}
    input,textarea{
      width:100%;background:var(--surface2);
      border:1px solid var(--border);border-radius:10px;
      padding:10px 14px;color:var(--text);
      font-family:'Space Grotesk',sans-serif;font-size:13.5px;
      outline:none;transition:border-color 0.2s;
    }
    input:focus,textarea:focus{border-color:var(--accent2);}
    textarea{resize:vertical;min-height:70px;}

    .btn{
      width:100%;padding:11px;border:none;border-radius:10px;
      font-family:'Space Grotesk',sans-serif;font-size:14px;
      font-weight:600;cursor:pointer;transition:all 0.2s;
    }
    .btn-primary{background:linear-gradient(135deg,#1f6feb,#238636);color:#fff;}
    .btn-primary:hover{filter:brightness(1.1);transform:translateY(-1px);}
    .btn-danger{background:rgba(218,54,51,0.15);border:1px solid rgba(218,54,51,0.3);color:var(--danger);margin-top:10px;}
    .btn-danger:hover{background:rgba(218,54,51,0.25);}

    /* Result */
    .result{
      margin-top:14px;padding:12px 14px;border-radius:10px;
      font-size:13.5px;font-weight:500;display:none;
    }
    .result.success{background:rgba(63,185,80,0.1);border:1px solid rgba(63,185,80,0.3);color:var(--success);}
    .result.error{background:rgba(218,54,51,0.1);border:1px solid rgba(218,54,51,0.3);color:var(--danger);}
    .result.warn{background:rgba(227,179,65,0.1);border:1px solid rgba(227,179,65,0.3);color:var(--warn);}

    /* Bulk test */
    .bulk-info{font-size:12px;color:var(--muted);margin-bottom:12px;line-height:1.6;}
    .bulk-result{margin-top:12px;max-height:160px;overflow-y:auto;}
    .bulk-item{
      font-size:12px;padding:6px 10px;border-radius:7px;
      margin-bottom:5px;font-family:'JetBrains Mono',monospace;
    }
    .bulk-item.ok{background:rgba(63,185,80,0.1);color:var(--success);}
    .bulk-item.dup{background:rgba(227,179,65,0.1);color:var(--warn);}
    .bulk-item.inv{background:rgba(218,54,51,0.1);color:var(--danger);}

    /* Table */
    .table-wrap{overflow-x:auto;}
    table{width:100%;border-collapse:collapse;font-size:13px;}
    th{
      padding:10px 14px;text-align:left;
      border-bottom:1px solid var(--border);
      color:var(--muted);font-size:11.5px;font-weight:600;
      text-transform:uppercase;letter-spacing:0.5px;
    }
    td{
      padding:10px 14px;border-bottom:1px solid var(--border);
      font-family:'JetBrains Mono',monospace;font-size:12px;
    }
    tr:last-child td{border-bottom:none;}
    tr:hover td{background:var(--surface2);}
    .tag{
      display:inline-block;padding:2px 8px;border-radius:6px;
      font-size:11px;font-weight:600;
    }
    .tag.ok{background:rgba(63,185,80,0.15);color:var(--success);}
    .tag.dup{background:rgba(227,179,65,0.15);color:var(--warn);}
    .tag.inv{background:rgba(218,54,51,0.15);color:var(--danger);}

    /* Tabs */
    .tabs{display:flex;gap:8px;margin-bottom:16px;}
    .tab{
      padding:7px 16px;border-radius:20px;font-size:13px;
      cursor:pointer;border:1px solid var(--border);
      background:transparent;color:var(--muted);
      font-family:'Space Grotesk',sans-serif;transition:all 0.2s;
    }
    .tab.active{background:var(--accent2);border-color:var(--accent2);color:#fff;}

    .empty{text-align:center;padding:30px;color:var(--muted);font-size:13px;}

    /* Footer */
    .footer{
      text-align:center;padding:20px;
      font-size:12px;color:var(--muted);
      border-top:1px solid var(--border);margin-top:10px;
    }
  </style>
</head>
<body>
<div class="wrap">

  <!-- Header -->
  <div class="header">
    <div class="header-icon">🛡️</div>
    <div>
      <h1>Data Redundancy Removal System</h1>
      <p>CodeAlpha Cloud Computing Internship — Task 1 | Gayathri B | CA/DF1/79283</p>
    </div>
    <div class="badge">✅ System Active</div>
  </div>

  <!-- Stats -->
  <div class="stats" id="statsGrid">
    <div class="stat green"><div class="val" id="s1">0</div><div class="lbl">Unique Records</div></div>
    <div class="stat red"><div class="val" id="s2">0</div><div class="lbl">Duplicates Blocked</div></div>
    <div class="stat yellow"><div class="val" id="s3">0</div><div class="lbl">Invalid Blocked</div></div>
    <div class="stat blue"><div class="val" id="s4">0%</div><div class="lbl">DB Accuracy</div></div>
  </div>

  <!-- Main Grid -->
  <div class="grid">

    <!-- Add Record -->
    <div class="card">
      <div class="card-header">
        <span>➕</span><h2>Add New Record</h2>
      </div>
      <div class="card-body">
        <div class="form-group">
          <label>Full Name *</label>
          <input id="f_name" placeholder="e.g. Gayathri B"/>
        </div>
        <div class="form-group">
          <label>Email Address *</label>
          <input id="f_email" type="email" placeholder="e.g. gayathri@email.com"/>
        </div>
        <div class="form-group">
          <label>Phone Number</label>
          <input id="f_phone" placeholder="e.g. +91 9876543210"/>
        </div>
        <div class="form-group">
          <label>Additional Data</label>
          <textarea id="f_data" placeholder="Any extra information..."></textarea>
        </div>
        <button class="btn btn-primary" onclick="addRecord()">🚀 Submit & Validate</button>
        <div class="result" id="result"></div>
        <button class="btn btn-danger" onclick="clearAll()">🗑 Clear All Records</button>
      </div>
    </div>

    <!-- Bulk Test -->
    <div class="card">
      <div class="card-header">
        <span>⚡</span><h2>Bulk Test (Demo)</h2>
      </div>
      <div class="card-body">
        <p class="bulk-info">
          Click below to auto-insert <strong>10 sample records</strong> including duplicates and invalid entries.
          The system will automatically detect and block redundant data.
        </p>
        <button class="btn btn-primary" onclick="runBulkTest()">▶ Run Bulk Test</button>
        <div class="bulk-result" id="bulkResult"></div>

        <div style="margin-top:20px;">
          <div class="card-header" style="padding:10px 0;border:none;">
            <span>🔍</span><h2>How It Works</h2>
          </div>
          <div style="font-size:13px;color:var(--muted);line-height:1.9;margin-top:8px;">
            <div>1️⃣ <strong style="color:var(--text)">Validation</strong> — checks name, email, phone format</div>
            <div>2️⃣ <strong style="color:var(--text)">Hash Generation</strong> — SHA-256 fingerprint per record</div>
            <div>3️⃣ <strong style="color:var(--text)">Duplicate Check</strong> — hash + email uniqueness</div>
            <div>4️⃣ <strong style="color:var(--text)">Insert / Reject</strong> — only unique valid data stored</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Records Table -->
  <div class="card" style="margin-bottom:24px;">
    <div class="card-header">
      <span>🗄️</span><h2>Database Records</h2>
    </div>
    <div class="card-body" style="padding:0;">
      <div style="padding:14px 18px 0;">
        <div class="tabs">
          <button class="tab active" onclick="switchTab('unique',this)">✅ Unique Records</button>
          <button class="tab" onclick="switchTab('rejected',this)">🚫 Rejected Records</button>
        </div>
      </div>
      <div class="table-wrap" id="tableWrap">
        <div class="empty" id="emptyMsg">No records yet. Add one above!</div>
        <table id="recordsTable" style="display:none;">
          <thead>
            <tr>
              <th>#</th><th>Name</th><th>Email</th><th>Phone</th><th>Data</th><th>Status</th><th>Added At</th>
            </tr>
          </thead>
          <tbody id="recordsTbody"></tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="footer">
    🛡️ Data Redundancy Removal System · CodeAlpha Cloud Computing Internship · Task 1 · Gayathri B
  </div>
</div>

<script>
  let currentTab = 'unique';

  async function loadStats() {
    const r = await fetch('/api/stats');
    const d = await r.json();
    document.getElementById('s1').textContent = d.total_unique;
    document.getElementById('s2').textContent = d.duplicates_blocked;
    document.getElementById('s3').textContent = d.invalid_blocked;
    document.getElementById('s4').textContent = d.accuracy + '%';
  }

  async function loadTable() {
    const url = currentTab === 'unique' ? '/api/records' : '/api/rejected';
    const r = await fetch(url);
    const data = await r.json();
    const tbody = document.getElementById('recordsTbody');
    const table = document.getElementById('recordsTable');
    const empty = document.getElementById('emptyMsg');

    if (!data.length) {
      table.style.display = 'none';
      empty.style.display = 'block';
      empty.textContent = currentTab === 'unique' ? 'No records yet. Add one above!' : 'No rejected records.';
      return;
    }

    table.style.display = 'table';
    empty.style.display = 'none';

    if (currentTab === 'unique') {
      tbody.innerHTML = data.map((r,i) => `
        <tr>
          <td>${r.id}</td>
          <td>${r.name}</td>
          <td>${r.email}</td>
          <td>${r.phone || '—'}</td>
          <td>${r.data ? r.data.slice(0,30) + (r.data.length>30?'…':'') : '—'}</td>
          <td><span class="tag ok">✅ Unique</span></td>
          <td>${r.added_at}</td>
        </tr>`).join('');
    } else {
      tbody.innerHTML = data.map(r => `
        <tr>
          <td>${r.id}</td>
          <td>${r.name || '—'}</td>
          <td>${r.email || '—'}</td>
          <td>${r.phone || '—'}</td>
          <td>${r.data ? r.data.slice(0,25)+'…' : '—'}</td>
          <td><span class="tag ${r.reason.includes('duplicate')||r.reason.includes('already') ? 'dup':'inv'}">${r.reason.includes('duplicate')||r.reason.includes('already') ? '🔁 Duplicate':'❌ Invalid'}</span></td>
          <td>${r.rejected_at}</td>
        </tr>`).join('');
    }
  }

  function refresh() { loadStats(); loadTable(); }

  async function addRecord() {
    const record = {
      name:  document.getElementById('f_name').value,
      email: document.getElementById('f_email').value,
      phone: document.getElementById('f_phone').value,
      data:  document.getElementById('f_data').value
    };
    const r = await fetch('/api/add', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(record)
    });
    const d = await r.json();
    const res = document.getElementById('result');
    res.style.display = 'block';
    if (d.status === 'success') {
      res.className = 'result success';
      res.textContent = '✅ ' + d.message;
      document.getElementById('f_name').value = '';
      document.getElementById('f_email').value = '';
      document.getElementById('f_phone').value = '';
      document.getElementById('f_data').value = '';
    } else if (d.status === 'duplicate') {
      res.className = 'result warn';
      res.textContent = '🔁 Duplicate blocked: ' + d.reason;
    } else {
      res.className = 'result error';
      res.textContent = '❌ Rejected: ' + d.reason;
    }
    refresh();
  }

  const BULK_DATA = [
    {name:"Gayathri B",     email:"gayathri@email.com",  phone:"+91 9876543210", data:"Cloud intern"},
    {name:"Ravi Kumar",     email:"ravi@email.com",       phone:"+91 9123456780", data:"Developer"},
    {name:"Priya S",        email:"priya@email.com",      phone:"+91 9988776655", data:"Designer"},
    {name:"Gayathri B",     email:"gayathri@email.com",  phone:"+91 9876543210", data:"Cloud intern"},  // exact dup
    {name:"Ravi Kumar",     email:"ravi@email.com",       phone:"+91 9123456780", data:"Developer"},    // exact dup
    {name:"",               email:"noname@email.com",     phone:"",               data:"Empty name"},   // invalid
    {name:"John Doe",       email:"not-an-email",         phone:"",               data:"Bad email"},    // invalid
    {name:"Ananya R",       email:"ananya@email.com",     phone:"+91 9001122334", data:"Analyst"},
    {name:"GAYATHRI B",     email:"gayathri@email.com",  phone:"",               data:"Upper case dup"}, // email dup
    {name:"Karthik M",      email:"karthik@email.com",   phone:"+91 9445566778", data:"Engineer"},
  ];

  async function runBulkTest() {
    const container = document.getElementById('bulkResult');
    container.innerHTML = '<div style="color:var(--muted);font-size:12px;padding:8px;">Running...</div>';
    const results = [];
    for (const rec of BULK_DATA) {
      const r = await fetch('/api/add', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(rec)
      });
      const d = await r.json();
      results.push({rec, d});
    }
    container.innerHTML = results.map(({rec,d}) => {
      const cls = d.status==='success' ? 'ok' : d.status==='duplicate' ? 'dup' : 'inv';
      const icon = d.status==='success' ? '✅' : d.status==='duplicate' ? '🔁' : '❌';
      const name = rec.name || '(empty)';
      const msg = d.message || d.reason || '';
      return `<div class="bulk-item ${cls}">${icon} ${name} — ${msg.slice(0,60)}</div>`;
    }).join('');
    refresh();
  }

  async function clearAll() {
    if (!confirm('Clear all records? This cannot be undone.')) return;
    await fetch('/api/clear', {method:'POST'});
    document.getElementById('result').style.display = 'none';
    document.getElementById('bulkResult').innerHTML = '';
    refresh();
  }

  function switchTab(tab, el) {
    currentTab = tab;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    el.classList.add('active');
    loadTable();
  }

  refresh();
  setInterval(refresh, 5000);
</script>
</body>
</html>
"""

# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/add", methods=["POST"])
def api_add():
    data = request.get_json()
    result = add_record(data)
    return jsonify(result)

@app.route("/api/records")
def api_records():
    return jsonify(get_all_records())

@app.route("/api/rejected")
def api_rejected():
    return jsonify(get_rejected())

@app.route("/api/stats")
def api_stats():
    return jsonify(get_stats())

@app.route("/api/clear", methods=["POST"])
def api_clear():
    clear_all()
    return jsonify({"status": "ok"})

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("╔══════════════════════════════════════════════╗")
    print("║  Data Redundancy Removal System              ║")
    print("║  CodeAlpha Internship Task 1                 ║")
    print("║  Running at → http://127.0.0.1:5000          ║")
    print("╚══════════════════════════════════════════════╝")
    app.run(debug=True, port=5000)
