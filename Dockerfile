# 1. Base image
FROM python:3.13.7-slim

# 2. Working directory
WORKDIR /app

# 3. Copy and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# 4. Copy project files
COPY . .

# 5. Create necessary directories
RUN mkdir -p /app/data /app/docs && \
    chmod -R 755 /app/data /app/docs

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8
ENV PORT=8000

# 6. Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
