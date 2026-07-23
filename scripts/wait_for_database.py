import os
import socket
import time


def main() -> None:
    host = os.getenv("DATABASE_HOST", "localhost")
    port = int(os.getenv("DATABASE_PORT", "5432"))
    timeout_seconds = int(os.getenv("DATABASE_WAIT_TIMEOUT", "60"))
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"database reachable at {host}:{port}")
                return
        except OSError:
            print(f"waiting for database at {host}:{port}")
            time.sleep(2)

    raise TimeoutError(f"database did not become reachable at {host}:{port}")


if __name__ == "__main__":
    main()
