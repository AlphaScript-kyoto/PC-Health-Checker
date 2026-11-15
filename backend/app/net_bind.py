"""待ち受けポートを開けるかどうか。開けないのにスケジューラだけ残さない。"""

from __future__ import annotations

import socket


def port_is_free(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # すぐ閉じるので、検査の直後に uvicorn が同じポートを取れるようにする
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()
