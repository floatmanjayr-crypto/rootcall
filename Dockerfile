FROM python:3.11-slim

WORKDIR /app

# Copy only backend (your actual code)
COPY backend ./backend
COPY apprunner.yaml ./   # optional, not needed anymore

WORKDIR /app/backend

RUN pip install --no-cache-dir uvicorn[standard] fastapi python-multipart
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
