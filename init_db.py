
import sqlite3
conn = sqlite3.connect('nyaysetu_messages.db')
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, direction TEXT, message TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
conn.commit()
conn.close()
print("DB initialized: nyaysetu_messages.db")
