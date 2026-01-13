# AnkiRAG Local Agent Dockerfile
# PyQt6-based desktop application with GUI support

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for PyQt6 and GUI
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    # Qt6 dependencies
    libgl1-mesa-glx \
    libglib2.0-0 \
    libxcb1 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxkbcommon-x11-0 \
    libxkbcommon0 \
    libdbus-1-3 \
    libegl1 \
    libfontconfig1 \
    libfreetype6 \
    libx11-xcb1 \
    libxi6 \
    libxrender1 \
    x11-utils \
    # Additional utilities
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir -e . || pip install --no-cache-dir PyQt6 httpx aiohttp pydantic pydantic-settings

# Copy application code
COPY . .

# Set environment variables for Qt
ENV QT_QPA_PLATFORM=xcb
ENV DISPLAY=:0

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Entry point
CMD ["python", "-m", "src.main"]
