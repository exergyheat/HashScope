FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY hashscope_agent/ ./hashscope_agent/

# Run agent
CMD ["python", "-m", "hashscope_agent.main"]

