-- Subscription Tiers
CREATE TABLE IF NOT EXISTS badbot_subscription_tiers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    price_monthly DECIMAL(10,2) NOT NULL,
    max_shield_numbers INTEGER NOT NULL,
    max_trusted_contacts INTEGER NOT NULL,
    sms_alerts_included BOOLEAN DEFAULT true,
    email_alerts_included BOOLEAN DEFAULT false,
    call_recording BOOLEAN DEFAULT false,
    priority_support BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO badbot_subscription_tiers (name, price_monthly, max_shield_numbers, max_trusted_contacts, sms_alerts_included, email_alerts_included, call_recording, priority_support)
VALUES 
    ('Basic Shield', 9.99, 1, 5, true, false, false, false),
    ('Family Shield', 19.99, 3, 15, true, true, false, false),
    ('Premium Shield', 39.99, 10, 50, true, true, true, true)
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS badbot_user_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    tier_id INTEGER REFERENCES badbot_subscription_tiers(id),
    status VARCHAR(20) DEFAULT 'active',
    stripe_subscription_id VARCHAR(255),
    current_period_end TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE badbot_configs ADD COLUMN IF NOT EXISTS shield_number_nickname VARCHAR(100);
ALTER TABLE badbot_configs ADD COLUMN IF NOT EXISTS is_primary BOOLEAN DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_user_subscriptions ON badbot_user_subscriptions(user_id);
