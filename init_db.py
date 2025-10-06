import sqlite3

conn = sqlite3.connect('kas.db')
c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS kas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT NOT NULL,
    jumlah INTEGER NOT NULL,
    tanggal TEXT NOT NULL
)
''')

conn.commit()
conn.close()
print("Database and table created successfully.")