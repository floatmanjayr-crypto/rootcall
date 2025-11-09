import re

with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# Find the "Unknown -> Send to Retell" section and replace it
old_code = '''        # 3) Unknown -> Send to Retell
        if retell_did:
            log.info("[UNKNOWN] Transferring %s to Retell: %s", from_num, retell_did)
            result = await telnyx_transfer(ccid, retell_did)
            return {"status": "retell_transfer", "from": from_num, "retell_did": retell_did, "result": result}'''

new_code = '''        # 3) Unknown -> Transfer DIRECTLY to client (bypass Retell for now)
        log.info("[UNKNOWN] Transferring %s DIRECTLY to client: %s", from_num, client_cell)
        if client_cell:
            send_sms_alert(client_cell, f"[BadBot] Unknown caller {from_num} - transferred")
            result = await telnyx_transfer(ccid, client_cell)
            return {"status": "unknown_transferred_direct", "from": from_num, "to": client_cell, "result": result}'''

content = content.replace(old_code, new_code)

with open('app/routers/badbot_screen.py', 'w') as f:
    f.write(content)

print("Updated! Now ALL calls (except spam) transfer directly to client.")
