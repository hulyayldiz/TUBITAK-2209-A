FROM python:3.10-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Gerekli kütüphaneleri yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tüm proje dosyalarını kopyala
COPY . .

# Streamlit portunu dışa aç
EXPOSE 8501

# Uygulamayı başlat
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
