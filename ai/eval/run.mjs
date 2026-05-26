#!/usr/bin/env node
import net from 'node:net';
import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const NANOCLAW_DATA = process.env.NANOCLAW_DATA ?? '/home/prompter/projects/hafnarvaktin/ai/nanoclaw/data';
const AGENT_GROUP_ID = process.env.HAFNAR_AGENT_GROUP ?? 'ag-1777921519963-8l0zcs';
const TELEGRAM_PLATFORM_ID = process.env.HAFNAR_TELEGRAM_PID ?? 'telegram:6794963036';

const SOCK = path.join(NANOCLAW_DATA, 'cli.sock');
const TRANSCRIPT_DIR = path.join(NANOCLAW_DATA, `v2-sessions/${AGENT_GROUP_ID}/.claude-shared/projects/-workspace-agent`);
const QUESTIONS_FILE = path.join(HERE, 'questions.json');
const RESULTS_FILE = path.join(HERE, 'results.csv');
const RAW_FILE = path.join(HERE, 'raw-replies.jsonl');
const TOOL_PREFIX = 'mcp__hafnarvaktin__';

const TARGET = { channelType: 'telegram', platformId: TELEGRAM_PLATFORM_ID, threadId: null };
const REPLY_TO = { channelType: 'cli', platformId: 'local', threadId: null };

const SIZE_POLL_MS = 1000;
const STABLE_MS = 10_000;
const HARD_TIMEOUT_MS = 180_000;
const CLEAR_SETTLE_MS = 6000;
const INTER_QUESTION_DELAY_MS = 13000;

function csvEscape(s) {
  if (s == null) return '';
  const t = String(s);
  if (t.includes('"') || t.includes(',') || t.includes('\n')) return '"' + t.replace(/"/g, '""') + '"';
  return t;
}

function sendOneShot(payload) {
  return new Promise((resolve, reject) => {
    const sock = net.connect(SOCK);
    sock.on('error', reject);
    sock.on('connect', () => {
      sock.write(JSON.stringify(payload) + '\n', () => {
        setTimeout(() => { try { sock.end(); } catch {} resolve(); }, 200);
      });
    });
  });
}

function listTranscripts() {
  const out = execSync(`sudo ls -t "${TRANSCRIPT_DIR}"/*.jsonl 2>/dev/null`, { encoding: 'utf8' }).trim();
  return out ? out.split('\n').filter(s => s.endsWith('.jsonl')) : [];
}

function transcriptSize(p) {
  return parseInt(execSync(`sudo stat -c %s "${p}"`, { encoding: 'utf8' }).trim(), 10);
}

function readTranscript(p) {
  return execSync(`sudo cat "${p}"`, { encoding: 'utf8', maxBuffer: 200 * 1024 * 1024 });
}

function aggregateSize() {
  let total = 0;
  for (const p of listTranscripts()) {
    try { total += transcriptSize(p); } catch {}
  }
  return total;
}

function scanTranscriptsSince(cutISO) {
  const tools = [];
  const texts = [];
  const cutTs = Date.parse(cutISO);
  for (const p of listTranscripts()) {
    let content;
    try { content = readTranscript(p); } catch { continue; }
    for (const ln of content.split('\n')) {
      if (!ln.trim()) continue;
      let obj;
      try { obj = JSON.parse(ln); } catch { continue; }
      const ts = Date.parse(obj.timestamp || '');
      if (!Number.isFinite(ts) || ts <= cutTs) continue;
      const msg = obj.message;
      if (!msg || !Array.isArray(msg.content)) continue;
      for (const c of msg.content) {
        if (c.type === 'tool_use') {
          const name = String(c.name || '');
          const friendly = name.startsWith(TOOL_PREFIX) ? name.slice(TOOL_PREFIX.length) : name;
          tools.push({ name: friendly, raw: name, ts: obj.timestamp, input: c.input });
        } else if (c.type === 'text' && typeof c.text === 'string' && c.text.trim()) {
          if (obj.type === 'assistant' || msg.role === 'assistant') {
            texts.push({ text: c.text, ts: obj.timestamp });
          }
        }
      }
    }
  }
  tools.sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts));
  texts.sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts));
  return { tools, texts, firstAssistantTextTs: texts[0]?.ts ?? null };
}

async function waitForStableAggregateSize(startSize, startedAt) {
  let lastSize = startSize;
  let lastChangeAt = Date.now();
  while (true) {
    const now = Date.now();
    if (now - startedAt > HARD_TIMEOUT_MS) return { reason: 'hard_timeout' };
    let cur;
    try { cur = aggregateSize(); } catch { cur = lastSize; }
    if (cur !== lastSize) {
      lastSize = cur;
      lastChangeAt = now;
    } else if (cur > startSize && now - lastChangeAt > STABLE_MS) {
      return { reason: 'stable' };
    } else if (cur === startSize && now - startedAt > 60_000) {
      return { reason: 'no_growth' };
    }
    await new Promise(r => setTimeout(r, SIZE_POLL_MS));
  }
}

