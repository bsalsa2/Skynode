// ---------------------------------------------------------------------------
//  CONTACT FORM LOGIC
//
//  The checks and the request body for web/contact.html, kept apart from the
//  page code (contact.js) so they can be tested without a browser
//  (test/contact-form.test.mjs).
//
//  The form is a Netlify Form. Netlify finds it in the built contact.html
//  (the `data-netlify` attribute), stores each submission, and emails it to the
//  address set under Site configuration > Forms > Form notifications.
// ---------------------------------------------------------------------------

export const FORM_NAME = 'contact';
export const HONEYPOT = 'bot-field';
export const LIMITS = { name: 100, email: 254, message: 5000, minMessage: 10 };

// Same loose shape check as footer.email in scripts/check-content.mjs: it
// catches typos, it doesn't try to prove the address exists.
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Trim the three visible fields. Anything missing becomes ''. */
export function clean(fields = {}) {
  const get = (key) => (typeof fields[key] === 'string' ? fields[key].trim() : '');
  return { name: get('name'), email: get('email'), message: get('message') };
}

/**
 * Check what the visitor typed.
 * -> { ok, values, errors }  where errors maps a field name to a short sentence.
 * A filled-in honeypot field is not an error the visitor can see: it is a
 * robot, so `spam` is set and the page pretends the message went through.
 */
export function validate(fields = {}) {
  const values = clean(fields);
  const errors = {};

  if (!values.name) errors.name = 'Please enter your name.';
  else if (values.name.length > LIMITS.name) errors.name = `Please keep your name under ${LIMITS.name} characters.`;

  if (!values.email) errors.email = 'Please enter your email address, so I can reply.';
  else if (values.email.length > LIMITS.email || !EMAIL.test(values.email))
    errors.email = 'That email address doesn’t look right.';

  if (!values.message) errors.message = 'Please write a message.';
  else if (values.message.length < LIMITS.minMessage)
    errors.message = `Please write a little more (at least ${LIMITS.minMessage} characters).`;
  else if (values.message.length > LIMITS.message)
    errors.message = `Please keep it under ${LIMITS.message} characters.`;

  const spam = typeof fields[HONEYPOT] === 'string' && fields[HONEYPOT].trim() !== '';
  return { ok: Object.keys(errors).length === 0, spam, values, errors };
}

/** The urlencoded body Netlify expects: the form name, the three fields and the (empty) honeypot. */
export function encodeBody(values) {
  const { name, email, message } = clean(values);
  return new URLSearchParams({ 'form-name': FORM_NAME, name, email, message, [HONEYPOT]: '' }).toString();
}

/** A mailto: link carrying the visitor's message, for when sending fails. */
export function mailtoFallback(to, values = {}) {
  const { name, message } = clean(values);
  const body = [message.slice(0, 1500), name ? `\n— ${name}` : ''].join('');
  return `mailto:${to}?subject=${encodeURIComponent('Message from the Talo site')}&body=${encodeURIComponent(body)}`;
}
