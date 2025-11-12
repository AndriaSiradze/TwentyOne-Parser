FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /usr/src/app/bot

# Базовые утилиты и нужные либы для headless Chrome
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl unzip xdg-utils \
      libasound2 libatk-bridge2.0-0 libgtk-3-0 libnss3 libnspr4 libxss1 libgbm1 \
  && rm -rf /var/lib/apt/lists/*

# Ставим Chrome и Chromedriver из Chrome for Testing (никаких apt-реп)
# Берём последнюю стабильную версию через LATEST_RELEASE
RUN set -eux; \
  VER="$(curl -fsSL https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE)"; \
  curl -fsSL -o /tmp/chrome.zip "https://storage.googleapis.com/chrome-for-testing-public/${VER}/linux64/chrome-linux64.zip"; \
  curl -fsSL -o /tmp/driver.zip "https://storage.googleapis.com/chrome-for-testing-public/${VER}/linux64/chromedriver-linux64.zip"; \
  mkdir -p /opt/chrome /opt/chromedriver; \
  unzip -q /tmp/chrome.zip -d /opt; \
  unzip -q /tmp/driver.zip -d /opt; \
  ln -sf /opt/chrome-linux64/chrome /usr/local/bin/google-chrome; \
  ln -sf /opt/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver; \
  rm -f /tmp/chrome.zip /tmp/driver.zip; \
  google-chrome --version; chromedriver --version

# Python-зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код
COPY . .
