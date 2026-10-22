import type { SocketFactory, WebSocketLike } from '../realtime/protocol';

/** In-memory WebSocket driven by the test (the "server" side). */
export class FakeSocket implements WebSocketLike {
  readyState = 0;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  readonly sent: string[] = [];
  closedWith: { code?: number | undefined; reason?: string | undefined } | null = null;

  constructor(
    readonly url: string,
    readonly protocols: string[] | undefined,
  ) {}

  send(data: string): void {
    if (this.readyState !== 1) throw new Error('socket not open');
    this.sent.push(data);
  }

  close(code?: number, reason?: string): void {
    this.closedWith = { code, reason };
    this.readyState = 3;
  }

  /** Parsed messages the client sent. */
  sentMessages(): ({ type: string } & Record<string, unknown>)[] {
    return this.sent.map((s) => JSON.parse(s) as { type: string } & Record<string, unknown>);
  }

  sentTypes(): string[] {
    return this.sentMessages().map((m) => m.type);
  }

  // ---- server side ----
  open(): void {
    this.readyState = 1;
    this.onopen?.(new Event('open'));
  }

  receive(message: unknown): void {
    const data = typeof message === 'string' ? message : JSON.stringify(message);
    this.onmessage?.(new MessageEvent('message', { data }));
  }

  /** Open and acknowledge authentication (`auth_ok`, with the unread count when given). */
  accept(unreadCount?: number): void {
    this.open();
    this.receive({
      type: 'auth_ok',
      payload: {
        heartbeat_seconds: 25,
        expires_at: 0,
        ...(unreadCount !== undefined ? { unread_count: unreadCount } : {}),
      },
    });
  }

  serverClose(code = 1006, reason = ''): void {
    this.readyState = 3;
    this.onclose?.(new CloseEvent('close', { code, reason }));
  }
}

export interface FakeSocketServer {
  factory: SocketFactory;
  sockets: FakeSocket[];
  /** The most recently created socket. */
  last: () => FakeSocket;
}

export function fakeSocketServer(): FakeSocketServer {
  const sockets: FakeSocket[] = [];
  return {
    sockets,
    factory: (url, protocols) => {
      const s = new FakeSocket(url, protocols);
      sockets.push(s);
      return s;
    },
    last: () => {
      const s = sockets[sockets.length - 1];
      if (s === undefined) throw new Error('no socket created yet');
      return s;
    },
  };
}
