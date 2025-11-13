import os
import httpx
import asyncio

TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")

async def test():
    # Get active calls first
    async with httpx.AsyncClient(timeout=10) as client:
        # List calls
        r = await client.get(
            "https://api.telnyx.com/v2/calls",
            headers={"Authorization": f"Bearer {TELNYX_API_KEY}"}
        )
        print("Active calls:", r.status_code)
        if r.status_code == 200:
            calls = r.json().get('data', [])
            print(f"Found {len(calls)} active calls")
            for call in calls:
                print(f"  - {call.get('call_control_id')} | {call.get('from')} -> {call.get('to')}")
                
                # Try to transfer this call
                ccid = call.get('call_control_id')
                if ccid:
                    print(f"\nAttempting transfer of {ccid}...")
                    transfer_r = await client.post(
                        f"https://api.telnyx.com/v2/calls/{ccid}/actions/transfer",
                        headers={"Authorization": f"Bearer {TELNYX_API_KEY}"},
                        json={"to": "+17543670370"}
                    )
                    print(f"Transfer response: {transfer_r.status_code}")
                    print(f"Response body: {transfer_r.text}")
        else:
            print(f"Error: {r.text}")

asyncio.run(test())
