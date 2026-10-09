// Tests for src/field-upload.js. Run with: npm test   (Node's built-in test runner; no network)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  CHUNK, FOLDER_NAME, MAX_BYTES, SignInError, clipName, contentRange, findOrCreateFolder,
  nextOffset, rejectReason, startSession, uploadFile,
} from '../src/field-upload.js';

const reply = (status, { headers = {}, json = {} } = {}) => ({
  status,
  ok: status >= 200 && status < 300,
  headers: { get: (name) => headers[name] ?? null },
  json: async () => json,
});
const video = (size, type = 'video/mp4', name = 'IMG_1.MOV') => ({
  size, type, name, slice: (start, end) => ({ start, end }),
});
const noWait = async () => {};

test('clip names are timestamped, safe, and use a known extension', () => {
  const when = new Date(2026, 9, 9, 14, 5, 7);
  assert.equal(clipName(video(1, 'video/mp4'), when), 'skynode-20261009-140507.mp4');
  assert.equal(clipName(video(1, 'video/quicktime'), when), 'skynode-20261009-140507.mov');
  assert.equal(clipName(video(1, 'video/webm;codecs=vp9'), when), 'skynode-20261009-140507.webm');
  assert.equal(clipName(video(1, '', 'clip.MKV'), when), 'skynode-20261009-140507.mkv');
  assert.equal(clipName(video(1, '', 'weird.exe'), when), 'skynode-20261009-140507.mp4');
  assert.equal(clipName(video(1, 'video/mp4'), when, 2), 'skynode-20261009-140507-2.mp4');
});

test('files we will not send are refused with a reason', () => {
  assert.equal(rejectReason(video(1000)), '');
  assert.match(rejectReason(video(0)), /empty/);
  assert.match(rejectReason(video(MAX_BYTES + 1)), /5 GB/);
  assert.match(rejectReason({ size: 10, type: 'image/png' }), /not a video/);
  assert.equal(rejectReason({ size: 10, type: '' }), ''); // some phones send no type
});

test('range helpers', () => {
  assert.equal(contentRange(0, 8, 20), 'bytes 0-7/20');
  assert.equal(nextOffset('bytes=0-7'), 8);
  assert.equal(nextOffset(null), 0);
  assert.equal(nextOffset('garbage'), 0);
  assert.equal(CHUNK % (256 * 1024), 0);
});

test('an existing upload folder is reused, not duplicated', async () => {
  const calls = [];
  const fetchFn = async (url, init = {}) => {
    calls.push({ url, method: init.method || 'GET' });
    return reply(200, { json: { files: [{ id: 'F1' }] } });
  };
  assert.equal(await findOrCreateFolder('tok', fetchFn), 'F1');
  assert.equal(calls.length, 1);
  assert.match(decodeURIComponent(calls[0].url), new RegExp(FOLDER_NAME));
});

test('the upload folder is created the first time', async () => {
  const seen = [];
  const fetchFn = async (url, init = {}) => {
    seen.push(init.method || 'GET');
    return init.method === 'POST' ? reply(200, { json: { id: 'NEW' } }) : reply(200, { json: { files: [] } });
  };
  assert.equal(await findOrCreateFolder('tok', fetchFn), 'NEW');
  assert.deepEqual(seen, ['GET', 'POST']);
});

test('an expired sign-in is reported as such', async () => {
  const fetchFn = async () => reply(401);
  await assert.rejects(findOrCreateFolder('old', fetchFn), SignInError);
});

test('a session needs an address from Drive', async () => {
  await assert.rejects(startSession('t', 'F', 'a.mp4', video(10), async () => reply(200)), /upload address/);
});

// A tiny fake of Drive's resumable upload endpoint.
function fakeDrive({ dropOnce = false, alwaysDrop = false, expired = false } = {}) {
  const state = { received: 0, puts: [], dropped: false };
  const fetchFn = async (url, init = {}) => {
    if (url.includes('uploadType=resumable')) {
      return reply(200, { headers: { Location: 'https://upload.example/session' } });
    }
    const range = init.headers['Content-Range'];
    state.puts.push(range);
    if (expired) return reply(404);
    if (range.startsWith('bytes */')) {
      return state.received > 0
        ? reply(308, { headers: { Range: `bytes=0-${state.received - 1}` } })
        : reply(308);
    }
    if (alwaysDrop || (dropOnce && !state.dropped && state.puts.length === 2)) {
      state.dropped = true;
      throw new TypeError('network down');
    }
    const [, from, to, total] = /bytes (\d+)-(\d+)\/(\d+)/.exec(range).map(Number);
    assert.equal(from, state.received, 'chunks must arrive in order, with no gaps');
    state.received = to + 1;
    return state.received === total
      ? reply(200, { json: { id: 'FILE1' } })
      : reply(308, { headers: { Range: `bytes=0-${to}` } });
  };
  return { fetchFn, state };
}

test('a clip is sent in chunks and reports progress', async () => {
  const { fetchFn, state } = fakeDrive();
  const progress = [];
  const id = await uploadFile({
    token: 't', folderId: 'F', file: video(20), name: 'a.mp4', fetchFn, chunk: 8, wait: noWait,
    onProgress: (sent, total) => progress.push([sent, total]),
  });
  assert.equal(id, 'FILE1');
  assert.deepEqual(state.puts, ['bytes 0-7/20', 'bytes 8-15/20', 'bytes 16-19/20']);
  assert.deepEqual(progress, [[8, 20], [16, 20], [20, 20]]);
});

test('a dropped connection resumes where Drive got to, without resending', async () => {
  const { fetchFn, state } = fakeDrive({ dropOnce: true });
  const id = await uploadFile({
    token: 't', folderId: 'F', file: video(20), name: 'a.mp4', fetchFn, chunk: 8, wait: noWait,
  });
  assert.equal(id, 'FILE1');
  assert.equal(state.received, 20);
  assert.ok(state.puts.includes('bytes */20'), 'asked Drive how much arrived');
});

test('it gives up after too many failures in a row', async () => {
  const { fetchFn } = fakeDrive({ alwaysDrop: true });
  await assert.rejects(
    uploadFile({ token: 't', folderId: 'F', file: video(20), name: 'a.mp4', fetchFn, chunk: 8, retries: 2, wait: noWait }),
    /kept dropping/,
  );
});

test('an expired upload session is a clear error', async () => {
  const { fetchFn } = fakeDrive({ expired: true });
  await assert.rejects(
    uploadFile({ token: 't', folderId: 'F', file: video(20), name: 'a.mp4', fetchFn, chunk: 8, wait: noWait }),
    /expired/,
  );
});
