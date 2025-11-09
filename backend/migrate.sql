
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
