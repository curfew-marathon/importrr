FROM python:alpine

# Set the stage
LABEL maintainer="curfew-marathon"
LABEL version="0.1.0"
LABEL description="Docker Image for Importrr"

# Install exiftool
RUN apk add exiftool

# Copy the Python app and install requirements
COPY src /app
COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir --root-user-action=ignore -r requirements.txt

# Setup the crontab
RUN echo '*/30  *  *  *  *    python3 /app/launch.py' > /etc/crontabs/root

# Go for launch!
CMD ["/usr/sbin/crond", "-f"]
