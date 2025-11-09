# Quick script to add a client to the config file

# EDIT THESE VALUES:
TELNYX_NUMBER = "+18135478530"      # Your Telnyx number (what clients forward to)
CLIENT_CELL = "+18135551234"        # Client's actual cell phone
CLIENT_NAME = "Test Senior Client"
RETELL_AGENT_ID = "agent_abc123"    # Your Retell agent ID (from Retell dashboard)
RETELL_DID = "+18135478530"         # Can be same as TELNYX_NUMBER or different

# Add to the CLIENT_LINES dictionary
config_addition = f'''
# Real Client Added: {CLIENT_NAME}
CLIENT_LINES["{TELNYX_NUMBER}"] = {{
    "client_cell": "{CLIENT_CELL}",
    "client_name": "{CLIENT_NAME}",
    "retell_agent_id": "{RETELL_AGENT_ID}",
    "retell_did": "{RETELL_DID}",
    "trusted_contacts": [
        # Add trusted numbers like: "+18135554321",
    ],
    "caregiver_cell": ""  # Optional caregiver SMS alerts
}}
'''

# Append to the config file
with open("app/services/client_config.py", "a") as f:
    f.write(config_addition)

print("✅ Client added successfully!")
print(f"   Telnyx Number: {TELNYX_NUMBER}")
print(f"   Client Cell: {CLIENT_CELL}")
print(f"   Retell Agent: {RETELL_AGENT_ID}")
