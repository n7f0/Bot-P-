import sqlite3
import datetime
import json
import os

DB_PATH = "/app/data/bot.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS welcome_messages (
            user_id INTEGER PRIMARY KEY,
            message TEXT,
            image_url TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            channel_id INTEGER,
            message TEXT,
            schedule_time TEXT,
            repeat_interval INTEGER,
            active INTEGER DEFAULT 1
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS ticket_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_channel_id INTEGER,
            user_id INTEGER,
            rating INTEGER,
            comment TEXT,
            created_at TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS moderation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT,
            moderator_id INTEGER,
            target_id INTEGER,
            reason TEXT,
            created_at TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS open_tickets (
            user_id INTEGER,
            channel_id INTEGER,
            opened_at TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def get_welcome_message(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT message, image_url FROM welcome_messages WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row if row else None

def set_welcome_message(user_id, message, image_url=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO welcome_messages (user_id, message, image_url) VALUES (?, ?, ?)",
              (user_id, message, image_url))
    conn.commit()
    conn.close()

def add_scheduled_event(event_type, channel_id, message, schedule_time, repeat_interval=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO scheduled_events (event_type, channel_id, message, schedule_time, repeat_interval, active) VALUES (?, ?, ?, ?, ?, ?)",
              (event_type, channel_id, message, schedule_time, repeat_interval, 1))
    conn.commit()
    conn.close()

def get_active_events():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM scheduled_events WHERE active = 1")
    rows = c.fetchall()
    conn.close()
    return rows

def deactivate_event(event_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE scheduled_events SET active = 0 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()

def add_ticket_feedback(ticket_channel_id, user_id, rating, comment):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO ticket_feedback (ticket_channel_id, user_id, rating, comment, created_at) VALUES (?, ?, ?, ?, ?)",
              (ticket_channel_id, user_id, rating, comment, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

def log_moderation(action, moderator_id, target_id, reason):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO moderation_logs (action, moderator_id, target_id, reason, created_at) VALUES (?, ?, ?, ?, ?)",
              (action, moderator_id, target_id, reason, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

def add_open_ticket(user_id, channel_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO open_tickets (user_id, channel_id, opened_at) VALUES (?, ?, ?)",
              (user_id, channel_id, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

def remove_open_ticket(channel_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM open_tickets WHERE channel_id = ?", (channel_id,))
    conn.commit()
    conn.close()

def count_user_tickets_last_hours(user_id, hours=8):
    conn = get_db()
    c = conn.cursor()
    since = (datetime.datetime.now() - datetime.timedelta(hours=hours)).isoformat()
    c.execute("SELECT COUNT(*) FROM open_tickets WHERE user_id = ? AND opened_at > ?", (user_id, since))
    count = c.fetchone()[0]
    conn.close()
    return count