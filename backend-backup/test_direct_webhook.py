from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()

@app.post("/test-webhook")
async def test_webhook(request: Request):
    body = await request.json()
    print("="*60)
    print("WEBHOOK RECEIVED!")
    print("="*60)
    print(f"Event: {body.get('data', {}).get('event_type')}")
    print(f"From: {body.get('data', {}).get('payload', {}).get('from', {}).get('phone_number')}")
    print(f"To: {body.get('data', {}).get('payload', {}).get('to', {}).get('phone_number')}")
    return {"status": "ok"}

if __name__ == "__main__":
    print("Starting test webhook on port 8001...")
    print("Update Telnyx to: https://your-ngrok/test-webhook")
    uvicorn.run(app, host="0.0.0.0", port=8001)
