// Tests for the contact form's checks and request body (src/contact-form.js).
// Run with `npm test`.
import test from 'node:test';
import assert from 'node:assert/strict';
import { FORM_NAME, HONEYPOT, LIMITS, clean, encodeBody, mailtoFallback, validate } from '../src/contact-form.js';

const good = { name: 'Ada Lovelace', email: 'ada@example.org', message: 'I would like to talk about a pilot.' };

test('a complete, sensible message passes with no errors', () => {
  const result = validate(good);
  assert.equal(result.ok, true);
  assert.deepEqual(result.errors, {});
  assert.equal(result.spam, false);
  assert.deepEqual(result.values, good);
});

test('spaces around the fields are trimmed', () => {
  const result = validate({ name: '  Ada  ', email: ' ada@example.org ', message: '   a long enough message   ' });
  assert.equal(result.ok, true);
  assert.deepEqual(result.values, { name: 'Ada', email: 'ada@example.org', message: 'a long enough message' });
});

test('every field is required, and each missing one gets its own message', () => {
  const result = validate({});
  assert.equal(result.ok, false);
  assert.deepEqual(Object.keys(result.errors).sort(), ['email', 'message', 'name']);
  // Spaces alone count as empty
  assert.equal(validate({ ...good, name: '   ' }).errors.name, 'Please enter your name.');
});

test('email must look like an address', () => {
  for (const bad of ['ada', 'ada@', '@example.org', 'ada@example', 'ada @example.org', 'a@b@c.d']) {
    assert.ok(validate({ ...good, email: bad }).errors.email, `"${bad}" should be refused`);
  }
  assert.equal(validate({ ...good, email: 'ada.l+talo@sub.example.org' }).ok, true);
});

test('the message needs a few words, and has an upper limit', () => {
  assert.ok(validate({ ...good, message: 'hi' }).errors.message);
  assert.equal(validate({ ...good, message: 'x'.repeat(LIMITS.minMessage) }).ok, true);
  assert.equal(validate({ ...good, message: 'x'.repeat(LIMITS.message) }).ok, true);
  assert.ok(validate({ ...good, message: 'x'.repeat(LIMITS.message + 1) }).errors.message);
});

test('over-long names and addresses are refused', () => {
  assert.ok(validate({ ...good, name: 'n'.repeat(LIMITS.name + 1) }).errors.name);
  assert.ok(validate({ ...good, email: `${'a'.repeat(LIMITS.email)}@example.org` }).errors.email);
});

test('a filled-in honeypot marks the submission as spam without producing a visible error', () => {
  const result = validate({ ...good, [HONEYPOT]: 'http://spam.example' });
  assert.equal(result.spam, true);
  assert.equal(result.ok, true);
  assert.equal(validate({ ...good, [HONEYPOT]: '   ' }).spam, false);
});

test('values that are not strings are treated as empty, not as a crash', () => {
  assert.deepEqual(clean({ name: 5, email: null, message: undefined }), { name: '', email: '', message: '' });
  assert.equal(validate({ name: {}, email: [], message: 7 }).ok, false);
});

test('the request body has the form name Netlify looks for, the three fields and an empty honeypot', () => {
  const body = new URLSearchParams(encodeBody(good));
  assert.equal(body.get('form-name'), FORM_NAME);
  assert.equal(FORM_NAME, 'contact');
  assert.equal(body.get('name'), good.name);
  assert.equal(body.get('email'), good.email);
  assert.equal(body.get('message'), good.message);
  assert.equal(body.get(HONEYPOT), '');
  assert.deepEqual([...body.keys()], ['form-name', 'name', 'email', 'message', HONEYPOT]);
});

test('special characters survive encoding', () => {
  const message = 'Cost & scope = ?\nSecond line, with “quotes” and ünïcode';
  assert.equal(new URLSearchParams(encodeBody({ ...good, message })).get('message'), message);
});

test('the mailto fallback is addressed to the contact email and carries the message', () => {
  const link = mailtoFallback('hello@tryvarn.com', good);
  assert.ok(link.startsWith('mailto:hello@tryvarn.com?subject='));
  const body = new URLSearchParams(link.split('?')[1]).get('body');
  assert.ok(body.includes(good.message));
  assert.ok(body.includes('Ada Lovelace'));
  // A very long message is cut so the mail program does not choke on the link
  const long = mailtoFallback('hello@tryvarn.com', { ...good, message: 'y'.repeat(9000) });
  assert.ok(long.length < 4000);
});
