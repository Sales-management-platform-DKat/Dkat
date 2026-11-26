#!/usr/bin/env node
// Translation audit for DKat.
//
// Messages use the Vietnamese source text (or a dotted key such as "api.error.X") as the key,
// and src/locales/en.json maps it to English. This script parses every .js/.jsx file under src/
// and reports:
//   missing   – a key passed to t()/translate()/errorMessage()/{key: ...} that en.json lacks
//               (dotted keys must also exist in vi.json, otherwise Vietnamese shows the raw key)
//   hardcoded – Vietnamese text rendered without going through the catalog: JSX text, string
//               attributes (placeholder, title, aria-label, ...) and other string literals that
//               are not catalog keys. These stay Vietnamese after switching to English.
//
// Usage: node scripts/check-i18n.mjs [--json] [--list]     exit code 1 when anything is reported.
import { existsSync, readFileSync, statSync } from 'node:fs';
import { dirname, extname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseAst } from 'rollup/parseAst';

const root = fileURLToPath(new URL('..', import.meta.url));
const srcDir = join(root, 'src');
const en = JSON.parse(readFileSync(join(srcDir, 'locales/en.json'), 'utf8'));
const vi = JSON.parse(readFileSync(join(srcDir, 'locales/vi.json'), 'utf8'));

// Files that are data, not UI copy, or that only hold the i18n machinery itself.
const SKIP = new Set(['i18n/index.js', 'i18n/locale.js', 'mocks/data.js', 'seed.js', 'demo/demo-seed.js']);
// Literal arguments of these calls are never shown to users.
const SILENT_CALLS = new Set(['console.log', 'console.warn', 'console.error', 'localStorage.setItem',
  'localStorage.getItem', 'sessionStorage.setItem', 'sessionStorage.getItem', 'apiRequest', 'fetch',
  'querySelector', 'addEventListener', 'dispatchEvent', 'Error',
  // csv.js: the message is internal; the user sees error.translation.
  'rowError']);
const KEY_CALLS = new Set(['t', 'translate']);
// Proper nouns in demo/marketing content (people, districts, cities) are shown as-is in every language.
const PROPER_NOUNS = new Set(['Tiếng Việt', 'Quận 1', 'Thảo Điền', 'Bình Thạnh', 'Thủ Đức', 'Đà Nẵng', 'Nguyễn Minh Anh', 'Trần Gia Hân']);
const VIETNAMESE = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i;
const DOTTED_KEY = /^[a-z][\w-]*(\.[\w-]+)+$/;
const FILE_NAME = /\.(?:m?jsx?|css|json|svg|png|jpe?g|webp|csv|html)$/i;

// Only files reachable from the entry point are rendered; unused legacy files are not audited.
function reachableFiles(entry) {
  const seen = new Set();
  const queue = [entry];
  while (queue.length) {
    const path = queue.pop();
    if (seen.has(path)) continue;
    seen.add(path);
    const code = readFileSync(path, 'utf8');
    for (const match of code.matchAll(/(?:import|export)[^'"]*?from\s*['"](\.[^'"]+)['"]|import\(\s*['"](\.[^'"]+)['"]\s*\)/g)) {
      const target = resolve(dirname(path), match[1] || match[2]);
      const candidates = [target, `${target}.js`, `${target}.jsx`, join(target, 'index.js')];
      const found = candidates.find((candidate) => existsSync(candidate) && statSync(candidate).isFile()
        && ['.js', '.jsx'].includes(extname(candidate)));
      if (found) queue.push(found);
    }
  }
  return [...seen];
}

function calleeName(node) {
  if (node.type === 'Identifier') return node.name;
  if (node.type === 'MemberExpression' && !node.computed) {
    const object = calleeName(node.object);
    return object ? `${object}.${node.property.name}` : node.property.name;
  }
  return null;
}

function staticString(node) {
  if (!node) return null;
  if (node.type === 'Literal' && typeof node.value === 'string') return node.value;
  if (node.type === 'TemplateLiteral' && node.expressions.length === 0) return node.quasis[0].value.cooked;
  return null;
}

function lineOf(code, offset) {
  let line = 1;
  for (let i = 0; i < offset; i += 1) if (code.charCodeAt(i) === 10) line += 1;
  return line;
}

