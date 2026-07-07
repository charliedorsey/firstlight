#!/usr/bin/env node
// ternlight_bridge.js — stdin/stdout bridge between Python and @ternlight/base.
//
// Single mode:  echo '"some text"'          | node ternlight_bridge.js  → [float, ...]
// Batch mode:   echo '["text1", "text2"]'   | node ternlight_bridge.js  → [[float, ...], ...]
//
// Auto-detects single vs batch from the JSON input type (string vs array).
// Outputs JSON to stdout. Errors go to stderr as JSON {error: "..."}.

import { embed } from '@ternlight/base';

async function main() {
  let raw = '';
  for await (const chunk of process.stdin) raw += chunk;

  const input = JSON.parse(raw);
  const texts = typeof input === 'string' ? [input] : input;

  const vectors = [];
  for (const text of texts) {
    const vec = await embed(text);
    vectors.push(Array.from(vec));
  }

  const output = typeof input === 'string' ? vectors[0] : vectors;
  process.stdout.write(JSON.stringify(output));
}

main().catch(err => {
  process.stderr.write(JSON.stringify({ error: err.message }));
  process.exit(1);
});
