with open('.env', 'r') as f:
    lines = f.readlines()

new_lines = []
seen_voice_webhook = False

for line in lines:
    if line.startswith('TELNYX_VOICE_WEBHOOK_URL='):
        if not seen_voice_webhook:
            # Keep only the first one and fix it
            new_lines.append('TELNYX_VOICE_WEBHOOK_URL=https://declinatory-gonidioid-elise.ngrok-free.dev/telnyx/badbot/webhook\n')
            seen_voice_webhook = True
            print(f"Fixed: {line.strip()} -> correct webhook")
        else:
            print(f"Removed duplicate: {line.strip()}")
    else:
        new_lines.append(line)

with open('.env', 'w') as f:
    f.writelines(new_lines)

print("\n.env fixed! Restart server.")
