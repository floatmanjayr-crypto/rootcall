# -*- coding: utf-8 -*-
"""
Apply standard Telnyx configuration to all connections
Based on requirements from uploaded config
"""
import os
import requests

# Load API key
with open('.env', 'r') as f:
    for line in f:
        if line.startswith('TELNYX_API_KEY='):
            TELNYX_API_KEY = line.split('=', 1)[1].strip()
            break

# Standard configuration requirements
REQUIRED_CONFIG = {
    "outbound_voice_profile_id": "2812952284193883196",
    "inbound_voice_enabled": True,
    "rtcp_settings": {
        "enabled": True,
        "capture_enabled": False,
        "report_frequency_seconds": 5
    },
    "dtmf_type": "RFC 2833",
    "encode_audio_type": "G722",
    "encrypted_media": "SRTP",
    "transport_protocol": "TLS"
}

print("="*60)
print("APPLYING STANDARD TELNYX CONFIGURATION")
print("="*60)

# Get all connections
print("\n1. Getting all Telnyx connections...")
response = requests.get(
    "https://api.telnyx.com/v2/connections",
    headers={"Authorization": f"Bearer {TELNYX_API_KEY}"}
)

if response.status_code != 200:
    print(f"Failed to get connections: {response.text}")
    exit(1)

connections = response.json().get('data', [])
print(f"Found {len(connections)} connections")

# Apply config to each
for conn in connections:
    conn_id = conn['id']
    conn_name = conn.get('connection_name', 'Unknown')
    
    print(f"\n{'='*60}")
    print(f"Connection: {conn_name} ({conn_id})")
    print(f"{'='*60}")
    
    # Check current config
    has_outbound = conn.get('outbound_voice_profile_id')
    print(f"  Current outbound profile: {has_outbound or 'NONE'}")
    
    if not has_outbound or has_outbound != REQUIRED_CONFIG['outbound_voice_profile_id']:
        print(f"  WARNING: Missing or wrong outbound profile!")
        print(f"  MANUAL FIX REQUIRED:")
        print(f"     1. Go to: https://portal.telnyx.com/#/app/connections")
        print(f"     2. Edit connection: {conn_id}")
        print(f"     3. Set Outbound Voice Profile: {REQUIRED_CONFIG['outbound_voice_profile_id']}")
        print(f"     4. Verify: Inbound Voice ENABLED")
        print(f"     5. Verify: DTMF = RFC 2833")
        print(f"     6. Verify: Audio Codec = G722")
        print(f"     7. Verify: Encryption = SRTP")
        print(f"     8. Verify: Transport = TLS")
        print(f"     9. Save")
    else:
        print(f"  OK: Outbound profile correct")

# Save standard config to .env
print(f"\n{'='*60}")
print("SAVING STANDARD CONFIG TO .ENV")
print(f"{'='*60}")

with open('.env', 'r') as f:
    env_lines = f.readlines()

# Remove old settings
env_lines = [line for line in env_lines 
             if not line.startswith('TELNYX_OUTBOUND_VOICE_PROFILE_ID=')
             and not line.startswith('TELNYX_STANDARD_CONFIG_')]

# Add new standard config
env_lines.append('\n# Telnyx Standard Configuration\n')
env_lines.append(f'TELNYX_OUTBOUND_VOICE_PROFILE_ID={REQUIRED_CONFIG["outbound_voice_profile_id"]}\n')
env_lines.append('TELNYX_STANDARD_CONFIG_APPLIED=true\n')

with open('.env', 'w') as f:
    f.writelines(env_lines)

print("OK: Standard configuration saved to .env")

print(f"\n{'='*60}")
print("NEXT STEPS")
print(f"{'='*60}")
print("\n1. Fix connection in Telnyx Portal (see warnings above)")
print("2. Test: Call +18135478530")
print("3. Should transfer to: +17543670370")
print("4. Update provisioning code for auto-config")
print(f"{'='*60}\n")
