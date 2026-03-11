FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (Firefox/Camoufox needs GTK, dbus, etc.)
# Mesa/OpenGL packages provide software-rendered WebGL (llvmpipe) inside Docker
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libxt6 \
    libasound2 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxcursor1 \
    libxi6 \
    libpango-1.0-0 \
    libcairo2 \
    libatk1.0-0 \
    libgl1-mesa-dri \
    libgbm1 \
    libegl1 \
    libglx-mesa0 \
    libgl1 \
    xvfb \
    # Fonts — real browsers have 50-200+ fonts, Docker default has ~10
    fonts-liberation2 \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    fonts-noto-core \
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
    fontconfig \
    # PulseAudio — provides mediaDevices (real PCs always have audio devices)
    pulseaudio \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f -v > /dev/null 2>&1

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Remove bezier C extension (.so) — it fails with "cannot enable executable stack"
# in Docker. Removing it forces bezier to use pure Python fallback automatically.
RUN find /usr/local/lib -path "*/bezier/_speedup*" -delete && \
    find /usr/local/lib -name "libbezier*.so*" -delete

# Download Camoufox browser binary
RUN python -m camoufox fetch

COPY . .

# FastAPI start
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
