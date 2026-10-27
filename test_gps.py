import socket


def main():
    # UDP Sunucusu (GPSd Forwarder için daha uyumludur)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('0.0.0.0', 5000))

    print("--- UDP TEST BAŞLADI ---")
    print("1. Bilgisayar şu an 5000 portunda UDP paketleri bekliyor.")
    print("2. Telefondaki uygulamadan 'Start'a basın.")
    print("------------------------")

    try:
        while True:
            data, addr = s.recvfrom(4096)
            print(f"🎉 VERİ GELDİ! Kaynak: {addr}")
            print(f"Gelen NMEA: {data.decode(errors='replace').strip()}")
    except Exception as e:
        print(f"Hata: {e}")
    finally:
        s.close()


if __name__ == "__main__":
    main()
