FROM python:alpine

# Set the stage
LABEL maintainer="curfew-marathon"
LABEL version="0.1.0"
LABEL description="Docker Image for importrr"

# Install exiftool
RUN apk add exiftool ffmpeg

# Copy the Python app and install requirements
COPY src /app
COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir --root-user-action=ignore -r requirements.txt

# Set working directory
WORKDIR /app

# Prometheus metrics endpoint (see METRICS_PORT, default 9130)
EXPOSE 9130

# Go for launch with the scheduler!
CMD ["python3", "launch.py"]
