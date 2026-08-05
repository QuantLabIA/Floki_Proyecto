import os
import socket

from waitress import serve

from app import app


def local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "IP-DE-TU-PC"
    finally:
        sock.close()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print("\nFloki Manager v2.5 iniciado")
    print(f"En esta computadora: http://127.0.0.1:{port}")
    print(f"Desde un celular en el mismo Wi-Fi: http://{local_ip()}:{port}\n")
    serve(app, host="0.0.0.0", port=port, threads=6)
