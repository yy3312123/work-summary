"""
每日工作总结 - 团队联网版
启动方式：python server.py
访问地址：http://localhost:5678
团队成员通过你的 IP 地址访问：http://你的IP:5678
"""
import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, g, send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'work_summary.db')


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

    db.execute('''INSERT INTO summaries (date, name, dept, today_work, plan, notes, updated_at)
                  VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                  ON CONFLICT(date, name) DO UPDATE SET
                  dept=excluded.dept, today_work=excluded.today_work,
                  plan=excluded.plan, notes=excluded.notes, updated_at=CURRENT_TIMESTAMP''',
               (date, name, dept, today_work, plan, notes))

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
            'updated_at': row['updated_at']
        }})

    rows = db.execute('SELECT name, dept, today_work, plan, notes, updated_at FROM summaries WHERE date=? ORDER BY updated_at DESC', (date,)).fetchall()
    results = []
    for row in rows:
        results.append({
            'name': row['name'], 'dept': row['dept'],
            'today_work': json.loads(row['today_work']),
            'plan': json.loads(row['plan']),
            'notes': row['notes'],
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


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5678))
    print('=' * 50)
    print('  每日工作总结 - 团队联网版 已启动')
    print(f'  访问地址：http://localhost:{port}')
    print('  按 Ctrl+C 停止服务')
    print('=' * 50)
    app.run(host='0.0.0.0', port=port, debug=False)
