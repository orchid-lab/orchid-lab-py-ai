FROM python:3.11-slim-bullseye

# Upgrade system packages and install dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libgl1 \
        libglib2.0-0 \
        ffmpeg && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir --upgrade pip fastapi uvicorn ultralytics pillow python-multipart && \
    rm -rf /root/.cache/pip

#Copy application files
WORKDIR /app
COPY . /app

# Expose the port the app runs on port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]