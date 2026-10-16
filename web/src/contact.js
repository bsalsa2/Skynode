// Contact form behaviour (web/contact.html). The page works without this file:
// the browser then posts the form to Netlify itself. This adds checks that name
// the problem next to the field, and sends the message without leaving the page.
import { HONEYPOT, encodeBody, mailtoFallback, validate } from './contact-form.js';

const form = document.querySelector('.contact-form');

if (form) {
  const status = form.querySelector('.form-status');
  const button = form.querySelector('button[type="submit"]');
  const fieldNames = ['name', 'email', 'message'];

  // The browser's own pop-ups are replaced by messages beside each field.
  form.noValidate = true;

  const input = (name) => form.elements[name];
  const errorBox = (name) => form.querySelector(`#cf-${name}-error`);

  function showErrors(errors) {
    let first = null;
    for (const name of fieldNames) {
      const box = errorBox(name);
      const message = errors[name] || '';
      box.textContent = message;
      box.hidden = !message;
      input(name).setAttribute('aria-invalid', message ? 'true' : 'false');
      if (message && !first) first = input(name);
    }
    if (first) first.focus();
  }

  function say(text, { link = false } = {}) {
    status.textContent = text;
    if (link) {
      status.append(' ');
      const a = document.createElement('a');
      a.className = 'u-link';
      a.href = mailtoFallback(form.dataset.email, Object.fromEntries(new FormData(form)));
      a.textContent = form.dataset.email;
      status.append(a, '.');
    }
    status.hidden = false;
  }

  // Clear a field's message as soon as the visitor starts fixing it.
  for (const name of fieldNames) {
    input(name).addEventListener('input', () => {
      errorBox(name).hidden = true;
      input(name).setAttribute('aria-invalid', 'false');
    });
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    status.hidden = true;

    const fields = Object.fromEntries(new FormData(form));
    const result = validate({ ...fields, [HONEYPOT]: fields[HONEYPOT] });
    showErrors(result.errors);
    if (!result.ok) return;

    // A robot filled in the hidden field. Look like it worked; send nothing.
    if (result.spam) {
      form.reset();
      say(form.dataset.success);
      return;
    }

    button.disabled = true;
    const label = button.firstChild.textContent;
    button.firstChild.textContent = `${form.dataset.sending} `;
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: encodeBody(result.values),
      });
      if (!response.ok) throw new Error(`The form service answered ${response.status}.`);
      form.reset();
      say(form.dataset.success);
    } catch (error) {
      console.warn('[talo] contact form could not send.', error);
      say(form.dataset.failure, { link: true });
    } finally {
      button.disabled = false;
      button.firstChild.textContent = label;
    }
  });
}
