# Build stage
FROM python:3.12-slim AS builder
ENV EXIFTOOL_PATH=/usr/bin/exiftool
ENV FFMPEG_PATH=/usr/bin/ffmpeg
# Set TMPDIR to avoid cross-device link errors during pip operations
ENV TMPDIR=/tmp

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    ffmpeg \
    exiftool \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment with proper permissions
RUN python -m venv /opt/venv && \
    chmod -R 755 /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Clear pip cache and upgrade pip
RUN pip cache purge || true
RUN pip install --upgrade pip --no-cache-dir

# Copy requirements and install Python packages with error-resistant flags
COPY requirements.txt .
RUN pip install --no-cache-dir --force-reinstall --no-deps -r requirements.txt || \
    pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.12-slim

# Set TMPDIR to avoid cross-device link errors
ENV TMPDIR=/tmp

# Install FFmpeg and its dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder with proper permissions
COPY --from=builder /opt/venv /opt/venv
RUN chmod -R 755 /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1

# Create workspace directory with proper permissions for Docker Desktop file sharing
RUN mkdir -p /workspace && chmod 755 /workspace
WORKDIR /workspace

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

CMD ["bash"]