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

# Environment variables for scheduling (can be overridden)
ENV SCHEDULE_HOUR="6-22/2"
ENV SCHEDULE_MINUTE="0"
ENV TIMEZONE="UTC"
ENV RUN_ON_STARTUP="false"

# Go for launch with the scheduler!
CMD ["python3", "scheduler.py"]
