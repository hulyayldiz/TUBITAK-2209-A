FROM python:3.11-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Gerekli kütüphaneleri yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tüm proje dosyalarını kopyala
COPY . .

# Streamlit portunu dışa aç
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)" || exit 1

# Uygulamayı başlat
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
