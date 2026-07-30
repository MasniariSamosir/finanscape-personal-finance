import sqlite3

conn = sqlite3.connect("budget.db")
c = conn.cursor()

# Cek apakah kolom category_id sudah ada
c.execute("PRAGMA table_info('transaction')")
columns = [col[1] for col in c.fetchall()]
if 'category_id' not in columns:
    c.execute("ALTER TABLE 'transaction' ADD COLUMN category_id INTEGER")
    print("Kolom 'category_id' berhasil ditambahkan.")
else:
    print("Kolom 'category_id' sudah ada.")

conn.commit()
conn.close()
