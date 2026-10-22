"""Gate 7 channel doubles: recording push/e-mail clients that can fail the next sends."""

from asseta.core.email import EmailSendError, EmailSendResult, OutboundEmail
from asseta.core.push import PushMessage, PushRouter, PushSendError, PushSendResult


class RecordingPush:
    def __init__(self, name: str) -> None:
        self.name = name
        self.sent: list[tuple[PushMessage, str | None]] = []
        self.failures: list[PushSendError] = []

    def send(self, message: PushMessage, reference: str | None = None) -> PushSendResult:
        if self.failures:
            raise self.failures.pop(0)
        self.sent.append((message, reference))
        return PushSendResult(self.name, f"{self.name}-{len(self.sent)}")


class RecordingEmail:
    def __init__(self) -> None:
        self.sent: list[tuple[OutboundEmail, str | None]] = []
        self.failures: list[EmailSendError] = []

    def send(self, message: OutboundEmail, reference: str | None = None) -> EmailSendResult:
        if self.failures:
            raise self.failures.pop(0)
        self.sent.append((message, reference))
        return EmailSendResult("fake-email", f"<{reference}@test>")


def recording_router() -> tuple[PushRouter, RecordingPush, RecordingPush]:
    android, ios = RecordingPush("fake-fcm"), RecordingPush("fake-apns")
    return PushRouter(android, ios), android, ios