export function auditSource(code, file = '<source>') {
  const ast = parseAst(code, { jsx: true });
  const missing = [];
  const hardcoded = [];
  const keyNodes = new Set();

  const checkKey = (value, node) => {
    keyNodes.add(node);
    if (!value.trim()) return;
    const inEnglish = Object.hasOwn(en, value);
    const needsVietnamese = DOTTED_KEY.test(value);
    if (!inEnglish || (needsVietnamese && !Object.hasOwn(vi, value))) {
      missing.push({ file, line: lineOf(code, node.start), text: value });
    }
  };

  const visit = (node, parent, silent) => {
    if (!node || typeof node.type !== 'string') return;
    let childSilent = silent;
    if (node.type === 'CallExpression') {
      const name = calleeName(node.callee);
      const short = name?.split('.').pop();
      if (KEY_CALLS.has(short)) {
        const value = staticString(node.arguments[0]);
        if (value !== null) checkKey(value, node.arguments[0]);
        // A conditional key: t(cond ? 'A' : 'B')
        const arg = node.arguments[0];
        if (arg?.type === 'ConditionalExpression') {
          for (const branch of [arg.consequent, arg.alternate]) {
            const branchValue = staticString(branch);
            if (branchValue !== null) checkKey(branchValue, branch);
          }
        }
      } else if (short === 'errorMessage') {
        const value = staticString(node.arguments[1]);
        if (value !== null) checkKey(value, node.arguments[1]);
      }
      if (name && (SILENT_CALLS.has(name) || SILENT_CALLS.has(short))) childSilent = true;
    }
    if (node.type === 'NewExpression' && calleeName(node.callee) === 'Error') childSilent = true;
    if (node.type === 'ImportDeclaration' || node.type === 'ExportAllDeclaration') return;
    if (node.type === 'Property' && !node.computed) {
      const keyName = node.key.type === 'Identifier' ? node.key.name : node.key.value;
      const value = staticString(node.value);
      if (keyName === 'key' && value !== null && (VIETNAMESE.test(value) || DOTTED_KEY.test(value))) checkKey(value, node.value);
    }

    // Message keys handed around as plain strings (notify('branch.autoCreated'), { title: 'x.y' }).
    if (!childSilent && !keyNodes.has(node)) {
      const dotted = staticString(node);
      if (dotted !== null && DOTTED_KEY.test(dotted) && !FILE_NAME.test(dotted) && parent?.type !== 'ImportExpression'
          && !(parent?.type === 'Property' && parent.key === node) && parent?.type !== 'MemberExpression') checkKey(dotted, node);
    }
    if (!childSilent && !keyNodes.has(node)) {
      if (node.type === 'JSXText') {
        const text = node.value.replace(/\s+/g, ' ').trim();
        if (VIETNAMESE.test(text) && !PROPER_NOUNS.has(text)) hardcoded.push({ file, line: lineOf(code, node.start), text, kind: 'jsx-text' });
      } else {
        const value = staticString(node);
        // Text placed straight into JSX is rendered as-is even when the catalog knows it.
        const renderedDirectly = parent?.type === 'JSXAttribute' || parent?.type === 'JSXExpressionContainer';
        if (value !== null && VIETNAMESE.test(value) && !PROPER_NOUNS.has(value) && (renderedDirectly || !Object.hasOwn(en, value))
            && !(parent?.type === 'Property' && parent.key === node)) {
          const kind = parent?.type === 'JSXAttribute' ? `attr:${parent.name.name}` : 'literal';
          hardcoded.push({ file, line: lineOf(code, node.start), text: value, kind });
        }
      }
    }
    for (const [key, child] of Object.entries(node)) {
      if (key === 'start' || key === 'end') continue;
      if (Array.isArray(child)) child.forEach((item) => visit(item, node, childSilent));
      else if (child && typeof child.type === 'string') visit(child, node, childSilent);
    }
  };
  visit(ast, null, false);
  return { missing, hardcoded };
}

export function auditProject() {
  const result = { missing: [], hardcoded: [] };
  for (const path of reachableFiles(join(srcDir, 'main.jsx')).sort()) {
    const file = relative(srcDir, path).replaceAll('\\', '/');
    if (SKIP.has(file) || file.startsWith('locales/')) continue;
    const { missing, hardcoded } = auditSource(readFileSync(path, 'utf8'), file);
    result.missing.push(...missing);
    result.hardcoded.push(...hardcoded);
  }
  return result;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const result = auditProject();
  if (process.argv.includes('--json')) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    const byFile = (items) => Object.entries(items.reduce((acc, item) => {
      acc[item.file] = (acc[item.file] || 0) + 1; return acc;
    }, {})).sort((a, b) => b[1] - a[1]);
    console.log(`Missing translations: ${result.missing.length}`);
    for (const [file, count] of byFile(result.missing)) console.log(`  ${count.toString().padStart(4)}  ${file}`);
    console.log(`Hardcoded Vietnamese text: ${result.hardcoded.length}`);
    for (const [file, count] of byFile(result.hardcoded)) console.log(`  ${count.toString().padStart(4)}  ${file}`);
    if (process.argv.includes('--list')) {
      for (const item of [...result.missing, ...result.hardcoded]) {
        console.log(`${item.file}:${item.line}\t${item.kind || 'missing'}\t${item.text}`);
      }
    }
  }
  process.exitCode = result.missing.length || result.hardcoded.length ? 1 : 0;
}
