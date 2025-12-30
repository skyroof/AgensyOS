# Stage 1: Builder
FROM public.ecr.aws/docker/library/python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Download fonts
RUN mkdir -p /app/assets/fonts && \
    wget -q "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Regular.ttf" -O /app/assets/fonts/Montserrat-Regular.ttf && \
    wget -q "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Medium.ttf" -O /app/assets/fonts/Montserrat-Medium.ttf && \
    wget -q "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-SemiBold.ttf" -O /app/assets/fonts/Montserrat-SemiBold.ttf && \
    wget -q "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf" -O /app/assets/fonts/Montserrat-Bold.ttf

# Stage 2: Final
FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    zlib1g \
    libfreetype6 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Copy fonts from builder
COPY --from=builder /app/assets/fonts /app/assets/fonts

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Run application
CMD ["sh", "-c", "alembic upgrade head && python -m src.bot.main"]
