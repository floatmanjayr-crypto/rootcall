# -*- coding: utf-8 -*-
"""
Add debug logging to trace SMS alerts
"""

with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# Add logging before SMS alert calls
old1 = '''        # Alert client screening is happening
        if cfg.get("sms_alerts_enabled") and cfg.get("alert_on_unknown"):
            await send_sms_alert(client_cell, f"[BadBot] Unknown caller {cnam or from_num} being screened", to_num)'''

new1 = '''        # Alert client screening is happening
        log.info("[SMS CHECK] sms_alerts_enabled=%s, alert_on_unknown=%s, client_cell=%s", 
                 cfg.get("sms_alerts_enabled"), cfg.get("alert_on_unknown"), client_cell)
        if cfg.get("sms_alerts_enabled") and cfg.get("alert_on_unknown"):
            log.info("[SMS] Sending unknown caller alert to %s", client_cell)
            await send_sms_alert(client_cell, f"[BadBot] Unknown caller {cnam or from_num} being screened", to_num)
        else:
            log.warning("[SMS] Alert skipped - alerts not enabled or no client_cell")'''

if old1 in content:
    content = content.replace(old1, new1)
    print("Added SMS debug logging")

with open('app/routers/badbot_screen.py', 'w') as f:
    f.write(content)

print("Debug logging added!")
print("Server will reload.")
print("\nCall +18135478530 again and check logs for [SMS CHECK] messages")

