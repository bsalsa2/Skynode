// Contact form: sends through a form service when one is configured
// (data-endpoint), otherwise opens the visitor's email app, pre-filled.
export function initContactForm() {
  const form = document.getElementById('contact-form');
  if (!form) return;
  const status = form.querySelector('.contact-status');
  const button = form.querySelector('button[type="submit"]');
  const label = button.querySelector('.btn-label');
  const idle = label.textContent;
  const say = (text, bad = false) => {
    status.hidden = false;
    status.textContent = text;
    status.classList.toggle('is-error', bad);
  };

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = new FormData(form);
    if (data.get('company')) return; // honeypot: bots fill hidden fields
    const name = String(data.get('name')).trim();
    const from = String(data.get('email')).trim();
    const message = String(data.get('message')).trim();
    const endpoint = form.dataset.endpoint;

    if (!endpoint) {
      const subject = `Varn website question from ${name}`;
      const body = `${message}\n\n${name}\n${from}`;
      window.location.href = `mailto:${form.dataset.email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
      say(form.dataset.mailto);
      return;
    }

    button.disabled = true;
    label.textContent = form.dataset.sending;
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ name, email: from, message, _replyto: from }),
      });
      if (!res.ok) throw new Error(String(res.status));
      form.reset();
      say(form.dataset.success);
    } catch {
      say(form.dataset.error, true);
    } finally {
      button.disabled = false;
      label.textContent = idle;
    }
  });
}
