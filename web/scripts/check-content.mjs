// Checks src/content.js before every build, so a typo or a missing field
// shows up as a clear message (pointing at the line) instead of a broken
// page or a confusing build error. Run it on its own with: npm run check
//
// On GitHub, messages also appear as annotations on the pull request.

import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = join(here, '..');
const file = process.argv[2] ? join(process.cwd(), process.argv[2]) : join(webRoot, 'src', 'content.js');
const shownPath = relative(join(webRoot, '..'), file);
const inCI = !!process.env.GITHUB_ACTIONS;
const source = existsSync(file) ? readFileSync(file, 'utf8') : '';
const lines = source.split('\n');

const errors = [];
const warnings = [];

// Best guess at the line a value lives on, for friendlier messages.
function lineOf(value) {
  if (typeof value !== 'string' || !value.trim()) return undefined;
  const needle = value.trim().slice(0, 40);
  const i = lines.findIndex((l) => l.includes(needle));
  return i >= 0 ? i + 1 : undefined;
}
// Line of `needle` at or after the line containing `anchor`.
function lineAfter(anchor, needle) {
  const start = lines.findIndex((l) => l.includes(anchor));
  if (start < 0) return undefined;
  const i = lines.findIndex((l, n) => n >= start && l.includes(needle));
  return i >= 0 ? i + 1 : undefined;
}
const err = (msg, line) => errors.push({ msg, line });
const warn = (msg, line) => warnings.push({ msg, line });

function print(list, level) {
  for (const { msg, line } of list) {
    const where = line ? `${shownPath}:${line}` : shownPath;
    if (inCI) console.log(`::${level} file=${shownPath}${line ? `,line=${line}` : ''}::${msg}`);
    console.log(`  ${level === 'error' ? 'ERROR' : 'warning'}  ${where}\n           ${msg}`);
  }
}

function finish() {
  if (warnings.length) {
    console.log(`\ncontent.js: ${warnings.length} warning(s)`);
    print(warnings, 'warning');
  }
  if (errors.length) {
    console.log(`\ncontent.js: ${errors.length} problem(s) to fix before the site can build`);
    print(errors, 'error');
    console.log('\nNothing was published. Fix the line(s) above and commit again.\n');
    process.exit(1);
  }
}

// ---- 1. Is it valid JavaScript? -------------------------------------------
if (!existsSync(file)) {
  err(`File not found: ${shownPath}`);
  finish();
}
const syntax = spawnSync(process.execPath, ['--check', file], { encoding: 'utf8' });
if (syntax.status !== 0) {
  const out = syntax.stderr || '';
  const line = Number((out.match(/:(\d+)\s*\n/) || [])[1]) || undefined;
  const reason = (out.match(/SyntaxError: (.*)/) || [])[1] || 'the file could not be read';
  err(
    `Typo: ${reason}. Usual causes: a missing comma at the end of the line above, ` +
      `a missing quote, or an apostrophe inside 'single quotes' (wrap that text in backticks instead).`,
    line
  );
  finish();
}

// ---- 2. Does it have everything the page needs? ---------------------------
let content;
try {
  ({ content } = await import(pathToFileURL(file).href));
} catch (e) {
  err(`Could not load the file: ${e.message}`);
  finish();
}
if (!content || typeof content !== 'object') {
  err('The file must export `content` (the first line should be: export const content = {).');
  finish();
}

const get = (path) => path.split('.').reduce((o, k) => (o == null ? o : o[k]), content);

function text(path, value = get(path)) {
  if (typeof value !== 'string' || !value.trim()) {
    const simple = !/\.\d+\./.test(path); // list items: no reliable line to point at
    err(`${path} is missing or empty.`, simple ? lineOf(path.split('.').pop() + ':') : undefined);
    return false;
  }
  return true;
}

function list(path, { min = 1 } = {}) {
  const value = get(path);
  if (!Array.isArray(value)) {
    err(`${path} should be a list in [square brackets].`);
    return [];
  }
  if (value.length < min) err(`${path} needs at least ${min} item(s).`);
  return value;
}

