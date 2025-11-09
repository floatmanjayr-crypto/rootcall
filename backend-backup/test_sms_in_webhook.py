# -*- coding: utf-8 -*-
import asyncio
import httpx
import os

async def test_sms():
    with open('.env', 'r') as f:
        for line in f:
            if 'TELNYX_API_KEY=' in line:
                TELNYX_API_KEY = line.split('=', 1)[1].strip()
                break
    
    url = "https://api.telnyx.com/v2/messages"
    
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(
                url,
                headers={"Authorization": f"Bearer {TELNYX_API_KEY}"},
                json={
                    "from": "+18135478530",
                    "to": "+17543670370",
                    "text": "[BadBot] Test: Unknown caller being screened by AI"
                }
            )
            print(f"Status: {r.status_code}")
            print(f"Response: {r.text}")
            
            if r.status_code in [200, 201, 202]:
                print("\nSUCCESS! Check James phone!")
            else:
                print("\nFAILED!")
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(test_sms())
