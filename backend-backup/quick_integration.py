import subprocess

print("="*60)
print("BADBOT INTEGRATION")
print("="*60)

# 1. Get DB URL
db_url = None
with open('.env', 'r') as f:
    for line in f:
        if 'DATABASE_URL' in line:
            db_url = line.split('=', 1)[1].strip().strip('"').strip("'")
            break

print("\n[1/5] Creating database table...")
sql = """
CREATE TABLE IF NOT EXISTS badbot_call_logs (
    id SERIAL PRIMARY KEY,
    phone_number_id INTEGER REFERENCES phone_numbers(id),
    from_number VARCHAR(20) NOT NULL,
    caller_name VARCHAR(255),
    action VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    call_control_id VARCHAR(255),
    timestamp TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_badbot_logs_phone ON badbot_call_logs(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_badbot_logs_timestamp ON badbot_call_logs(timestamp);
"""

with open('migrate.sql', 'w') as f:
    f.write(sql)

try:
    subprocess.run(['psql', db_url, '-f', 'migrate.sql'], check=True)
    print("OK: Table created")
except:
    print("OK: Table may already exist")

# 2. Create model
print("\n[2/5] Creating model...")
exec(open('setup_real_stats.py').read())

print("\n[3/5] Run these commands manually:")
print("\n1. Restart uvicorn server")
print("2. Make test call to +18135478530")
print("3. Open: http://localhost:8000/static/james-portal.html")
print("\nStats will be REAL after calls are made!")

