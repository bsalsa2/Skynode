// The phone upload page (field.html): sign in with Google, record or pick a video,
// and it goes to your Drive. All the Drive work is in field-upload.js.
import { CLIENT_ID } from './field-config.js';
import { FOLDER_NAME, SCOPE, SignInError, clipName, findOrCreateFolder, rejectReason,
  uploadFile } from './field-upload.js';

const $ = (id) => document.getElementById(id);
const els = {
  status: $('status'), signIn: $('sign-in'), signOut: $('sign-out'), actions: $('actions'),
  record: $('record'), choose: $('choose'), list: $('uploads'), setup: $('setup'),
};

let token = null; // the access token lives here and nowhere else (never stored)
let folderId = null;
let tokenClient = null;
let sequence = 0;
const waiting = []; // uploads that need a fresh sign-in

function say(text) {
  els.status.textContent = text;
}

function show(signedIn) {
  els.signIn.hidden = signedIn;
  els.signOut.hidden = !signedIn;
  els.actions.hidden = !signedIn;
}

function loadGoogle() {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.oauth2) return resolve();
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.onload = resolve;
    script.onerror = () => reject(new Error('Could not reach Google. Check your connection.'));
    document.head.append(script);
  });
}

function requestToken() {
  tokenClient.requestAccessToken({ prompt: token ? '' : 'select_account' });
}

function onToken(response) {
  if (response.error || !response.access_token) {
    say('Sign-in did not finish. Tap "Sign in with Google" to try again.');
    return;
  }
  token = response.access_token;
  folderId = null; // look the folder up again with the new token
  show(true);
  say(`Signed in. Clips go to My Drive ▸ ${FOLDER_NAME}.`);
  while (waiting.length) waiting.shift()();
}

function row(name, size) {
  const item = document.createElement('li');
  const label = document.createElement('span');
  label.className = 'name';
  label.textContent = `${name} · ${(size / 1024 / 1024).toFixed(1)} MB`;
  const bar = document.createElement('progress');
  bar.max = 100;
  bar.value = 0;
  const note = document.createElement('span');
  note.className = 'note';
  note.textContent = 'Waiting…';
  item.append(label, bar, note);
  els.list.prepend(item);
  return { item, bar, note };
}

async function send(file) {
  const problem = rejectReason(file);
  const name = clipName(file, new Date(), sequence++ % 100);
  const ui = row(name, file.size);
  if (problem) {
    ui.note.textContent = problem;
    ui.item.classList.add('failed');
    return;
  }
  const attempt = async () => {
    ui.item.classList.remove('failed');
    ui.note.textContent = 'Uploading…';
    try {
      folderId ??= await findOrCreateFolder(token);
      await uploadFile({
        token, folderId, file, name,
        onProgress: (sent, total) => { ui.bar.value = Math.round((100 * sent) / total); },
      });
      ui.bar.value = 100;
      ui.item.classList.add('done');
      ui.note.textContent = 'In your Drive. It is used the next time training runs.';
    } catch (error) {
      ui.item.classList.add('failed');
      if (error instanceof SignInError) {
        ui.note.textContent = 'Sign-in expired. Signing in again…';
        waiting.push(attempt);
        requestToken();
      } else {
        ui.note.textContent = `${error.message} Tap to retry.`;
        ui.item.onclick = () => { ui.item.onclick = null; attempt(); };
      }
    }
  };
  await attempt();
}

function take(input) {
  const files = [...input.files];
  input.value = ''; // so picking the same file again still fires
  files.forEach(send);
}

async function main() {
  if (!CLIENT_ID) {
    els.setup.hidden = false;
    say('This page is not set up yet.');
    return;
  }
  try {
    await loadGoogle();
  } catch (error) {
    say(error.message);
    return;
  }
  tokenClient = window.google.accounts.oauth2.initTokenClient({
    client_id: CLIENT_ID, scope: SCOPE, callback: onToken,
    error_callback: () => say('Sign-in was closed. Tap "Sign in with Google" to try again.'),
  });
  els.signIn.hidden = false;
  say('Sign in to send clips to your Drive.');
  els.signIn.addEventListener('click', requestToken);
  els.signOut.addEventListener('click', () => {
    window.google.accounts.oauth2.revoke(token, () => {});
    token = null;
    folderId = null;
    show(false);
    els.signIn.hidden = false;
    say('Signed out.');
  });
  els.record.addEventListener('change', () => take(els.record));
  els.choose.addEventListener('change', () => take(els.choose));
}

main();
