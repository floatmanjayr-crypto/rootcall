# -*- coding: utf-8 -*-
"""
Add this to app/routers/badbot_screen.py
"""

webhook_code = '''
# Add this new endpoint to badbot_screen.py

@router.post("/retell/call-analyzed")
async def retell_call_analyzed(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Retell webhook: Called after agent finishes screening
    If agent determined call is legitimate, transfer it
    """
    call_id = data.get("call_id")
    call_type = data.get("call_type")  # "agent_decided_to_transfer" or "ended"
    transcript = data.get("transcript", "")
    
    log.info(f"Retell callback: {call_id}, type: {call_type}")
    
    # Check if agent wants to transfer
    if call_type == "agent_decided_to_transfer" or "transfer" in transcript.lower():
        # Get the original call info
        retell_phone = data.get("to_number")  # BadBot number
        
        # Look up client config
        phone = db.query(PhoneNumber).filter(
            PhoneNumber.phone_number == retell_phone
        ).first()
        
        if not phone:
            log.error(f"No phone config for {retell_phone}")
            return {"status": "error", "message": "Config not found"}
        
        config = db.query(BadBotConfig).filter(
            BadBotConfig.phone_number_id == phone.id
        ).first()
        
        if not config:
            log.error(f"No BadBot config for phone {phone.id}")
            return {"status": "error", "message": "BadBot not configured"}
        
        # Transfer to client cell
        client_cell = config.client_cell
        log.info(f"Transferring {call_id} to {client_cell}")
        
        # Get Telnyx call control ID from your database or mapping
        # You may need to store this when the call first arrives
        
        # For now, we'll use the call_id (you may need to map this)
        await telnyx_transfer(call_id, client_cell)
        
        return {
            "status": "transferred",
            "to": client_cell,
            "client": config.client_name
        }
    
    return {"status": "no_action"}
'''

print("="*60)
print("RETELL TRANSFER WEBHOOK CODE")
print("="*60)
print("\nAdd this to app/routers/badbot_screen.py:")
print(webhook_code)
print("\n" + "="*60)
print("\nThen configure Retell agent to call this webhook:")
print("https://your-domain.com/api/v1/badbot/retell/call-analyzed")
print("="*60)
