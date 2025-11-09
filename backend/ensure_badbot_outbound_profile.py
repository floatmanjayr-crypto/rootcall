# -*- coding: utf-8 -*-
"""
Ensure BadBot Telnyx connection has outbound voice profile for transfers
This is SEPARATE from Retell Elastic SIP Trunk configuration
"""
import os
import requests

# Load API key
with open('.env', 'r') as f:
    for line in f:
        if line.startswith('TELNYX_API_KEY='):
            TELNYX_API_KEY = line.split('=', 1)[1].strip()
            break

BADBOT_CONNECTION_ID = "2812968115544000352"
OUTBOUND_PROFILE_ID = "2812952284193883196"

print("="*60)
print("BADBOT TELNYX CONNECTION - OUTBOUND PROFILE SETUP")
print("="*60)

print(f"\nConnection ID: {BADBOT_CONNECTION_ID}")
print(f"Outbound Profile: {OUTBOUND_PROFILE_ID}")

print("\n" + "="*60)
print("MANUAL SETUP REQUIRED")
print("="*60)
print("\n1. Go to: https://portal.telnyx.com/#/app/connections")
print(f"2. Find connection: {BADBOT_CONNECTION_ID}")
print("3. Click 'Edit'")
print("4. Scroll to 'Outbound' section")
print(f"5. Select Outbound Voice Profile: {OUTBOUND_PROFILE_ID}")
print("6. Click 'Save'")

print("\n" + "="*60)
print("TEST AFTER SETUP")
print("="*60)
print("Call: +18135478530")
print("Should transfer to: +17543670370")

print("\n" + "="*60)
print("SAVING CONFIG FOR FUTURE AUTOMATON")
print("="*60)

# Save to .env for future phone number provisioning
with open('.env', 'r') as f:
    env_lines = f.readlines()

# Remove old
env_lines = [line for line in env_lines 
             if not line.startswith('TELNYX_BADBOT_CONNECTION_ID=')
             and not line.startswith('TELNYX_BADBOT_OUTBOUND_PROFILE=')]

# Add new
env_lines.append('\n# BadBot Telnyx Configuration\n')
env_lines.append(f'TELNYX_BADBOT_CONNECTION_ID={BADBOT_CONNECTION_ID}\n')
env_lines.append(f'TELNYX_BADBOT_OUTBOUND_PROFILE={OUTBOUND_PROFILE_ID}\n')

with open('.env', 'w') as f:
    f.writelines(env_lines)

print("OK: Configuration saved to .env")
print("\nAll NEW BadBot phone numbers will use this configuration automatically.")
print("="*60)
