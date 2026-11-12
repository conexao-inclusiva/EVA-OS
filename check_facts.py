import sqlite3

conn = sqlite3.connect("data/databases/eva_long_term.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM facts WHERE user_id='admin'")
rows = cursor.fetchall()

if rows:
    print("✅ Fatos encontrados para admin:")
    for row in rows:
        print(row)
else:
    print("❌ Nenhum fato encontrado para admin.")

conn.close()