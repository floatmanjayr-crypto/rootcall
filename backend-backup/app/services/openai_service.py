"""OpenAI Service for Conversational AI"""
import logging
import os
import uuid
import httpx
from openai import OpenAI, AsyncOpenAI
from app.config import settings

log = logging.getLogger(__name__)

class OpenAIService:
    """Complete conversational AI using OpenAI"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.async_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.conversation_history = {}
    
    # ==================== SPEECH-TO-TEXT ====================
    
    async def transcribe_audio(self, audio_url: str) -> str:
        """
        Transcribe audio using Whisper
        
        Args:
            audio_url: URL to audio file (mp3, wav, etc)
        
        Returns:
            Transcribed text
        """
        try:
            log.info(f"Transcribing audio from {audio_url}")
            
            # Download audio file
            async with httpx.AsyncClient() as client:
                response = await client.get(audio_url)
                audio_bytes = response.content
            
            # Save temporarily
            temp_file = os.path.join(os.environ.get("TEMP", "."), f"{uuid.uuid4()}.mp3")
            with open(temp_file, "wb") as f:
                f.write(audio_bytes)
            
            # Transcribe with Whisper
            with open(temp_file, "rb") as audio_file:
                transcript = await self.async_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en",  # Auto-detect if None
                    response_format="text"
                )
            
            log.info(f"Whisper transcription: {transcript}")
            return transcript
        
        except Exception as e:
            log.error(f"Whisper transcription failed: {e}", exc_info=True)
            return ""
    
    # ==================== LLM (CONVERSATION) ====================
    
    async def get_ai_response(
        self,
        user_message: str,
        call_id: str,
        system_prompt: str = None
    ) -> str:
        """
        Get conversational response from GPT-4o-mini
        
        Args:
            user_message: What the user said
            call_id: Unique call identifier
            system_prompt: Optional custom instructions
        
        Returns:
            AI response text
        """
        try:
            # Initialize conversation if new
            if call_id not in self.conversation_history:
                default_prompt = """You are a helpful phone assistant.
Keep responses under 30 words.
Be friendly, professional, and concise.
If asked to do something, confirm you'll help."""
                
                self.conversation_history[call_id] = [
                    {
                        "role": "system",
                        "content": system_prompt or default_prompt
                    }
                ]
            
            # Add user message
            self.conversation_history[call_id].append({
                "role": "user",
                "content": user_message
            })
            
            # Get AI response
            response = await self.async_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.conversation_history[call_id],
                temperature=0.7,
                max_tokens=80  # Keep responses short
            )
            
            ai_message = response.choices[0].message.content
            
            # Add to history
            self.conversation_history[call_id].append({
                "role": "assistant",
                "content": ai_message
            })
            
            log.info(f"GPT response: {ai_message}")
            return ai_message
        
        except Exception as e:
            log.error(f"GPT failed: {e}", exc_info=True)
            return "I'm sorry, could you repeat that?"
    
    # ==================== TEXT-TO-SPEECH ====================
    
    async def text_to_speech(
        self,
        text: str,
        voice: str = "nova"
    ) -> bytes:
        """
        Convert text to speech using OpenAI TTS
        
        Args:
            text: Text to speak
            voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
        
        Returns:
            Audio bytes (MP3)
        """
        try:
            log.info(f"Generating speech: {text[:50]}...")
            
            response = await self.async_client.audio.speech.create(
                model="tts-1",  # High quality
                voice=voice,
                input=text,
                speed=1.0
            )
            
            # Get audio bytes
            audio_bytes = response.content
            
            log.info(f"Generated {len(audio_bytes)} bytes of audio")
            return audio_bytes
        
        except Exception as e:
            log.error(f"TTS failed: {e}", exc_info=True)
            return b""
    
    # ==================== UTILITY ====================
    
    def clear_conversation(self, call_id: str):
        """Clear conversation history for a call"""
        if call_id in self.conversation_history:
            del self.conversation_history[call_id]
            log.info(f"Cleared conversation for {call_id}")
    
    def get_conversation_history(self, call_id: str) -> list:
        """Get full conversation history"""
        return self.conversation_history.get(call_id, [])

# Global instance
openai_service = OpenAIService()
