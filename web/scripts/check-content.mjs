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

const sectionIds = new Set(['top', 'project', 'results', 'roadmap']);

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

const gc = get('analytics.goatcounter');
if (gc && !/^[a-z0-9-]+$/.test(gc))
  err(`analytics.goatcounter should be just your GoatCounter code, like 'varn' (lowercase letters, numbers, dashes), not "${gc}".`, lineOf(gc));

text('meta.title');
text('meta.description');
link('meta.url');

text('nav.brand');
list('nav.links').forEach((l, i) => {
  text(`nav.links.${i}.label`, l?.label);
  link(`nav.links.${i}.href`, l?.href);
});
text('nav.github.label');
link('nav.github.href');

// ---- Hero
['eyebrow', 'headline', 'sub', 'stage', 'trackLabel'].forEach((k) => text(`hero.${k}`));
for (const b of ['primary', 'secondary']) {
  text(`hero.${b}.label`);
  link(`hero.${b}.href`);
}
list('hero.facts').forEach((f, i) => text(`hero.facts.${i}`, f));
list('hero.tagline').forEach((t, i) => text(`hero.tagline.${i}`, t));
// The drone in the hero photo is an illustration, not a detection.
if (!/\bSAMPLE\b/.test(get('hero.trackLabel') || ''))
  err('hero.trackLabel must contain the word SAMPLE: the tracked drone in the hero is an illustration.', lineOf('trackLabel:'));
// Until the hardware runs, the status row has to say so.
if (!/prototype/i.test(get('hero.stage') || ''))
  err('hero.stage must say this is a prototype (for example "Research prototype").', lineOf('stage:'));

// ---- How it works
text('project.kicker');
list('project.heading').forEach((h, i) => text(`project.heading.${i}`, h));
text('project.body');
list('project.steps').forEach((st, i) => {
  if (!['eye', 'brain', 'shield', 'crosshair', 'plane', 'database'].includes(st?.icon))
    err(`project.steps.${i}.icon should be one of eye, brain, shield, crosshair, plane, database.`, lineOf('steps:'));
  ['title', 'text'].forEach((k) => text(`project.steps.${i}.${k}`, st?.[k]));
});
text('project.feedLabel');
if (!/\bSAMPLE\b/.test(get('project.feedLabel') || ''))
  err('project.feedLabel must contain the word SAMPLE: the dashboard panel is a simulation, not a live feed.', lineOf('feedLabel:'));
text('project.objectsLabel');
list('project.objects').forEach((o, i) => {
  ['name', 'value', 'kind'].forEach((k) => text(`project.objects.${i}.${k}`, o?.[k]));
  if (!['uav', 'plane', 'bird', 'heli'].includes(o?.kind))
    err(`project.objects.${i}.kind should be 'uav', 'plane', 'bird' or 'heli'.`, lineOf('objects:'));
});
list('project.readouts').forEach((r, i) => text(`project.readouts.${i}`, r));

// ---- Test results: only measured numbers, always with a source
text('results.kicker');
text('results.heading');
text('results.body');
text('results.button.label');
link('results.button.href');
const cards = list('results.cards');
cards.forEach((card, i) => {
  ['icon', 'title', 'value'].forEach((k) => text(`results.cards.${i}.${k}`, card?.[k]));
  list(`results.cards.${i}.caption`).forEach((cap, j) => text(`results.cards.${i}.caption.${j}`, cap));
});
if (!get('results.source') || !String(get('results.source')).trim())
  err('results has numbers but results.source is empty. Say how and when they were measured.', lineAfter('results:', 'source:'));
else
  cards.forEach((card, i) => {
    // Every percentage on a card must appear in the source, so made-up numbers can't slip in.
    const pct = String(card?.value || '').replace(/[~≈]/g, '');
    if (/%$/.test(pct) && !String(get('results.source')).includes(pct))
      err(`results.cards.${i}.value is ${card.value}, but results.source doesn't mention ${pct}. Add how it was measured.`, lineOf(card.value));
  });
