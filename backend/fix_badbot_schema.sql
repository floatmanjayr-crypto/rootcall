-- Make retell fields nullable since they're optional for BadBot
ALTER TABLE badbot_configs ALTER COLUMN retell_agent_id DROP NOT NULL;
ALTER TABLE badbot_configs ALTER COLUMN retell_did DROP NOT NULL;
