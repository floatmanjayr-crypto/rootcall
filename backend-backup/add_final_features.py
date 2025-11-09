# -*- coding: utf-8 -*-
print("Adding final features...")

# 1. Add CSV export to API
print("\n[1/3] Adding CSV export...")

export_code = '''
@router.get("/api/badbot/export/{client_id}")
async def export_calls(client_id: int, db: Session = Depends(get_db)):
    """Export call logs as CSV"""
    from fastapi.responses import StreamingResponse
    import io
    import csv
    
    phones = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).all()
    phone_ids = [p.id for p in phones]
    
    if not phone_ids:
        raise HTTPException(status_code=404)
    
    logs = db.query(BadBotCallLog).filter(
        BadBotCallLog.phone_number_id.in_(phone_ids)
    ).order_by(BadBotCallLog.timestamp.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Timestamp', 'From', 'Caller Name', 'Action', 'Status'])
    
    for log in logs:
        writer.writerow([
            log.timestamp.isoformat(),
            log.from_number,
            log.caller_name or 'Unknown',
            log.action,
            log.status
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=badbot_calls.csv"}
    )
'''

with open('app/routers/badbot_portal.py', 'r', encoding='utf-8') as f:
    portal = f.read()

if 'export_calls' not in portal:
    portal = portal.rstrip() + '\n\n' + export_code
    with open('app/routers/badbot_portal.py', 'w', encoding='utf-8') as f:
        f.write(portal)
    print("   OK: CSV export added")
else:
    print("   OK: Already exists")

# 2. Create enhanced portal page
print("\n[2/3] Creating enhanced portal...")

enhanced_portal = open('static/james-portal.html', 'r', encoding='utf-8').read()

# Add export button if not exists
if 'Export CSV' not in enhanced_portal:
    enhanced_portal = enhanced_portal.replace(
        '<h2 class="text-2xl font-bold mb-4">Recent Call Activity</h2>',
        '''<div class="flex justify-between items-center mb-4">
            <h2 class="text-2xl font-bold">Recent Call Activity</h2>
            <a href="/api/badbot/export/1" download class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
                Export CSV
            </a>
        </div>'''
    )
    with open('static/james-portal.html', 'w', encoding='utf-8') as f:
        f.write(enhanced_portal)
    print("   OK: Export button added")

# 3. Summary
print("\n[3/3] Creating feature summary...")

summary = '''
BADBOT PORTAL - COMPLETE FEATURES
=====================================

DASHBOARD:
- Real-time spam blocked counter
- Calls screened counter  
- Trusted contacts forwarded counter
- Total calls counter

SETTINGS:
- Toggle SMS alerts on/off
- Alert on spam blocked
- Alert on unknown callers
- Update alert phone number

TRUSTED CONTACTS:
- Add contacts with names
- Remove contacts
- Bypass screening for trusted numbers

CALL HISTORY:
- View recent 20 calls
- Timestamps and caller IDs
- Action taken (spam/screen/forward)
- Status indicators

EXPORT:
- Download all calls as CSV
- Full call history export

AUTO-FEATURES:
- Real-time stats from database
- Auto-refresh every 30 seconds
- SMS alerts on calls
- Call logging to database

PORTALS:
- http://localhost:8000/static/james-portal.html
- http://localhost:8000/static/badbot-portal.html

API ENDPOINTS:
- GET  /api/badbot/stats/{client_id}
- GET  /api/badbot/calls/{client_id}
- GET  /api/badbot/config/{client_id}
- PATCH /api/badbot/config/{client_id}
- POST /api/badbot/trusted-contacts/{client_id}
- DELETE /api/badbot/trusted-contacts/{client_id}/{phone}
- GET  /api/badbot/export/{client_id}

TEST:
1. Call +18135478530
2. Open portal
3. Watch real stats update!
'''

with open('BADBOT_FEATURES.txt', 'w') as f:
    f.write(summary)

print("\n" + "="*60)
print("COMPLETE!")
print("="*60)
print("\nFeatures added:")
print("  - CSV Export")
print("  - Export button in portal")
print("  - Feature documentation")
print("\nOpen portal:")
print("  http://localhost:8000/static/james-portal.html")
print("\nExport calls:")
print("  http://localhost:8000/api/badbot/export/1")
print("\nSee BADBOT_FEATURES.txt for full list!")
print("="*60)