const sectionIds = new Set(['top', 'math', 'how', 'mount', 'status', 'build', 'roadmap']);
if (Array.isArray(get('results.items')) && get('results.items').length) sectionIds.add('results');
if (Array.isArray(get('limits.items')) && get('limits.items').length) sectionIds.add('limits');

function link(path, value = get(path)) {
  if (!text(path, value)) return;
  if (value.startsWith('#')) {
    if (!sectionIds.has(value.slice(1)))
      err(`${path} points to "${value}", which isn't a section on the page. Use one of: ${[...sectionIds].map((s) => '#' + s).join(', ')}.`, lineOf(value));
  } else if (value.startsWith('http://')) {
    warn(`${path} uses http://. Prefer https:// so browsers don't warn visitors.`, lineOf(value));
  } else if (/^\.\/[\w-]+\.html$/.test(value)) {
    if (!existsSync(join(webRoot, value.slice(2))))
      err(`${path} points to "${value}", but there's no such page in web/.`, lineOf(value));
  } else if (!/^(https:\/\/|mailto:)/.test(value)) {
    err(`${path} should start with https://, mailto:, #, or ./page.html (got "${value}").`, lineOf(value));
  }
}

function publicFile(path, value = get(path)) {
  if (!value || /^https:\/\//.test(value)) return;
  if (!existsSync(join(webRoot, 'public', value)))
    err(`${path} is "${value}", but there's no file at web/public/${value}. Upload it there first.`, lineOf(value));
}

const gc = get('analytics.goatcounter');
if (gc && !/^[a-z0-9-]+$/.test(gc))
  err(`analytics.goatcounter should be just your GoatCounter code, like 'skynode' (lowercase letters, numbers, dashes), not "${gc}".`, lineOf(gc));

text('meta.title');
text('meta.description');
link('meta.url');

text('nav.brand');
list('nav.links').forEach((l, i) => {
  text(`nav.links.${i}.label`, l?.label);
  link(`nav.links.${i}.href`, l?.href);
});

['eyebrow', 'headline', 'sub', 'caption'].forEach((k) => text(`hero.${k}`));
text('hero.primary.label');
link('hero.primary.href');
text('hero.secondary.label');
link('hero.secondary.href');
list('hero.facts').forEach((f, i) => text(`hero.facts.${i}`, f));
if (get('hero.cost') !== undefined) {
  text('hero.cost');
  // The cost claim must keep saying what it leaves out.
  if (!/before the computer/i.test(get('hero.cost') || ''))
    err('hero.cost must say the price is "before the computer that runs the model".', lineOf('cost:'));
}

const footage = get('hero.footage');
if (footage && footage.video) {
  publicFile('hero.footage.video');
  publicFile('hero.footage.poster');
  if (!footage.caption || !footage.caption.trim())
    err('hero.footage.caption is empty. Say what the clip shows before it goes on the page.', lineAfter('footage:', 'caption:'));
}

text('math.heading');
text('math.body');
if (get('math.stats') && !get('math.statsNote'))
  err('math.stats compares prices, so math.statsNote must say it is a price comparison only, not a capability comparison.', lineOf('stats:'));
if (get('math.statsNote') !== undefined) text('math.statsNote');
if (get('math.useCases')) {
  text('math.useCases.tag');
  text('math.useCases.text');
}
if (get('math.statement') !== undefined) {
  if (text('math.statement') && (get('math.statement').match(/\[/g) || []).length !== (get('math.statement').match(/\]/g) || []).length)
    err('math.statement has an unmatched [ or ]. Put [square brackets] around the words to light up.', lineOf('statement:'));
}
if (get('math.stats') !== undefined) {
  list('math.stats').forEach((s, i) => {
    text(`math.stats.${i}.label`, s?.label);
    text(`math.stats.${i}.value`, s?.value);
  });
}

text('how.heading');
list('how.steps').forEach((s, i) => {
  ['number', 'title', 'body'].forEach((k) => text(`how.steps.${i}.${k}`, s?.[k]));
});
text('how.note');
if (get('how.sensor')) {
  text('how.sensor.label');
  text('how.sensor.caption');
}
if (get('how.mount')) {
  text('how.mount.label');
  text('how.mount.caption');
  list('how.mount.parts').forEach((p, i) => {
    text(`how.mount.parts.${i}.name`, p?.name);
    text(`how.mount.parts.${i}.text`, p?.text);
  });
}

if (get('limits')) {
  text('limits.heading');
  list('limits.items').forEach((it, i) => {
    text(`limits.items.${i}.tag`, it?.tag);
    text(`limits.items.${i}.text`, it?.text);
  });
}

text('status.heading');
const LABELS = ['DONE', 'IN PROGRESS', 'NEXT'];
const counts = { DONE: 0, 'IN PROGRESS': 0, NEXT: 0 };
list('status.items').forEach((it, i) => {
  if (!text(`status.items.${i}.text`, it?.text)) return;
  if (!LABELS.includes(it?.label)) {
    err(
      `Status item ${i + 1} has label "${it?.label}". Use exactly 'DONE', 'IN PROGRESS', or 'NEXT' (capital letters).`,
      lineOf(it.text)
    );
  } else counts[it.label]++;
});

const results = get('results');
if (results && Array.isArray(results.items) && results.items.length) {
  text('results.heading');
  results.items.forEach((it, i) => {
    text(`results.items.${i}.value`, it?.value);
    text(`results.items.${i}.label`, it?.label);
  });
  if (!results.source || !results.source.trim())
    err('results has numbers but results.source is empty. Say how and when they were measured.', lineAfter('results:', 'source:'));
}

text('build.heading');
text('build.body');
if (get('build.quote') !== undefined) text('build.quote');

if (get('privacy')) {
  ['title', 'updated', 'intro', 'contactText'].forEach((k) => text(`privacy.${k}`));
  list('privacy.sections').forEach((sec, i) => {
    text(`privacy.sections.${i}.heading`, sec?.heading);
    text(`privacy.sections.${i}.text`, sec?.text);
    if (sec?.link) link(`privacy.sections.${i}.link.href`, sec.link.href);
  });
}

text('roadmap.heading');
if (get('roadmap.intro') !== undefined) text('roadmap.intro');
list('roadmap.phases').forEach((p, i) => {
  ['phase', 'title', 'body'].forEach((k) => text(`roadmap.phases.${i}.${k}`, p?.[k]));
});
text('roadmap.closing');

if (get('sister')) {
  ['label', 'name', 'linkLabel'].forEach((k) => text(`sister.${k}`));
  link('sister.href');
}

text('footer.brand');
list('footer.links').forEach((l, i) => {
  text(`footer.links.${i}.label`, l?.label);
  link(`footer.links.${i}.href`, l?.href);
});
text('footer.contactLabel');
if (text('footer.email') && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(get('footer.email')))
  err(`footer.email doesn't look like an email address.`, lineOf(get('footer.email')));

// ---- 3. House rules: no placeholders, no emoji ----------------------------
(function walk(value, path) {
  if (typeof value === 'string') {
    if (/lorem ipsum|\bTODO\b|\bTBD\b|\bxxx\b/i.test(value))
      err(`${path} still has placeholder text: "${value.slice(0, 60)}".`, lineOf(value));
    if (/\p{Extended_Pictographic}/u.test(value))
      warn(`${path} contains an emoji; the site style avoids them.`, lineOf(value));
  } else if (value && typeof value === 'object') {
    for (const [k, v] of Object.entries(value)) walk(v, path ? `${path}.${k}` : k);
  }
})(content, '');

finish();
console.log(
  `content.js OK: ${counts.DONE} done, ${counts['IN PROGRESS']} in progress, ${counts.NEXT} next` +
    (results?.items?.length ? `, ${results.items.length} result(s)` : '') +
    (footage?.video ? ', real footage on' : '')
);
