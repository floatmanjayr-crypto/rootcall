-- Clear old tiers
TRUNCATE badbot_subscription_tiers CASCADE;

-- Insert new professional tiers
INSERT INTO badbot_subscription_tiers (name, price_monthly, max_shield_numbers, max_trusted_contacts, sms_alerts_included, email_alerts_included, call_recording, priority_support, created_at)
VALUES 
    ('Basic Protection', 34.99, 1, 10, true, false, false, false, NOW()),
    ('Smart AI Screening', 69.99, 1, 25, true, true, false, true, NOW()),
    ('Premium Family Shield', 124.99, 5, 50, true, true, true, true, NOW());