async function main() {
  if (!fs.existsSync(SOCK)) { console.error(`cli.sock not found at ${SOCK}`); process.exit(2); }
  const transcripts = listTranscripts();
  console.log(`Tracking ${transcripts.length} transcript file(s).`);
  console.log(`Initial aggregate size: ${aggregateSize()} bytes\n`);

  const spec = JSON.parse(fs.readFileSync(QUESTIONS_FILE, 'utf8'));
  fs.writeFileSync(RESULTS_FILE, 'idx,scenario,expected_first_tool,question,first_tool_called,tools_used,tool_count,tool_first_match,answered,from_memory,first_reply_ms,total_ms,reply_chars,reply\n');
  fs.writeFileSync(RAW_FILE, '');

  let totalQ = 0;
  for (const s of spec.scenarios) totalQ += s.questions.length;
  console.log(`Running ${totalQ} questions across ${spec.scenarios.length} scenarios.\n`);

  let idx = 0, toolFirstMatch = 0, answered = 0, fromMemory = 0;
  const startWall = Date.now();

  for (const scenario of spec.scenarios) {
    console.log(`\n=== ${scenario.id} — expected first tool: ${scenario.expected_first_tool} ===`);
    for (const q of scenario.questions) {
      idx++;
      process.stdout.write(`[${idx}/${totalQ}] (${scenario.id}) ${q.slice(0, 72)}${q.length > 72 ? '…' : ''}\n`);

      try { await sendOneShot({ text: '/clear', to: TARGET, reply_to: REPLY_TO }); }
      catch (e) { console.error('  ! clear failed:', e.message); }
      await new Promise(r => setTimeout(r, CLEAR_SETTLE_MS));

      const cutISO = new Date().toISOString();
      const cutAggSize = aggregateSize();
      const startedAt = Date.now();
      try { await sendOneShot({ text: q, to: TARGET, reply_to: REPLY_TO }); }
      catch (e) { console.error('  ! send failed:', e.message); continue; }

      const stable = await waitForStableAggregateSize(cutAggSize, startedAt);
      const totalMs = Date.now() - startedAt;

      let tools = [], texts = [], firstTextTs = null;
      try {
        const parsed = scanTranscriptsSince(cutISO);
        tools = parsed.tools;
        texts = parsed.texts;
        firstTextTs = parsed.firstAssistantTextTs;
      } catch (e) { console.error('  ! transcript scan failed:', e.message); }

      const firstTool = tools[0]?.name ?? null;
      const tool_first_match = firstTool === scenario.expected_first_tool;
      const reply = texts.map(t => t.text).join('\n\n');
      const answeredOk = reply.length > 0;
      const memOnly = tools.length === 0 && answeredOk;
      const firstReplyMs = firstTextTs ? (Date.parse(firstTextTs) - startedAt) : null;

      if (tool_first_match) toolFirstMatch++;
      if (answeredOk) answered++;
      if (memOnly) fromMemory++;

      const row = [
        idx, scenario.id, scenario.expected_first_tool, q,
        firstTool ?? '', tools.map(t => t.name).join('|'), tools.length,
        tool_first_match ? 'Y' : 'N',
        answeredOk ? 'Y' : 'N',
        memOnly ? 'Y' : 'N',
        firstReplyMs ?? '', totalMs, reply.length, reply,
      ].map(csvEscape).join(',') + '\n';
      fs.appendFileSync(RESULTS_FILE, row);
      fs.appendFileSync(RAW_FILE, JSON.stringify({
        idx, scenario: scenario.id, question: q,
        expected_first_tool: scenario.expected_first_tool,
        first_tool_called: firstTool,
        tools_used: tools.map(t => ({ name: t.name, input: t.input, ts: t.ts })),
        text_segments: texts.map(t => ({ ts: t.ts, chars: t.text.length })),
        tool_first_match, answered: answeredOk, from_memory: memOnly,
        replies: texts.map(t => t.text),
        stable_reason: stable.reason,
        first_reply_ms: firstReplyMs, total_ms: totalMs,
      }) + '\n');

      const marker = memOnly ? 'MEM' : (tool_first_match ? 'PASS' : (tools.length ? 'WRONG-TOOL' : 'NO-REPLY'));
      console.log(`  → tools=[${tools.map(t => t.name).join(', ')}] first=${firstTool ?? '∅'} | ${marker} | reply ${reply.length}ch in ${totalMs}ms (${stable.reason})`);
      await new Promise(r => setTimeout(r, INTER_QUESTION_DELAY_MS));
    }
  }

  const elapsedS = Math.round((Date.now() - startWall) / 1000);
  console.log(`\n=== summary ===`);
  console.log(`Total: ${idx}`);
  console.log(`Answered: ${answered}/${idx} (${(100*answered/idx).toFixed(1)}%)`);
  console.log(`First tool matched expected: ${toolFirstMatch}/${idx} (${(100*toolFirstMatch/idx).toFixed(1)}%)`);
  console.log(`Answered from memory (no tool call): ${fromMemory}/${idx} (${(100*fromMemory/idx).toFixed(1)}%)`);
  console.log(`Elapsed: ${elapsedS}s`);
  console.log(`Results: ${RESULTS_FILE}`);
  console.log(`Raw: ${RAW_FILE}`);
}

main().catch(e => { console.error('fatal:', e); process.exit(1); });
