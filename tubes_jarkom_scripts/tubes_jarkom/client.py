import socket
import argparse
import time
import statistics
import threading

# Skema Tugas:
# - Kamu (Client) menjalankan: client.py
# - Teman 1 (Proxy) menjalankan: proxy.py
# - Teman 2 (Webserver) menjalankan: webserver.py
DEFAULT_PROXY_HOST = "192.168.0.102" # IP laptop Teman 1 (Proxy)
DEFAULT_PROXY_PORT = 8080
DEFAULT_UDP_HOST = "192.168.0.102" # IP laptop Teman 2 (Webserver & UDP Server)
DEFAULT_UDP_PORT = 9000
BUFFER_SIZE = 8192


def http_get(proxy_host, proxy_port, path):
    if not path.startswith("/"):
        path = "/" + path

    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {proxy_host}:{proxy_port}\r\n"
        f"User-Agent: TubesJarkomClient/1.0\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("utf-8")

    start = time.time()
    try:
        with socket.create_connection((proxy_host, proxy_port), timeout=10) as s:
            s.sendall(request)
            chunks = []
            while (chunk := s.recv(BUFFER_SIZE)):
                chunks.append(chunk)
            response = b"".join(chunks)
    except Exception as e:
        print(f"HTTP GET Error: {e}")
        return 0.0, b""

    elapsed_ms = (time.time() - start) * 1000
    print("=" * 70)
    print(f"HTTP GET {path} via proxy {proxy_host}:{proxy_port} ({elapsed_ms:.2f} ms)")
    print("=" * 70)
    try:
        print(response.decode("utf-8", errors="replace"))
    except Exception:
        print(response)

    return elapsed_ms, response


def udp_ping(udp_host, udp_port, count=10, timeout=1.0, interval=0.5):
    rtts = []
    total_payload_bytes = 0
    test_start = time.time()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        udp_socket.settimeout(timeout)

        for seq in range(1, count + 1):
            send_time = time.time()
            payload = f"Ping {seq} {send_time}".encode("utf-8")
            total_payload_bytes += len(payload)

            try:
                udp_socket.sendto(payload, (udp_host, udp_port))
                data, addr = udp_socket.recvfrom(BUFFER_SIZE)
                rtt_ms = (time.time() - send_time) * 1000
                rtts.append(rtt_ms)
                print(f"Reply from {addr[0]}:{addr[1]} seq={seq} bytes={len(data)} RTT={rtt_ms:.2f} ms")
            except socket.timeout:
                print(f"Request timed out seq={seq}")

            time.sleep(interval)

    test_duration = time.time() - test_start
    received = len(rtts)
    packet_loss = ((count - received) / count) * 100 if count else 0

    print("\n" + "=" * 70)
    print("UDP QoS Statistics")
    print("=" * 70)
    print(f"Target          : {udp_host}:{udp_port}")
    print(f"Packets sent    : {count}")
    print(f"Packets received: {received}")
    print(f"Packet loss     : {packet_loss:.2f}%")

    if rtts:
        diffs = [abs(rtts[i] - rtts[i - 1]) for i in range(1, len(rtts))]
        jitter = statistics.stdev(diffs) if len(diffs) >= 2 else (diffs[0] if diffs else 0.0)
        throughput = ((total_payload_bytes * 8) / test_duration) / 1000 if test_duration > 0 else 0

        print(f"Min RTT         : {min(rtts):.2f} ms")
        print(f"Avg RTT         : {sum(rtts) / received:.2f} ms")
        print(f"Max RTT         : {max(rtts):.2f} ms")
        print(f"Jitter          : {jitter:.2f} ms")
        print(f"Throughput      : {throughput:.2f} kbps")
    else:
        print("No packets received, RTT/jitter/throughput tidak dapat dihitung.")


def run_multiclient(proxy_host, proxy_port, path, clients):
    results = []
    threads = []

    def worker(client_id):
        try:
            elapsed, _ = http_get(proxy_host, proxy_port, path)
            if elapsed > 0:
                results.append(elapsed)
                print(f"[Client-{client_id}] selesai dalam {elapsed:.2f} ms")
        except Exception as e:
            print(f"[Client-{client_id}] error: {e}")

    for i in range(1, clients + 1):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    if results:
        print("\nMulti-client summary")
        print(f"Jumlah client berhasil: {len(results)}/{clients}")
        print(f"Min/Avg/Max response: {min(results):.2f} / {sum(results)/len(results):.2f} / {max(results):.2f} ms")


def main():
    parser = argparse.ArgumentParser(description="Client TCP/UDP untuk Tubes Jarkom")
    parser.add_argument("--mode", choices=["tcp", "udp", "multi"], required=True)
    parser.add_argument("--path", default="/index.html")
    parser.add_argument("--proxy-host", default=DEFAULT_PROXY_HOST)
    parser.add_argument("--proxy-port", type=int, default=DEFAULT_PROXY_PORT)
    parser.add_argument("--udp-host", default=DEFAULT_UDP_HOST)
    parser.add_argument("--udp-port", type=int, default=DEFAULT_UDP_PORT)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--clients", type=int, default=5)
    args = parser.parse_args()

    if args.mode == "tcp":
        http_get(args.proxy_host, args.proxy_port, args.path)
    elif args.mode == "udp":
        udp_ping(args.udp_host, args.udp_port, args.count)
    elif args.mode == "multi":
        run_multiclient(args.proxy_host, args.proxy_port, args.path, args.clients)


if __name__ == "__main__":
    main()
