FROM python:alpine

# Set the stage
LABEL maintainer="curfew-marathon"
LABEL version="0.1.0"
LABEL description="Docker Image for importrr"

# exiftool + ffmpeg for media handling. tzdata lets the TZ env var actually take
# effect in log timestamps and work_dir names; alpine ships without it and would
# otherwise stay on UTC no matter what TZ is set to.
RUN apk add --no-cache exiftool ffmpeg tzdata

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
