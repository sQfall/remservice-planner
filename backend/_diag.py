import sqlite3

conn = sqlite3.connect('data.db')
c = conn.cursor()

print("Checking route_segments table...")
c.execute('SELECT COUNT(*) FROM route_segments')
count = c.fetchone()[0]
print(f"Total segments: {count}")

if count > 0:
    c.execute('SELECT id, is_garage_segment, garage_segment_type FROM route_segments LIMIT 5')
    for row in c.fetchall():
        print(f"  ID: {row[0]}, IsGarage: {row[1]}, Type: {row[2]}")
else:
    print("No segments found in database.")

conn.close()
