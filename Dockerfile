FROM python:3.11-slim

WORKDIR /app

# Зависимости для Pillow и ReportLab + утилиты
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    fonts-dejavu-core \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Скачиваем шрифт Montserrat (Google Fonts)
RUN mkdir -p /app/assets/fonts && \
    wget -q "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Regular.ttf" -O /app/assets/fonts/Montserrat-Regular.ttf && \
    wget -q "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Medium.ttf" -O /app/assets/fonts/Montserrat-Medium.ttf && \
    wget -q "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-SemiBold.ttf" -O /app/assets/fonts/Montserrat-SemiBold.ttf && \
    wget -q "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf" -O /app/assets/fonts/Montserrat-Bold.ttf

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Запуск
CMD ["python", "-m", "src.bot.main"]

