import socket
import threading
import os
import hashlib
import time
from datetime import datetime

# PROXY_HOST adalah IP interface proxy mendengarkan.
# "0.0.0.0" berarti mendengarkan di semua IP (termasuk IP LAN Teman 1).
PROXY_HOST = "0.0.0.0"
PROXY_PORT = 8080

# SERVER_HOST adalah IP tujuan webserver (Teman 2)
SERVER_HOST = "192.168.0.102" # IP laptop Teman 2
SERVER_PORT = 8000

BUFFER_SIZE = 4096
CACHE_DIR = "cache"
CACHE_LOCK = threading.Lock()
SERVER_TIMEOUT = 5


def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def cache_filename(path):
    key = hashlib.sha256(path.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, key + ".cache")


def build_error_response(status, message):
    body = f"<html><body><h1>{status}</h1><p>{message}</p></body></html>".encode("utf-8")
    header = (
        f"HTTP/1.1 {status}\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("utf-8")
    return header + body


def forward_to_server(request_bytes):
    with socket.create_connection((SERVER_HOST, SERVER_PORT), timeout=SERVER_TIMEOUT) as server_socket:
        server_socket.sendall(request_bytes)
        response_chunks = []
        while (chunk := server_socket.recv(BUFFER_SIZE)):
            response_chunks.append(chunk)
        return b"".join(response_chunks)


def handle_client(client_socket, client_addr):
    start_time = time.time()
    cache_status, path = "-", "-"

    try:
        request_bytes = client_socket.recv(BUFFER_SIZE)
        if not request_bytes:
            return

        request_text = request_bytes.decode("iso-8859-1", errors="ignore")
        parts = request_text.split("\r\n")[0].split()
        if len(parts) < 2:
            client_socket.sendall(build_error_response("400 Bad Request", "Malformed HTTP request"))
            return

        path = parts[1]
        cache_path = cache_filename(path)

        with CACHE_LOCK:
            has_cache = os.path.isfile(cache_path)

        if has_cache:
            cache_status = "HIT"
            with CACHE_LOCK:
                with open(cache_path, "rb") as f:
                    response = f.read()
            client_socket.sendall(response)
        else:
            cache_status = "MISS"
            try:
                response = forward_to_server(request_bytes)
                if not response:
                    response = build_error_response("502 Bad Gateway", "Empty response from web server")
                elif b"200 OK" in response.split(b"\r\n", 1)[0]:
                    with CACHE_LOCK:
                        with open(cache_path, "wb") as f:
                            f.write(response)
                client_socket.sendall(response)
            except socket.timeout:
                client_socket.sendall(build_error_response("504 Gateway Timeout", "Web server timeout"))
            except Exception as e:
                client_socket.sendall(build_error_response("502 Bad Gateway", f"Proxy error: {e}"))
    finally:
        elapsed = (time.time() - start_time) * 1000
        log(f"CLIENT {client_addr[0]} URL={path} CACHE={cache_status} TIME={elapsed:.2f}ms THREAD={threading.current_thread().name}")
        client_socket.close()


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)
    proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    proxy_socket.bind((PROXY_HOST, PROXY_PORT))
    proxy_socket.listen(50)

    log(f"Proxy listening on {PROXY_HOST}:{PROXY_PORT}")
    log(f"Forward target webserver: {SERVER_HOST}:{SERVER_PORT}")

    while True:
        client_socket, client_addr = proxy_socket.accept()
        threading.Thread(target=handle_client, args=(client_socket, client_addr), daemon=True).start()


if __name__ == "__main__":
    main()
