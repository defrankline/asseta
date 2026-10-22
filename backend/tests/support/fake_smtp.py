"""A minimal in-process SMTP server on 127.0.0.1 (ephemeral port) for exercising `SmtpEmailClient` with the real
`smtplib` protocol: no external network. Records accepted messages; can refuse recipients or fail DATA."""

import socketserver
import threading
from dataclasses import dataclass, field
from types import TracebackType


@dataclass
class Received:
    mail_from: str
    rcpt_to: list[str]
    data: str


@dataclass
class FakeSmtpState:
    messages: list[Received] = field(default_factory=list)
    reject_rcpt: dict[str, str] = field(default_factory=dict)  # address -> reply line, e.g. "550 5.1.1 no user"
    fail_data: list[str] = field(default_factory=list)  # replies for the next DATA commits, e.g. "451 try later"


class _Handler(socketserver.StreamRequestHandler):
    state: FakeSmtpState

    def _reply(self, line: str) -> None:
        self.wfile.write(f"{line}\r\n".encode())

    def handle(self) -> None:
        state = self.server.state  # type: ignore[attr-defined]
        self._reply("220 fake-smtp ready")
        mail_from, rcpts = "", list[str]()
        while True:
            raw = self.rfile.readline()
            if not raw:
                return
            line = raw.decode().rstrip("\r\n")
            verb = line.split(" ", 1)[0].upper()
            if verb in ("EHLO", "HELO"):
                self._reply("250-fake-smtp\r\n250 8BITMIME")
            elif verb == "MAIL":
                mail_from, rcpts = line.split(":", 1)[1].strip(" <>"), []
                self._reply("250 OK")
            elif verb == "RCPT":
                address = line.split(":", 1)[1].strip(" <>")
                if address in state.reject_rcpt:
                    self._reply(state.reject_rcpt[address])
                else:
                    rcpts.append(address)
                    self._reply("250 OK")
            elif verb == "DATA":
                self._reply("354 end with <CRLF>.<CRLF>")
                lines = []
                while (chunk := self.rfile.readline().decode()) not in (".\r\n", ""):
                    lines.append(chunk)
                if state.fail_data:
                    self._reply(state.fail_data.pop(0))
                else:
                    state.messages.append(Received(mail_from, rcpts, "".join(lines)))
                    self._reply("250 queued")
            elif verb in ("RSET", "NOOP"):
                self._reply("250 OK")
            elif verb == "QUIT":
                self._reply("221 bye")
                return
            else:
                self._reply("502 not implemented")


class FakeSmtpServer:
    def __init__(self) -> None:
        self.state = FakeSmtpState()
        self._server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Handler)
        self._server.daemon_threads = True
        self._server.state = self.state  # type: ignore[attr-defined]
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "FakeSmtpServer":
        self._thread.start()
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self._server.shutdown()
        self._server.server_close()
