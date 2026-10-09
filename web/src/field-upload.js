// Uploading a phone clip to the signed-in person's own Google Drive.
//
// Everything here is plain functions with `fetch` passed in, so test/field-upload.test.mjs
// can run them with a fake server. No page, no secrets: the access token comes from the
// caller and lives only in memory.
//
// Permission: drive.file. The page can only see and write files and folders IT created.
// It cannot read the rest of the Drive, which is why the clips go to a folder of its own
// (My Drive / skynode_phone_uploads) that training/auto_train.py also reads.

export const FOLDER_NAME = 'skynode_phone_uploads';
export const SCOPE = 'https://www.googleapis.com/auth/drive.file';
export const CHUNK = 8 * 1024 * 1024; // Drive wants a multiple of 256 KiB
export const MAX_BYTES = 5 * 1024 ** 3; // a clip this big is a mistake, not a sky video
const FILES = 'https://www.googleapis.com/drive/v3/files';
const UPLOAD = 'https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable';
const FOLDER_TYPE = 'application/vnd.google-apps.folder';

// The extensions training/skynode_data.py accepts.
const EXTENSIONS = { 'video/mp4': 'mp4', 'video/quicktime': 'mov', 'video/webm': 'webm',
  'video/x-m4v': 'm4v', 'video/x-matroska': 'mkv', 'video/x-msvideo': 'avi' };
const KNOWN = new Set(Object.values(EXTENSIONS));

export class SignInError extends Error {}

const two = (n) => String(n).padStart(2, '0');

/** skynode-20261009-141500.mp4 (local time). `n` > 0 adds -n, for two clips in one second. */
export function clipName(file, now = new Date(), n = 0) {
  const stamp = `${now.getFullYear()}${two(now.getMonth() + 1)}${two(now.getDate())}`
    + `-${two(now.getHours())}${two(now.getMinutes())}${two(now.getSeconds())}`;
  const fromName = (file.name || '').split('.').pop().toLowerCase();
  const ext = EXTENSIONS[(file.type || '').split(';')[0]] || (KNOWN.has(fromName) ? fromName : 'mp4');
  return `skynode-${stamp}${n ? `-${n}` : ''}.${ext}`;
}

/** An error message for a file we won't send, or '' if it is fine. */
export function rejectReason(file) {
  if (!file || !file.size) return 'The file is empty.';
  if (file.size > MAX_BYTES) return 'The file is over 5 GB.';
  if (file.type && !file.type.startsWith('video/')) return 'That is not a video.';
  return '';
}

/** "bytes 0-8388607/20000000" for the chunk [start, end). */
export function contentRange(start, end, total) {
  return `bytes ${start}-${end - 1}/${total}`;
}

/** Where to continue after Drive's "308 Resume Incomplete": Range "bytes=0-8388607" -> 8388608. */
export function nextOffset(rangeHeader) {
  const match = /^bytes=0-(\d+)$/.exec(rangeHeader || '');
  return match ? Number(match[1]) + 1 : 0;
}

const authHeaders = (token) => ({ Authorization: `Bearer ${token}` });

async function check(response, what) {
  if (response.status === 401) throw new SignInError('Your Google sign-in expired.');
  if (!response.ok && response.status !== 308) {
    throw new Error(`${what} failed (${response.status}).`);
  }
  return response;
}

/** The id of the upload folder, creating it the first time. */
export async function findOrCreateFolder(token, fetchFn = fetch) {
  const q = `name='${FOLDER_NAME}' and mimeType='${FOLDER_TYPE}' and trashed=false`;
  const search = await check(await fetchFn(
    `${FILES}?${new URLSearchParams({ q, fields: 'files(id)', spaces: 'drive' })}`,
    { headers: authHeaders(token) }), 'Looking for the upload folder');
  const found = (await search.json()).files || [];
  if (found.length) return found[0].id;
  const made = await check(await fetchFn(`${FILES}?fields=id`, {
    method: 'POST',
    headers: { ...authHeaders(token), 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: FOLDER_NAME, mimeType: FOLDER_TYPE }),
  }), 'Creating the upload folder');
  return (await made.json()).id;
}

/** Opens a resumable upload and returns its session address. */
export async function startSession(token, folderId, name, file, fetchFn = fetch) {
  const response = await check(await fetchFn(UPLOAD, {
    method: 'POST',
    headers: {
      ...authHeaders(token),
      'Content-Type': 'application/json; charset=UTF-8',
      'X-Upload-Content-Type': file.type || 'video/mp4',
      'X-Upload-Content-Length': String(file.size),
    },
    body: JSON.stringify({ name, parents: [folderId] }),
  }), 'Starting the upload');
  const session = response.headers.get('Location');
  if (!session) throw new Error('Drive did not give an upload address.');
  return session;
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Sends the file in chunks and survives a dropped signal: after a network error it asks
 * Drive how much arrived and carries on from there (up to `retries` times in a row).
 * Returns the new file's id. `onProgress(sentBytes, totalBytes)` is called after each chunk.
 */
export async function uploadFile({ token, folderId, file, name, onProgress = () => {},
  fetchFn = fetch, chunk = CHUNK, retries = 5, wait = sleep }) {
  const session = await startSession(token, folderId, name, file, fetchFn);
  const total = file.size;
  let offset = 0;
  let failures = 0;
  while (true) {
    const end = Math.min(offset + chunk, total);
    let response;
    try {
      response = await fetchFn(session, {
        method: 'PUT',
        headers: { 'Content-Range': contentRange(offset, end, total) },
        body: file.slice(offset, end),
      });
      if (response.status >= 500) throw new Error(`Drive said ${response.status}.`);
    } catch (error) {
      if (++failures > retries) throw new Error('The connection kept dropping. Try again.');
      await wait(Math.min(1000 * 2 ** failures, 15000));
      // Ask Drive where it got to.
      try {
        const probe = await fetchFn(session, {
          method: 'PUT',
          headers: { 'Content-Range': `bytes */${total}` },
        });
        if (probe.status === 200 || probe.status === 201) return (await probe.json()).id;
        if (probe.status === 308) offset = nextOffset(probe.headers.get('Range'));
      } catch (ignored) { /* still offline: the next loop tries again */ }
      continue;
    }
    failures = 0;
    if (response.status === 200 || response.status === 201) {
      onProgress(total, total);
      return (await response.json()).id;
    }
    if (response.status === 308) {
      offset = nextOffset(response.headers.get('Range'));
      onProgress(offset, total);
      continue;
    }
    if (response.status === 404) throw new Error('The upload expired. Start it again.');
    await check(response, 'Uploading');
    throw new Error(`Unexpected answer from Drive (${response.status}).`);
  }
}
