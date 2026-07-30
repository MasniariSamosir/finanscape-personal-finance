import sqlite3

db_path = "instance/budget.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Gunakan tanda " karena transaction adalah keyword SQL
c.execute('PRAGMA table_info("transaction");')
columns = [col[1] for col in c.fetchall()]

if 'category_id' not in columns:
    c.execute('ALTER TABLE "transaction" ADD COLUMN category_id INTEGER;')
    print("Kolom category_id berhasil ditambahkan!")
else:
    print("Kolom category_id sudah ada.")

conn.commit()
conn.close()
