import socket
import time

from path_setup import ensure_backend_path

ensure_backend_path()

from flipradar.core.settings import get_settings  # noqa: E402


def main() -> None:
    database = get_settings().database
    host = database.host
    port = database.port
    timeout_seconds = database.wait_timeout_seconds
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
