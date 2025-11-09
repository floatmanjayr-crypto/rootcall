with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# Find the transfer function and add complete error logging
old = '''            r = await client.post(
                url,
                headers={"Authorization": f"Bearer {TELNYX_API_KEY}"},
                json={"to": to}
            )
            log.info("Transfer response: %s", r.status_code)
            return r.json() if r.text else {"ok": True}'''

new = '''            r = await client.post(
                url,
                headers={"Authorization": f"Bearer {TELNYX_API_KEY}"},
                json={"to": to}
            )
            log.info("Transfer response: %s", r.status_code)
            log.info("Transfer response body: %s", r.text)
            
            if r.status_code >= 400:
                log.error("Transfer FAILED: %s", r.text)
                return {"error": r.text, "status_code": r.status_code}
            
            return r.json() if r.text else {"ok": True}'''

content = content.replace(old, new)

with open('app/routers/badbot_screen.py', 'w') as f:
    f.write(content)

print("Added detailed transfer logging!")
