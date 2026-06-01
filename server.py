"""
每日工作总结 - 团队联网版
启动方式：python server.py
访问地址：http://localhost:5678
团队成员通过你的 IP 地址访问：http://你的IP:5678
"""
import os
import sqlite3
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, g, send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'work_summary.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute('''CREATE TABLE IF NOT EXISTS summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        name TEXT NOT NULL,
        dept TEXT DEFAULT '',
        today_work TEXT DEFAULT '[]',
        plan TEXT DEFAULT '[]',
        notes TEXT DEFAULT '',
        photos TEXT DEFAULT '[]',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(date, name)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS members (
        name TEXT PRIMARY KEY,
        dept TEXT DEFAULT '',
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    db.commit()
    db.close()


# ===== API =====

@app.route('/api/summary', methods=['POST'])
def save_summary():
    data = request.get_json()
    if not data:
        return jsonify({'ok': False, 'error': '数据为空'}), 400
    date = data.get('date', '').strip()
    name = data.get('name', '').strip()
    if not date or not name:
        return jsonify({'ok': False, 'error': '日期和姓名不能为空'}), 400

    db = get_db()
    dept = data.get('dept', '').strip()
    today_work = json.dumps(data.get('today_work', []), ensure_ascii=False)
    plan = json.dumps(data.get('plan', []), ensure_ascii=False)
    notes = data.get('notes', '').strip()
    photos = json.dumps(data.get('photos', []), ensure_ascii=False)

    db.execute('''INSERT INTO summaries (date, name, dept, today_work, plan, notes, photos, updated_at)
                  VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                  ON CONFLICT(date, name) DO UPDATE SET
                  dept=excluded.dept, today_work=excluded.today_work,
                  plan=excluded.plan, notes=excluded.notes, photos=excluded.photos, updated_at=CURRENT_TIMESTAMP''',
               (date, name, dept, today_work, plan, notes, photos))

    db.execute('INSERT OR IGNORE INTO members (name, dept) VALUES (?, ?)', (name, dept))
    if dept:
        db.execute('UPDATE members SET dept=? WHERE name=? AND dept=""', (dept, name))
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/summary', methods=['GET'])
def get_summary():
    date = request.args.get('date', '').strip()
    name = request.args.get('name', '').strip()
    db = get_db()

    if name:
        row = db.execute('SELECT * FROM summaries WHERE date=? AND name=?', (date, name)).fetchone()
        if not row:
            return jsonify({'ok': True, 'data': None})
        return jsonify({'ok': True, 'data': {
            'name': row['name'], 'dept': row['dept'],
            'today_work': json.loads(row['today_work']),
            'plan': json.loads(row['plan']),
            'notes': row['notes'],
            'photos': json.loads(row['photos']),
            'updated_at': row['updated_at']
        }})

    rows = db.execute('SELECT name, dept, today_work, plan, notes, photos, updated_at FROM summaries WHERE date=? ORDER BY updated_at DESC', (date,)).fetchall()
    results = []
    for row in rows:
        results.append({
            'name': row['name'], 'dept': row['dept'],
            'today_work': json.loads(row['today_work']),
            'plan': json.loads(row['plan']),
            'notes': row['notes'],
            'photos': json.loads(row['photos']),
            'updated_at': row['updated_at']
        })
    return jsonify({'ok': True, 'data': results})


@app.route('/api/members', methods=['GET'])
def get_members():
    db = get_db()
    rows = db.execute('SELECT name, dept FROM members ORDER BY name').fetchall()
    return jsonify({'ok': True, 'data': [{'name': r['name'], 'dept': r['dept']} for r in rows]})


@app.route('/api/dates', methods=['GET'])
def get_dates():
    db = get_db()
    rows = db.execute('SELECT DISTINCT date FROM summaries ORDER BY date DESC LIMIT 60').fetchall()
    return jsonify({'ok': True, 'data': [r['date'] for r in rows]})


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/upload', methods=['POST'])
def upload_photo():
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': '未选择文件'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'ok': False, 'error': '文件名为空'}), 400
    if not allowed_file(file.filename):
        return jsonify({'ok': False, 'error': '仅支持 jpg/png/gif/webp/bmp 格式'}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOAD_DIR, filename))
    return jsonify({'ok': True, 'filename': filename})


@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route('/api/delete-photo', methods=['POST'])
def delete_photo():
    data = request.get_json()
    filename = (data or {}).get('filename', '')
    if not filename:
        return jsonify({'ok': False, 'error': '缺少文件名'}), 400
    path = os.path.join(UPLOAD_DIR, filename)
    if os.path.isfile(path):
        os.remove(path)
    return jsonify({'ok': True})


@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


# 启动时自动初始化数据库
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5678))
    print('=' * 50)
    print('  每日工作总结 - 团队联网版 已启动')
    print(f'  访问地址：http://localhost:{port}')
    print('  按 Ctrl+C 停止服务')
    print('=' * 50)
    app.run(host='0.0.0.0', port=port, debug=False)
