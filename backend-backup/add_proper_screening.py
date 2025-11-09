# -*- coding: utf-8 -*-
"""
Add proper call screening - agent asks who's calling first
"""

with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# The problem: We're transferring on call.answered immediately
# Solution: Transfer to Retell agent first for screening

old_code = '''        # 3) Unknown -> Greet then transfer to client
        log.info("[UNKNOWN] Greeting then transferring %s to client: %s", from_num, client_cell)
        if client_cell:
            # Say "One moment please" before transferring
            await telnyx_speak(ccid, "One moment please, transferring your call.")
            # Wait a moment for speech to complete
            import asyncio
            await asyncio.sleep(2)
            # Now transfer
            result = await telnyx_transfer(ccid, client_cell)
            return {"status": "greeted_and_transferred", "from": from_num, "to": client_cell}'''

new_code = '''        # 3) Unknown -> Send to Retell agent for screening
        if retell_did:
            log.info("[UNKNOWN] Sending %s to Retell agent for screening: %s", from_num, retell_did)
            result = await telnyx_transfer(ccid, retell_did)
            return {"status": "sent_to_retell_screening", "from": from_num, "retell_did": retell_did}
        
        # 4) No Retell configured -> Direct transfer with greeting
        log.info("[NO_RETELL] Direct transfer %s to client: %s", from_num, client_cell)
        if client_cell:
            # Say "One moment please" before transferring
            await telnyx_speak(ccid, "One moment please, transferring your call.")
            # Wait a moment for speech to complete
            import asyncio
            await asyncio.sleep(2)
            # Now transfer
            result = await telnyx_transfer(ccid, client_cell)
            return {"status": "direct_transferred", "from": from_num, "to": client_cell}'''

if old_code in content:
    content = content.replace(old_code, new_code)
    
    with open('app/routers/badbot_screen.py', 'w') as f:
        f.write(content)
    
    print("✅ Updated to use Retell screening!")
    print("\nNow flow is:")
    print("1. Call comes to +18135478530")
    print("2. Telnyx answers")
    print("3. Transfer to Retell agent")
    print("4. Retell asks: 'Who's calling?'")
    print("5. Retell decides to transfer")
    print("6. Retell transfers to +17543670370")
else:
    print("⚠️  Pattern not found - showing current config...")

print("\n" + "="*60)
print("CONFIGURATION CHECK")
print("="*60)

# Check if retell_did is configured
print("\nChecking if Retell DID is configured...")
print("Run: python -c \"from app.services.client_config import get_client_config; print(get_client_config('+18135478530'))\"")

print("\n" + "="*60)
print("IF RETELL DID IS MISSING")
print("="*60)
print("You need to add retell_did to BadBot config in database")
print("The Retell number that has the transfer tool configured")
print("="*60)
