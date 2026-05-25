/**
 * Websync channel — synchronous HTTP front door for NanoClaw.
 *
 * Built for the Hafnarvaktin iOS chat. A POST request with the user's text
 * is routed through NanoClaw's normal session pipeline (the same one
 * Telegram uses) and the HTTP response holds open until the agent replies.
 * This is what gives the React Native app *the same agent* — same
 * containers, same MCP tools, same memory — as the Telegram bot.
 *
 * Wire format:
 *   POST /chat
 *   { "text": "what boats are in port?", "user": "rn-app" }
 *
 *   200 { "text": "Right now BÁRA, HALLA, ... are in port." }
 *   400 { "error": "missing text" }
 *   504 { "error": "timeout waiting for agent reply" }
 *
 * Concurrency: requests are serialised. A second POST waits in a small
 * in-process queue for the first to finish before being injected into
 * NanoClaw's router. This keeps the simple one-pending-reply model and
 * matches typical interactive chat where the user types, waits, types
 * again. The queue depth is capped — a 9th request returns 503.
 *
 * Platform identity: all websync messages share PLATFORM_ID = 'rn-app'
 * (configurable via WEBSYNC_PLATFORM_ID) so they land in a single
 * messaging group wired once to the desired agent group, mirroring how
 * the CLI channel uses a single `local` platform id.
 */
import http from 'http';

import { log } from '../log.js';
import type { ChannelAdapter, ChannelSetup, OutboundMessage } from './adapter.js';
import { registerChannelAdapter } from './channel-registry.js';
import { stripTelegramFormatting } from './telegram-strip-formatting.js';

// Strip Markdown bold/italic markers — RN's <Text> doesn't parse them, so
// `**bold**` would otherwise render as literal asterisks. Removes the
// markers but keeps the inner text. Combined with stripTelegramFormatting
// (which kills code fences and pipe tables) this gives the iOS app the
// same plain-with-emoji look the Telegram bot has.
function stripMarkdownEmphasis(input: string): string {
  return input
    .replace(/\*\*(.+?)\*\*/gs, '$1')
    .replace(/__(.+?)__/g, '$1')
    .replace(/(^|[\s(])\*([^\s*][^*]*?)\*(?=[\s).,;!?]|$)/g, '$1$2')
    .replace(/(^|[\s(])_([^\s_][^_]*?)_(?=[\s).,;!?]|$)/g, '$1$2');
}

function sanitizeForPhone(input: string): string {
  return stripMarkdownEmphasis(stripTelegramFormatting(input));
}

const DEFAULT_PORT = 3010;
const DEFAULT_PLATFORM_ID = 'rn-app';
const REPLY_TIMEOUT_MS = 90_000;
const MAX_QUEUE_DEPTH = 8;

interface PendingReply {
  resolve: (text: string) => void;
  reject: (err: Error) => void;
  timer: NodeJS.Timeout;
}

function createAdapter(): ChannelAdapter {
  let server: http.Server | null = null;

  const platformId = process.env.WEBSYNC_PLATFORM_ID || DEFAULT_PLATFORM_ID;

  // Only one in-flight pending HTTP reply at a time. NanoClaw's outbound
  // delivery for this platformId resolves it.
  let pending: PendingReply | null = null;

  // Queue of waiters parked while another request is in flight.
  const queue: Array<() => void> = [];

  function settleAndDrain(): void {
    pending = null;
    const next = queue.shift();
    if (next) next();
  }

  const adapter: ChannelAdapter = {
    name: 'websync',
    channelType: 'websync',
    supportsThreads: false,

    async setup(config: ChannelSetup): Promise<void> {
      const port = parseInt(process.env.WEBSYNC_PORT || String(DEFAULT_PORT), 10);

      server = http.createServer(async (req, res) => {
        if (req.method === 'GET' && (req.url === '/' || req.url === '/health')) {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: true, platformId, queueDepth: queue.length, inFlight: pending !== null }));
          return;
        }

        if (req.method !== 'POST' || (req.url !== '/chat' && req.url !== '/webhook/chat')) {
          res.writeHead(404, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'not found' }));
          return;
        }

        const chunks: Buffer[] = [];
        for await (const chunk of req) chunks.push(chunk as Buffer);
        const raw = Buffer.concat(chunks).toString('utf8');

        let body: { text?: unknown; user?: unknown };
        try {
          body = raw ? JSON.parse(raw) : {};
        } catch {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'invalid json' }));
          return;
        }

        if (typeof body.text !== 'string' || body.text.length === 0) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'missing text' }));
          return;
        }
        const text = body.text;
        const userLabel = typeof body.user === 'string' && body.user.length > 0 ? body.user : 'web';

        if (queue.length >= MAX_QUEUE_DEPTH) {
          res.writeHead(503, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'busy' }));
          return;
        }

        // Wait our turn if another request is in flight.
        if (pending !== null) {
          await new Promise<void>((resolve) => queue.push(resolve));
        }

        // Set up the reply promise BEFORE injecting, so deliver() never
        // races us.
        const replyPromise = new Promise<string>((resolve, reject) => {
          const timer = setTimeout(() => {
            if (pending && pending.reject === reject) {
              settleAndDrain();
              reject(new Error('timeout waiting for agent reply'));
            }
          }, REPLY_TIMEOUT_MS);
          pending = { resolve, reject, timer };
        });

        try {
          await config.onInbound(platformId, null, {
            id: `websync-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            kind: 'chat',
            timestamp: new Date().toISOString(),
            content: {
              text,
              sender: userLabel,
              senderId: `websync:${userLabel}`,
            },
          });
        } catch (err) {
          if (pending) clearTimeout(pending.timer);
          settleAndDrain();
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: (err as Error).message }));
          return;
        }

        try {
          const reply = await replyPromise;
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ text: reply }));
        } catch (err) {
          res.writeHead(504, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: (err as Error).message }));
        }
      });

      await new Promise<void>((resolve, reject) => {
        server!.once('error', reject);
        server!.listen(port, '0.0.0.0', () => {
          log.info('Websync channel listening', { port, platformId });
          resolve();
        });
      });
    },

    async teardown(): Promise<void> {
      if (pending) {
        clearTimeout(pending.timer);
        try {
          pending.reject(new Error('adapter teardown'));
        } catch {
          // swallow
        }
        pending = null;
      }
      queue.splice(0).forEach((r) => r());

      if (server) {
        await new Promise<void>((resolve) => server!.close(() => resolve()));
        server = null;
      }
    },

    isConnected(): boolean {
      return server !== null;
    },

    async deliver(deliveryPlatformId, _threadId, message: OutboundMessage): Promise<string | undefined> {
      if (deliveryPlatformId !== platformId) return undefined;
      if (!pending) {
        // No HTTP waiter — outbound row is already persisted on the host side,
        // so the message isn't lost; it just won't make it back to this
        // request. Matches the cli.ts no-op-when-no-client convention.
        return undefined;
      }
      const text = extractText(message);
      if (text === null) return undefined;

      clearTimeout(pending.timer);
      const p = pending;
      settleAndDrain();
      p.resolve(sanitizeForPhone(text));
      return undefined;
    },
  };

  return adapter;
}

function extractText(message: OutboundMessage): string | null {
  const content = message.content as Record<string, unknown> | string | undefined;
  if (typeof content === 'string') return content;
  if (content && typeof content === 'object' && typeof content.text === 'string') {
    return content.text;
  }
  return null;
}

registerChannelAdapter('websync', { factory: createAdapter });
