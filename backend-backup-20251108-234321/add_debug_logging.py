with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# Add more logging to the transfer function
old_transfer = '''async def telnyx_transfer(ccid: str, to: str):
    """Transfer call to destination"""
    if DRY_RUN:
        log.info("[DRY_RUN] transfer ccid=%s to=%s", ccid, to)
        return {"ok": True, "dry_run": True}

    if not TELNYX_API_KEY:
        log.error("Missing TELNYX_API_KEY")
        return {"error": "Missing API key"}

    url = f"https://api.telnyx.com/v2/calls/{ccid}/actions/transfer"'''

new_transfer = '''async def telnyx_transfer(ccid: str, to: str):
    """Transfer call to destination"""
    log.info("===== TRANSFER CALLED =====")
    log.info("CCID: %s", ccid)
    log.info("TO: %s", to)
    log.info("DRY_RUN: %s", DRY_RUN)
    
    if DRY_RUN:
        log.info("[DRY_RUN] transfer ccid=%s to=%s", ccid, to)
        return {"ok": True, "dry_run": True}

    if not TELNYX_API_KEY:
        log.error("Missing TELNYX_API_KEY")
        return {"error": "Missing API key"}

    url = f"https://api.telnyx.com/v2/calls/{ccid}/actions/transfer"
    log.info("Transfer URL: %s", url)'''

content = content.replace(old_transfer, new_transfer)

with open('app/routers/badbot_screen.py', 'w') as f:
    f.write(content)

print("Added debug logging!")
