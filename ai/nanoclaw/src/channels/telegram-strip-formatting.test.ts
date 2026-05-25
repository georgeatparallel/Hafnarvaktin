import { describe, it, expect } from 'vitest';
import { stripTelegramFormatting } from './telegram-strip-formatting.js';

describe('stripTelegramFormatting', () => {
  it('removes plain ``` fences but keeps the inner text', () => {
    const input = '```\nA · 1kn · 14:32\nB · 0kn · 09:12\n```';
    expect(stripTelegramFormatting(input)).toBe('A · 1kn · 14:32\nB · 0kn · 09:12');
  });

  it('removes language-tagged fences (```text, ```python, etc.)', () => {
    const input = '```text\n3 vessel(s):\nA · pilot · 0kn\n```';
    expect(stripTelegramFormatting(input)).toBe('3 vessel(s):\nA · pilot · 0kn');
  });

  it('converts a pipe table to dot-separated rows and drops the separator', () => {
    const input = [
      '| Name | Type | Speed |',
      '|------|------|-------|',
      '| A    | pilot | 0kn  |',
      '| B    | cargo | 1kn  |',
    ].join('\n');
    expect(stripTelegramFormatting(input)).toBe('Name · Type · Speed\nA · pilot · 0kn\nB · cargo · 1kn');
  });

  it('handles a fence wrapping a pipe table — both layers get peeled', () => {
    const input = '```\n| A | 1kn |\n|---|-----|\n| B | 0kn |\n```';
    expect(stripTelegramFormatting(input)).toBe('A · 1kn\nB · 0kn');
  });

  it('leaves inline code spans alone (single backticks survive)', () => {
    const input = 'see `file.py` and `cmd --flag` for details';
    expect(stripTelegramFormatting(input)).toBe(input);
  });

  it('passes through plain prose unchanged', () => {
    const input = 'Goðafoss is currently outbound at 8.4kn.';
    expect(stripTelegramFormatting(input)).toBe(input);
  });

  it('passes through dot-separated rows unchanged', () => {
    const input = '3 vessel(s):\nA · pilot · 0kn\nB · cargo · 1kn';
    expect(stripTelegramFormatting(input)).toBe(input);
  });

  it('collapses runs of 3+ blank lines to one blank line', () => {
    const input = 'first\n\n\n\nsecond';
    expect(stripTelegramFormatting(input)).toBe('first\n\nsecond');
  });

  it('returns empty input unchanged', () => {
    expect(stripTelegramFormatting('')).toBe('');
  });

  it('handles a separator row written with colons (alignment markers)', () => {
    const input = '| A | B |\n|:---|:---:|\n| 1 | 2 |';
    expect(stripTelegramFormatting(input)).toBe('A · B\n1 · 2');
  });

  it('drops a pipe row that contains only empty cells', () => {
    const input = '| | |\nreal line';
    expect(stripTelegramFormatting(input)).toBe('real line');
  });

  it('preserves Icelandic + Unicode characters through the pipeline', () => {
    const input = '| Ísafjörður | Sundahöfn |\n|---|---|\n| Goðafoss | Bára |';
    expect(stripTelegramFormatting(input)).toBe('Ísafjörður · Sundahöfn\nGoðafoss · Bára');
  });
});
