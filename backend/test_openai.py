import asyncio
from app.services.openai_service import openai_service

async def test():
    print("\n=== Testing OpenAI Integration ===\n")
    
    # Test 1: TTS
    print("1. Testing Text-to-Speech...")
    try:
        audio = await openai_service.text_to_speech("Hello! This is a test.")
        print(f"   SUCCESS: Generated {len(audio)} bytes of audio")
    except Exception as e:
        print(f"   FAILED: {e}")
    
    # Test 2: GPT
    print("\n2. Testing GPT-4o-mini...")
    try:
        response = await openai_service.get_ai_response(
            "I need to book an appointment",
            "test-123"
        )
        print(f"   SUCCESS: AI said: {response}")
    except Exception as e:
        print(f"   FAILED: {e}")
    
    print("\n=== Test Complete ===\n")

if __name__ == "__main__":
    asyncio.run(test())
