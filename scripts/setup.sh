#!/bin/bash

echo "��� Setting up VoIP Platform..."

# Check Python (Windows uses 'python' not 'python3')
if command -v python &> /dev/null; then
    PYTHON_CMD=python
elif command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
else
    echo "❌ Python not found"
    exit 1
fi

# Check Node
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed"
    echo "   Download from: https://nodejs.org/"
    exit 1
fi

echo "✅ Python version: $($PYTHON_CMD --version)"
echo "✅ Node version: $(node --version)"
echo ""

# Setup Backend
echo "��� Setting up backend..."
cd backend

echo "Creating Python virtual environment..."
$PYTHON_CMD -m venv venv

echo "Activating virtual environment..."
source venv/Scripts/activate

echo "Upgrading pip..."
python -m pip install --upgrade pip --quiet

echo "Installing Python packages (2-3 minutes)..."
pip install -r requirements.txt --quiet

if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created backend/.env file"
fi

cd ..

# Setup Frontend
echo ""
echo "��� Setting up frontend..."
cd frontend

echo "Installing Node packages (3-5 minutes)..."
npm install --silent

cd ..

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ SETUP COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "��� NEXT STEPS:"
echo ""
echo "1. Get your FREE API keys:"
echo "   → Telnyx: https://portal.telnyx.com (sign up)"
echo "   → OpenAI: https://platform.openai.com/api-keys"
echo ""
echo "2. Add keys to backend/.env:"
echo "   notepad backend/.env"
echo ""
echo "3. I'll guide you through the rest after that!"
echo ""
