/**
 * Strip markdown formatting that doesn't render well in Telegram's mobile
 * client. Runs BEFORE `sanitizeTelegramLegacyMarkdown` in the outbound
 * pipeline (composed via `transformOutboundText` in `telegram.ts`).
 *
 * Why this exists: agents sometimes wrap responses in ```code fences``` or
 * `|` tables when given list-shaped data. Both render badly in narrow phone
 * bubbles — the fence triggers Telegram's "copy" UI and breaks reading
 * flow; pipe tables wrap unreadably. Prompt-engineering the agent to stop
 * doing this proved fragile under conversation-history drift, so we
 * sanitise deterministically at the send boundary.
 *
 * Content is preserved — only the formatting markers are removed.
 */

// Triple-backtick fence opener. Matches an optional language tag and the
// trailing newline that immediately follows. Single-line inline code
// (`foo`) is NOT touched.
const FENCE_OPEN = /^[ \t]*```[^\n]*\n/gm;

// Triple-backtick fence closer. Matches a backtick run on its own line
// (or at end of input) plus the leading newline that introduces it.
const FENCE_CLOSE = /\n?[ \t]*```[ \t]*(?=\n|$)/gm;

// A line that BEGINS with a pipe (after optional whitespace) — a markdown
// table row. We don't try to detect tables holistically; converting on a
// per-row basis is robust to malformed tables and partial outputs.
const PIPE_ROW = /^\s*\|/;

// Markdown table separator: a row consisting only of `-`, `:`, and pipes
// (e.g. `|---|:---:|`). The regex is run AFTER stripping the leading and
// trailing pipes and the inner pipes — it sees only the cell-text
// concatenation, which for a separator row is `-`, `:`, and whitespace.
const SEPARATOR_INNER = /^[\s:\-]+$/;

export function stripTelegramFormatting(input: string): string {
  if (!input) return input;

  // 1. Remove triple-backtick fence markers, keep the inner text as plain.
  let text = input.replace(FENCE_OPEN, '').replace(FENCE_CLOSE, '');

  // 2. Convert pipe-tables to dot-separated lines, drop separator rows.
  const out: string[] = [];
  for (const line of text.split('\n')) {
    if (!PIPE_ROW.test(line)) {
      out.push(line);
      continue;
    }
    // Strip outer pipes, then test the joined inner text — if it's all
    // dashes/colons/whitespace, this is the `|---|---|` separator row.
    const inner = line
      .trim()
      .replace(/^\|/, '')
      .replace(/\|\s*$/, '');
    const innerNoPipes = inner.replace(/\|/g, '');
    if (SEPARATOR_INNER.test(innerNoPipes)) continue;

    const cells = inner
      .split('|')
      .map((c) => c.trim())
      .filter((c) => c.length > 0);
    if (cells.length === 0) {
      // Empty pipe-only line; drop it.
      continue;
    }
    out.push(cells.join(' · '));
  }
  text = out.join('\n');

  // 3. Collapse 3+ blank lines to keep the visual rhythm tight.
  text = text.replace(/\n{3,}/g, '\n\n');

  return text.trim();
}
