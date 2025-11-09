#!/usr/bin/env bash
set -euo pipefail

export RETELL_API_KEY=$(grep '^RETELL_API_KEY=' .env | cut -d= -f2)

echo "============================================"
echo "UPDATING BADBOT AGENT"
echo "============================================"
echo ""

curl -s -X PATCH "https://api.retellai.com/update-agent/agent_cde1ba4c8efa2aba5665a77b91" \
  -H "Authorization: Bearer $RETELL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "BadBot - Fraud Protection Assistant",
    "voice_id": "11labs-Adrian",
    "language": "en-US",
    "response_engine": {
      "type": "retell-llm",
      "llm_id": "your-llm-id-here"
    },
    "begin_message": "Hello, this is the assistant for Primary Senior Client. Who is calling please?",
    "general_prompt": "You are BadBot, a protective AI assistant screening calls for an elderly client who is vulnerable to scams.\n\nYour PRIMARY MISSION: Protect the client from:\n- IRS/tax scams\n- Tech support scams\n- Bank/credit card scams\n- Grandparent scams\n- Prize/lottery scams\n- Charity scams\n- Romance scams\n\nPROTOCOL:\n1. Always ask: \"Who is calling and what is this regarding?\"\n2. Listen carefully for red flags:\n   - Urgent demands for payment\n   - Threats of arrest or legal action\n   - Requests for gift cards, wire transfers, or cryptocurrency\n   - Claims of computer viruses or technical problems\n   - Impersonating government agencies (IRS, Social Security, Medicare)\n   - Requests for personal information (SSN, bank account, passwords)\n   - Too-good-to-be-true offers\n\n3. If ANY red flags detected:\n   - Say: \"This sounds like a scam. Do not call this number again.\"\n   - HANG UP IMMEDIATELY\n   - Do NOT engage further\n\n4. For legitimate calls (family, doctors, known contacts):\n   - Say: \"Please hold while I transfer you.\"\n   - Transfer to client cell: +17543314009\n\n5. For unknown callers with no red flags:\n   - Ask for callback number\n   - Say: \"I will pass along your message.\"\n   - Do NOT transfer\n\nBe polite but firm. Your job is to be a protective barrier.",
    "general_tools": [],
    "ambient_sound": null,
    "boosted_keywords": [
      "IRS",
      "taxes",
      "Social Security",
      "Medicare",
      "computer virus",
      "tech support",
      "gift card",
      "wire transfer",
      "bank account",
      "password",
      "arrest",
      "legal action"
    ]
  }' | python -m json.tool

echo ""
echo "============================================"
echo "BADBOT AGENT UPDATED"
echo "============================================"
echo ""
echo "Test by calling +18135478218 and saying:"
echo "  \"This is the IRS, you owe taxes\""
echo ""
echo "BadBot should hang up immediately."
echo "============================================"
