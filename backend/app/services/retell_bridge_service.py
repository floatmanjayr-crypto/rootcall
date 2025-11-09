"""Automated Retell Bridge - No Phone Registration Required"""
import asyncio
import websockets
import json
import base64
import logging
from typing import Dict, Optional
import httpx
from app.config import settings

log = logging.getLogger(__name__)

class RetellBridgeService:
    """Bridge Telnyx calls to Retell without phone registration"""
    
    def __init__(self):
        self.api_key = settings.RETELL_API_KEY
        self.telnyx_key = settings.TELNYX_API_KEY
        self.active_bridges = {}
    
    async def create_retell_web_call(self, agent_id: str, metadata: Dict) -> Optional[Dict]:
        """Create a Retell web call"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.retellai.com/v2/create-web-call",
                    json={
                        "agent_id": agent_id,
                        "metadata": metadata
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    timeout=10.0
                )
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    log.info(f"✅ Created Retell web call: {data.get('call_id')}")
                    return data
                else:
                    log.error(f"Failed to create web call: {response.text}")
                    return None
        
        except Exception as e:
            log.error(f"Exception creating web call: {e}")
            return None
    
    async def start_telnyx_media_stream(self, call_control_id: str, stream_url: str):
        """Start media streaming on Telnyx call"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.telnyx.com/v2/calls/{call_control_id}/actions/streaming_start",
                    json={
                        "stream_url": stream_url,
                        "stream_track": "both_tracks",
                        "enable_dialogflow": False
                    },
                    headers={
                        "Authorization": f"Bearer {self.telnyx_key}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    log.info(f"✅ Started Telnyx media stream")
                    return True
                else:
                    log.error(f"Failed to start stream: {response.text}")
                    return False
        
        except Exception as e:
            log.error(f"Exception starting stream: {e}")
            return False
    
    async def bridge_audio(
        self,
        call_control_id: str,
        retell_call_data: Dict
    ):
        """Bridge audio between Telnyx and Retell"""
        
        call_id = retell_call_data.get("call_id")
        access_token = retell_call_data.get("access_token")
        
        # Connect to Retell's websocket
        retell_ws_url = f"wss://api.retellai.com/audio-websocket/{call_id}?access_token={access_token}"
        
        try:
            async with websockets.connect(retell_ws_url) as retell_ws:
                log.info(f"Connected to Retell websocket for call {call_id}")
                
                # Store bridge info
                self.active_bridges[call_control_id] = {
                    "retell_ws": retell_ws,
                    "call_id": call_id
                }
                
                # Handle messages
                async for message in retell_ws:
                    # Forward audio from Retell
                    # This would send to Telnyx media stream
                    pass
        
        except Exception as e:
            log.error(f"Audio bridge error: {e}")
        finally:
            if call_control_id in self.active_bridges:
                del self.active_bridges[call_control_id]

# Global instance
retell_bridge = RetellBridgeService()
