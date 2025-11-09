from openai import OpenAI
from typing import List, Dict
from app.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


class AIAgentService:
    
    @staticmethod
    def process_speech_to_text(audio_data: bytes) -> str:
        """Convert speech to text using Whisper"""
        try:
            # In production, save audio_data to temp file first
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_data
            )
            return transcript.text
        except Exception as e:
            print(f"Error in speech to text: {e}")
            return ""
    
    @staticmethod
    def generate_response(
        user_message: str,
        system_prompt: str,
        conversation_history: List[Dict] = None,
        temperature: float = 0.7,
        max_tokens: int = 150
    ) -> str:
        """Generate AI response based on user input"""
        try:
            messages = [{"role": "system", "content": system_prompt}]
            
            if conversation_history:
                messages.extend(conversation_history)
            
            messages.append({"role": "user", "content": user_message})
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error generating response: {e}")
            return "I apologize, but I'm having trouble processing your request. Could you please repeat that?"
    
    @staticmethod
    def text_to_speech(text: str, voice_model: str = "en-US-Neural2-F") -> bytes:
        """Convert text to speech (placeholder - integrate with Google TTS or ElevenLabs)"""
        # TODO: Integrate with Google Cloud TTS or ElevenLabs
        # For now, return placeholder
        print(f"TTS: {text}")
        return b""
    
    @staticmethod
    def detect_intent(user_message: str, possible_intents: List[str]) -> str:
        """Detect user intent from message"""
        try:
            prompt = f"""Classify the following message into one of these intents: {', '.join(possible_intents)}
            
Message: {user_message}

Respond with only the intent name, nothing else."""
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=10
            )
            
            return response.choices[0].message.content.strip().lower()
        except Exception as e:
            print(f"Error detecting intent: {e}")
            return "unknown"
    
    @staticmethod
    def extract_information(user_message: str, fields: List[str]) -> Dict:
        """Extract specific information from user message"""
        try:
            prompt = f"""Extract the following information from the message: {', '.join(fields)}
            
Message: {user_message}

Respond in JSON format with the field names as keys. If information is not found, use null."""
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=100
            )
            
            import json
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Error extracting information: {e}")
            return {}
