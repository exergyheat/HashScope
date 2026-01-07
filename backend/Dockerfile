FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY hashscope/ ./hashscope/

# Expose ports
EXPOSE 3333 8000

# Run the API server (which starts the proxy)
CMD ["uvicorn", "hashscope.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

