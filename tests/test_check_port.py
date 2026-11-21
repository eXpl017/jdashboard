import socket

from scripts.check_port import main, port_is_free


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_port_is_free_for_an_unused_port() -> None:
    assert port_is_free(_free_port()) is True


def test_port_is_not_free_when_a_socket_holds_it() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]
        assert port_is_free(port) is False


def test_check_port_exits_zero_for_a_free_port(capsys) -> None:
    port = _free_port()

    assert main([str(port)]) == 0
    assert capsys.readouterr().err == ""


def test_check_port_exits_one_and_explains_when_busy(capsys) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]

        assert main([str(port)]) == 1

    err = capsys.readouterr().err
    assert f"Port {port}" in err
    assert "If another local process is using that port" in err
    assert "make run DEV_PORT=" in err