['icon', 'title'].forEach((k) => text(`results.conditions.${k}`));
list('results.conditions.items').forEach((it, i) => text(`results.conditions.items.${i}`, it));
text('results.conditions.link.label');
link('results.conditions.link.href');

// ---- The road ahead
['kicker', 'heading'].forEach((k) => text(`roadmap.${k}`));
list('roadmap.body').forEach((line, i) => text(`roadmap.body.${i}`, line));
text('roadmap.button.label');
link('roadmap.button.href');
list('roadmap.steps').forEach((st, i) => {
  text(`roadmap.steps.${i}.when`, st?.when);
  text(`roadmap.steps.${i}.text`, st?.text);
  // A date in the past would read as a missed deadline.
  const m = /(?:Q([1-4])\s+)?(20\d\d)/.exec(st?.when || '');
  if (m) {
    const now = new Date();
    const end = new Date(Number(m[2]), m[1] ? Number(m[1]) * 3 : 12, 0);
    if (end < now) err(`roadmap.steps.${i}.when is "${st.when}", which is already in the past.`, lineOf(st.when));
  }
});

// ---- Privacy page
if (get('privacy')) {
  ['title', 'updated', 'intro', 'contactText'].forEach((k) => text(`privacy.${k}`));
  list('privacy.sections').forEach((sec, i) => {
    text(`privacy.sections.${i}.heading`, sec?.heading);
    text(`privacy.sections.${i}.text`, sec?.text);
    if (sec?.link) link(`privacy.sections.${i}.link.href`, sec.link.href);
  });
}

// ---- Footer
text('footer.brand');
text('footer.tagline');
list('footer.links').forEach((l, i) => {
  text(`footer.links.${i}.label`, l?.label);
  link(`footer.links.${i}.href`, l?.href);
});
text('footer.copyright');
// Varn Labs is a label, not a company, and the code is MIT licensed.
if (/all rights reserved|\b(inc|llc|ltd|corp)\b\.?/i.test(get('footer.copyright') || ''))
  err('footer.copyright must not read like a registered company or "All rights reserved": the project is MIT licensed.', lineOf('copyright:'));
text('footer.privacy.label');
link('footer.privacy.href');
text('footer.contactLabel');
if (text('footer.email') && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(get('footer.email')))
  err(`footer.email doesn't look like an email address.`, lineOf(get('footer.email')));

// Brand voice: Varn only watches. These words never appear on the page.
for (const word of ['missile', 'kill', 'strike', 'defeat', 'weapon']) {
  const i = lines.findIndex((l) => !/^\s*\/\//.test(l) && new RegExp(`\\b${word}`, 'i').test(l));
  if (i >= 0) err(`"${word}" is off-brand: Varn is detection only. Reword this line.`, i + 1);
}

// ---- 3. House rules: no placeholders, no emoji ----------------------------
(function walk(value, path) {
  if (typeof value === 'string') {
    if (/lorem ipsum|\bTODO\b|\bTBD\b|\bxxx\b/i.test(value))
      err(`${path} still has placeholder text: "${value.slice(0, 60)}".`, lineOf(value));
    if (/\p{Extended_Pictographic}/u.test(value.replace(/[©®™]/g, '')))
      warn(`${path} contains an emoji; the site style avoids them.`, lineOf(value));
  } else if (value && typeof value === 'object') {
    for (const [k, v] of Object.entries(value)) walk(v, path ? `${path}.${k}` : k);
  }
})(content, '');

// ---- 4. Site settings: the contact address must be a real one --------------
// Only a warning: the site still builds, but the footer and privacy page
// would show the placeholder address.
const configFile = join(webRoot, 'src', 'config.js');
if (existsSync(configFile) && /CONTACT_EMAIL\s*=\s*['"][^'"]*@example\.(com|org|net)['"]/.test(readFileSync(configFile, 'utf8')))
  warn('web/src/config.js still has the placeholder CONTACT_EMAIL; set your real contact address.');

finish();
console.log(`content.js OK: ${cards.length} result card(s), ${get('roadmap.steps').length} roadmap step(s)`);
