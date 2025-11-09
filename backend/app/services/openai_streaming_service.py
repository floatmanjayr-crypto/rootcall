"""OpenAI Streaming Service for Low-Latency TTS"""
import logging
import uuid
import os
import httpx
from openai import AsyncOpenAI
from app.config import settings

log = logging.getLogger(__name__)

class OpenAIStreamingService:
    """Streaming TTS for faster response"""
    
    def __init__(self):
        self.async_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.conversation_history = {}
    
    async def text_to_speech_streaming(self, text: str, voice: str = "nova") -> str:
        """
        Generate TTS with streaming and save to file
        Returns filepath immediately after starting generation
        """
        try:
            log.info(f"Streaming TTS: {text[:50]}...")
            
            # Generate filename
            filename = f"{uuid.uuid4()}.mp3"
            filepath = f"static/audio/{filename}"
            
            # Stream response
            response = await self.async_client.audio.speech.create(
                model="tts-1",  # Fast model
                voice=voice,
                input=text,
                response_format="mp3"
            )
            
            # Save streaming content
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            log.info(f"Streamed {len(response.content)} bytes")
            return f"/audio/{filename}"
        
        except Exception as e:
            log.error(f"Streaming TTS failed: {e}")
            return None
    
    async def transcribe_audio(self, audio_url: str) -> str:
        """Transcribe with Whisper"""
        try:
            log.info(f"Transcribing: {audio_url}")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(audio_url)
                audio_bytes = response.content
            
            temp_file = os.path.join(os.environ.get("TEMP", "."), f"{uuid.uuid4()}.mp3")
            with open(temp_file, "wb") as f:
                f.write(audio_bytes)
            
            with open(temp_file, "rb") as audio_file:
                transcript = await self.async_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en",
                    response_format="text"
                )
            
            # Cleanup
            try:
                os.remove(temp_file)
            except:
                pass
            
            log.info(f"Whisper: {transcript}")
            return transcript
        
        except Exception as e:
            log.error(f"Transcription failed: {e}")
            return ""
    
    async def get_ai_response_streaming(self, user_message: str, call_id: str, system_prompt: str = None) -> str:
        """Get GPT response with streaming"""
        try:
            if call_id not in self.conversation_history:
                default_prompt = "You are a helpful phone assistant. Keep responses under 30 words. Be concise and friendly."
                self.conversation_history[call_id] = [
                    {"role": "system", "content": system_prompt or default_prompt}
                ]
            
            self.conversation_history[call_id].append({
                "role": "user",
                "content": user_message
            })
            
            # Use streaming for faster first token
            response = await self.async_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.conversation_history[call_id],
                temperature=0.7,
                max_tokens=60,
                stream=False  # We'll implement full streaming later
            )
            
            ai_message = response.choices[0].message.content
            
            self.conversation_history[call_id].append({
                "role": "assistant",
                "content": ai_message
            })
            
            log.info(f"GPT: {ai_message}")
            return ai_message
        
        except Exception as e:
            log.error(f"GPT failed: {e}")
            return "I'm sorry, could you repeat that?"
    
    def clear_conversation(self, call_id: str):
        """Clear conversation history"""
        if call_id in self.conversation_history:
            del self.conversation_history[call_id]

# Global instance
streaming_service = OpenAIStreamingService()
