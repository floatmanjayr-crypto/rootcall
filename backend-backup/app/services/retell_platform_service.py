"""Retell Platform Service - Uses Working Endpoints"""
import logging
import requests
from typing import Optional, Dict
from app.config import settings

log = logging.getLogger(__name__)

class RetellPlatformService:
    """Manage Retell AI for multiple VoIP clients"""
    
    def __init__(self):
        self.api_key = settings.RETELL_API_KEY
        self.base_url = "https://api.retellai.com"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def create_client_agent(
        self, 
        client_name: str,
        system_prompt: str,
        greeting: str = "Hello! How can I help you?",
        voice: str = "11labs-Adrian"
    ) -> Optional[Dict]:
        """Create an AI agent for a client"""
        try:
            log.info(f"Creating agent for: {client_name}")
            
            # Step 1: Create Retell LLM
            llm_response = requests.post(
                f"{self.base_url}/create-retell-llm",
                json={
                    "general_prompt": system_prompt,
                    "begin_message": greeting,
                    "llm_model": "gpt-4.1"
                },
                headers=self.headers
            )
            
            if llm_response.status_code != 201:
                log.error(f"LLM failed: {llm_response.text}")
                return None
            
            llm_id = llm_response.json().get("llm_id")
            log.info(f"✅ LLM created: {llm_id}")
            
            # Step 2: Create Agent using working SDK approach
            from retell import Retell
            
            try:
                client = Retell(api_key=self.api_key)
                
                agent = client.agent.create(
                    agent_name=f"{client_name} AI",
                    voice_id=voice,
                    response_engine={
                        "type": "retell-llm",
                        "llm_id": llm_id
                    },
                    language="en-US",
                    enable_backchannel=True,
                    backchannel_frequency=0.8
                )
                
                agent_id = agent.agent_id
                log.info(f"✅ Agent created: {agent_id}")
                
                return {
                    "agent_id": agent_id,
                    "llm_id": llm_id,
                    "client_name": client_name,
                    "voice": voice
                }
                
            except Exception as sdk_error:
                log.error(f"SDK error: {sdk_error}")
                return None
        
        except Exception as e:
            log.error(f"Exception: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def list_agents(self) -> list:
        """List all agents"""
        try:
            from retell import Retell
            client = Retell(api_key=self.api_key)
            agents = client.agent.list()
            return [{"agent_id": a.agent_id, "agent_name": a.agent_name} for a in agents]
        except Exception as e:
            log.error(f"Failed: {e}")
            return []

# Global instance
retell_platform = RetellPlatformService()
