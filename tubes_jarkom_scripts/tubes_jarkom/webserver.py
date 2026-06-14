import socket
import threading
import os
import mimetypes
from datetime import datetime

# HTTP_HOST dan UDP_HOST adalah IP interface webserver mendengarkan.
# "0.0.0.0" berarti mendengarkan di semua IP (termasuk IP LAN Teman 2).
HTTP_HOST = "192.168.0.102"
HTTP_PORT = 8000
UDP_HOST = "192.168.0.102"
UDP_PORT = 9000
WEB_ROOT = "HTML"
BUFFER_SIZE = 4096


def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def build_response(status, body, content_type="text/html; charset=utf-8"):
    header = (
        f"HTTP/1.1 {status}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n\r\n"
    )
    return header.encode("utf-8") + body


def get_error_page(status_code, reason):
    path = os.path.join(WEB_ROOT, "status", f"{status_code}.html")
    if os.path.isfile(path):
        with open(path, "rb") as f:
            return f.read()
    return f"<html><body><h1>{status_code} {reason}</h1></body></html>".encode("utf-8")


def handle_http_client(client_socket, client_addr):
    try:
        request_data = client_socket.recv(BUFFER_SIZE)
        if not request_data:
            return

        request_text = request_data.decode("iso-8859-1", errors="ignore")
        parts = request_text.split("\r\n")[0].split()

        if len(parts) < 3 or parts[0] != "GET":
            body = b"<html><body><h1>400 Bad Request</h1><p>Only GET is supported.</p></body></html>"
            client_socket.sendall(build_response("400 Bad Request", body))
            log(f"HTTP {client_addr[0]} malformed_request 400")
            return

        path = parts[1].split("?", 1)[0].lstrip("/")
        file_path = os.path.join(WEB_ROOT, path or "index.html")

        if ".." in path or not os.path.isfile(file_path):
            body = get_error_page(404, "Not Found")
            client_socket.sendall(build_response("404 Not Found", body))
            log(f"HTTP {client_addr[0]} /{path} 404")
            return

        with open(file_path, "rb") as f:
            body = f.read()

        content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        client_socket.sendall(build_response("200 OK", body, content_type))
        log(f"HTTP {client_addr[0]} /{path} 200 thread={threading.current_thread().name}")

    except Exception as e:
        body = get_error_page(500, "Internal Server Error")
        client_socket.sendall(build_response("500 Internal Server Error", body))
        log(f"HTTP {client_addr[0]} error={e}")
    finally:
        client_socket.close()


def start_http_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HTTP_HOST, HTTP_PORT))
    server_socket.listen(50)
    log(f"HTTP web server running on {HTTP_HOST}:{HTTP_PORT}")

    while True:
        client_socket, client_addr = server_socket.accept()
        threading.Thread(target=handle_http_client, args=(client_socket, client_addr), daemon=True).start()


def start_udp_echo_server():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind((UDP_HOST, UDP_PORT))
    log(f"UDP echo server running on {UDP_HOST}:{UDP_PORT}")

    while True:
        data, addr = udp_socket.recvfrom(BUFFER_SIZE)
        udp_socket.sendto(data, addr)
        log(f"UDP echo {addr[0]}:{addr[1]} size={len(data)}")


def main():
    if not os.path.isdir(WEB_ROOT):
        log(f"WARNING: folder '{WEB_ROOT}' tidak ditemukan. Letakkan folder HTML sejajar dengan webserver.py")

    threading.Thread(target=start_udp_echo_server, daemon=True).start()
    start_http_server()


if __name__ == "__main__":
    main()
