const crypto = require('crypto');
const fs = require('fs');
const fsp = require('fs/promises');
const path = require('path');
const express = require('express');
const multer = require('multer');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');

const PORT = Number(process.env.PORT || 3000);
const STORAGE_DIR = process.env.STORAGE_DIR || path.join(__dirname, 'data');
const PUBLIC_BASE_URL = (process.env.PUBLIC_BASE_URL || '').replace(/\/$/, '');
const PUBLISH_TOKEN = process.env.PUBLISH_TOKEN || '';
const MAX_UPLOAD_MB = Number(process.env.MAX_UPLOAD_MB || 2000);
const DEFAULT_CHANNEL = 'stable';
const VERSION_RE = /^[0-9A-Za-z][0-9A-Za-z._-]{0,63}$/;
const CHANNEL_RE = /^[0-9A-Za-z][0-9A-Za-z._-]{0,31}$/;
const JWT_SECRET = process.env.JWT_SECRET || '';
const JWT_DAYS = 30;
const USERNAME_RE = /^[a-zA-Z0-9_-]{3,20}$/;
const USERS_PATH = path.join(STORAGE_DIR, 'users', 'users.json');

const app = express();
app.disable('x-powered-by');
app.use(express.json({ limit: '2mb' }));

const tmpDir = path.join(STORAGE_DIR, 'tmp');
const upload = multer({
  dest: tmpDir,
  limits: { fileSize: MAX_UPLOAD_MB * 1024 * 1024, files: 1 },
});

const uploadSessions = new Map();

function cleanupSession(sess) {
  if (!sess) return;
  sess.tmpFiles.forEach(f => { if (f) fsp.unlink(f).catch(() => {}); });
}

function safeName(value, fallback, re) {
  const s = String(value || fallback || '').trim();
  if (!re.test(s)) {
    throw new Error(`Invalid value: ${s}`);
  }
  return s;
}

function storagePaths(channel) {
  const base = path.join(STORAGE_DIR, 'releases', channel);
  return {
    base,
    index: path.join(base, 'index.json'),
  };
}

function publicBase(req) {
  if (PUBLIC_BASE_URL) return PUBLIC_BASE_URL;
  return `${req.protocol}://${req.get('host')}`;
}

async function ensureStorage(channel = DEFAULT_CHANNEL) {
  await fsp.mkdir(tmpDir, { recursive: true });
  const sp = storagePaths(channel);
  await fsp.mkdir(sp.base, { recursive: true });
  if (!fs.existsSync(sp.index)) {
    await fsp.writeFile(sp.index, JSON.stringify({ latest: null, releases: [] }, null, 2), 'utf8');
  }
}

async function readIndex(channel) {
  await ensureStorage(channel);
  const sp = storagePaths(channel);
  try {
    const data = JSON.parse(await fsp.readFile(sp.index, 'utf8'));
    if (data && Array.isArray(data.releases)) return data;
  } catch (_) {}
  return { latest: null, releases: [] };
}

async function writeIndex(channel, data) {
  const sp = storagePaths(channel);
  await fsp.writeFile(sp.index, JSON.stringify(data, null, 2), 'utf8');
}

function requirePublisher(req, res, next) {
  if (!PUBLISH_TOKEN) {
    return res.status(503).json({ ok: false, error: 'PUBLISH_TOKEN is not configured' });
  }
  const header = Buffer.from(String(req.get('authorization') || ''));
  const expected = Buffer.from(`Bearer ${PUBLISH_TOKEN}`);
  const authorized = header.length === expected.length && crypto.timingSafeEqual(header, expected);
  if (!authorized) {
    return res.status(401).json({ ok: false, error: 'Unauthorized' });
  }
  return next();
}

async function sha256File(filePath) {
  return new Promise((resolve, reject) => {
    const h = crypto.createHash('sha256');
    const s = fs.createReadStream(filePath);
    s.on('data', chunk => h.update(chunk));
    s.on('error', reject);
    s.on('end', () => resolve(h.digest('hex')));
  });
}

function manifestForRelease(req, release) {
  const base = publicBase(req);
  const manifest = {
    latest_version: release.version,
    package_url: `${base}/downloads/${encodeURIComponent(release.channel)}/${encodeURIComponent(release.filename)}`,
    sha256: release.sha256,
    notes: release.notes || '',
    channel: release.channel,
    size: release.size,
    created_at: release.created_at,
  };
  if (release.installer_filename) {
    manifest.installer_url = `${base}/downloads/${encodeURIComponent(release.channel)}/${encodeURIComponent(release.installer_filename)}`;
    manifest.installer_sha256 = release.installer_sha256 || '';
  }
  if (release.launcher_filename) {
    manifest.launcher_url = `${base}/downloads/${encodeURIComponent(release.channel)}/${encodeURIComponent(release.launcher_filename)}`;
    manifest.launcher_sha256 = release.launcher_sha256 || '';
  }
  return manifest;
}

app.get('/health', async (_req, res) => {
  try {
    await ensureStorage(DEFAULT_CHANNEL);
    res.json({ ok: true, storage_dir: STORAGE_DIR });
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err.message || err) });
  }
});

app.get('/manifest.json', async (req, res) => {
  req.params.channel = DEFAULT_CHANNEL;
  return manifestHandler(req, res);
});

app.get('/api/manifest/:channel', manifestHandler);

async function manifestHandler(req, res) {
  try {
    const channel = safeName(req.params.channel, DEFAULT_CHANNEL, CHANNEL_RE);
    const index = await readIndex(channel);
    const latestVersion = index.latest;
    if (!latestVersion) {
      return res.status(404).json({ ok: false, error: 'No release published for this channel' });
    }
    const release = index.releases.find(r => r.version === latestVersion) || index.releases[index.releases.length - 1];
    return res.json(manifestForRelease(req, release));
  } catch (err) {
    return res.status(400).json({ ok: false, error: String(err.message || err) });
  }
}

app.get('/api/releases/:channel', async (req, res) => {
  try {
    const channel = safeName(req.params.channel, DEFAULT_CHANNEL, CHANNEL_RE);
    const index = await readIndex(channel);
    res.json(index);
  } catch (err) {
    res.status(400).json({ ok: false, error: String(err.message || err) });
  }
});

app.get('/downloads/:channel/:filename', async (req, res) => {
  try {
    const channel = safeName(req.params.channel, DEFAULT_CHANNEL, CHANNEL_RE);
    const filename = path.basename(String(req.params.filename || ''));
    const isZip = filename.endsWith('.zip');
    const isExe = filename.endsWith('.exe');
    if (!isZip && !isExe) throw new Error('Invalid filename — only .zip and .exe allowed');
    const file = path.join(storagePaths(channel).base, filename);
    if (!fs.existsSync(file)) return res.status(404).json({ ok: false, error: 'File not found' });
    const contentType = isExe ? 'application/octet-stream' : 'application/zip';
    res.setHeader('Content-Type', contentType);
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    return res.sendFile(file);
  } catch (err) {
    return res.status(400).json({ ok: false, error: String(err.message || err) });
  }
});

app.post('/api/releases', requirePublisher, upload.single('package'), async (req, res) => {
  let uploaded = req.file ? req.file.path : null;
  try {
    if (!req.file) throw new Error('Missing package file');
    const version = safeName(req.body.version, '', VERSION_RE);
    const channel = safeName(req.body.channel, DEFAULT_CHANNEL, CHANNEL_RE);
    const notes = String(req.body.notes || '');
    const expectedSha = String(req.body.sha256 || '').trim().toLowerCase();
    const actualSha = await sha256File(req.file.path);
    if (expectedSha && actualSha !== expectedSha) {
      throw new Error(`SHA256 mismatch: expected ${expectedSha}, got ${actualSha}`);
    }
    await ensureStorage(channel);
    const filename = `HackerOS-${version}.zip`;
    const target = path.join(storagePaths(channel).base, filename);
    await fsp.rename(req.file.path, target);
    uploaded = null;
    // Preserve existing installer_filename if not re-uploading installer
    const existingIndex = await readIndex(channel);
    const existingRelease = existingIndex.releases.find(r => r.version === version) || {};
    const release = {
      version,
      channel,
      filename,
      sha256: actualSha,
      size: Number(req.file.size || req.body.size || 0),
      notes,
      created_at: new Date().toISOString(),
      installer_filename: existingRelease.installer_filename || null,
      installer_sha256: existingRelease.installer_sha256 || null,
    };
    existingIndex.releases = existingIndex.releases.filter(r => r.version !== version);
    existingIndex.releases.push(release);
    existingIndex.latest = version;
    await writeIndex(channel, existingIndex);
    return res.json({ ok: true, release, manifest: manifestForRelease(req, release) });
  } catch (err) {
    if (uploaded) {
      try { await fsp.unlink(uploaded); } catch (_) {}
    }
    return res.status(400).json({ ok: false, error: String(err.message || err) });
  }
});

app.post('/api/installer', requirePublisher, upload.single('installer'), async (req, res) => {
  let uploaded = req.file ? req.file.path : null;
  try {
    if (!req.file) throw new Error('Missing installer file');
    const version = safeName(req.body.version, '', VERSION_RE);
    const channel = safeName(req.body.channel, DEFAULT_CHANNEL, CHANNEL_RE);
    const expectedSha = String(req.body.sha256 || '').trim().toLowerCase();
    const actualSha = await sha256File(req.file.path);
    if (expectedSha && actualSha !== expectedSha) {
      throw new Error(`SHA256 mismatch: expected ${expectedSha}, got ${actualSha}`);
    }
    await ensureStorage(channel);
    const filename = `HackerOS-Setup-${version}.exe`;
    const target = path.join(storagePaths(channel).base, filename);
    await fsp.rename(req.file.path, target);
    uploaded = null;
    // Attach installer info to the matching release
    const index = await readIndex(channel);
    const release = index.releases.find(r => r.version === version);
    if (!release) {
      throw new Error(`Release ${version} introuvable sur le channel ${channel}. Publiez d'abord le package ZIP.`);
    }
    release.installer_filename = filename;
    release.installer_sha256 = actualSha;
    await writeIndex(channel, index);
    return res.json({
      ok: true,
      installer_url: `${publicBase(req)}/downloads/${encodeURIComponent(channel)}/${encodeURIComponent(filename)}`,
      installer_sha256: actualSha,
      manifest: manifestForRelease(req, release),
    });
  } catch (err) {
    if (uploaded) {
      try { await fsp.unlink(uploaded); } catch (_) {}
    }
    return res.status(400).json({ ok: false, error: String(err.message || err) });
  }
});

app.post('/api/launcher', requirePublisher, upload.single('launcher'), async (req, res) => {
  let uploaded = req.file ? req.file.path : null;
  try {
    if (!req.file) throw new Error('Missing launcher file');
    const version = safeName(req.body.version, '', VERSION_RE);
    const channel = safeName(req.body.channel, DEFAULT_CHANNEL, CHANNEL_RE);
    const expectedSha = String(req.body.sha256 || '').trim().toLowerCase();
    const actualSha = await sha256File(req.file.path);
    if (expectedSha && actualSha !== expectedSha) {
      throw new Error(`SHA256 mismatch: expected ${expectedSha}, got ${actualSha}`);
    }
    await ensureStorage(channel);
    const filename = 'HackerOS-Launcher.exe';
    const target = path.join(storagePaths(channel).base, filename);
    await fsp.rename(req.file.path, target);
    uploaded = null;
    const index = await readIndex(channel);
    const release = index.releases.find(r => r.version === version);
    if (release) {
      release.launcher_filename = filename;
      release.launcher_sha256 = actualSha;
      await writeIndex(channel, index);
    }
    const launcher_url = `${publicBase(req)}/downloads/${encodeURIComponent(channel)}/${encodeURIComponent(filename)}`;
    return res.json({ ok: true, filename, sha256: actualSha, launcher_url });
  } catch (err) {
    if (uploaded) { try { await fsp.unlink(uploaded); } catch (_) {} }
    return res.status(400).json({ ok: false, error: String(err.message || err) });
  }
});

app.post('/api/releases/upload/start', requirePublisher, async (req, res) => {
  try {
    const version = safeName(req.body.version, '', VERSION_RE);
    const channel = safeName(req.body.channel, DEFAULT_CHANNEL, CHANNEL_RE);
    const notes = String(req.body.notes || '');
    const sha256 = String(req.body.sha256 || '').trim().toLowerCase();
    const totalChunks = parseInt(String(req.body.total_chunks || '1'), 10);
    const size = Number(req.body.size || 0);
    const packageMode = String(req.body.package_mode || '');
    if (isNaN(totalChunks) || totalChunks < 1 || totalChunks > 200) throw new Error('Invalid total_chunks');
    const maxBytes = MAX_UPLOAD_MB * 1024 * 1024;
    if (size && size > maxBytes) throw new Error(`Declared size exceeds MAX_UPLOAD_MB (${MAX_UPLOAD_MB} MB)`);
    const uploadId = crypto.randomBytes(16).toString('hex');
    const sess = {
      channel, version, notes, sha256, totalChunks, size, packageMode,
      receivedChunks: new Set(),
      tmpFiles: new Array(totalChunks).fill(null),
      bytesReceived: 0,
    };
    uploadSessions.set(uploadId, sess);
    setTimeout(() => { cleanupSession(uploadSessions.get(uploadId)); uploadSessions.delete(uploadId); }, 2 * 60 * 60 * 1000);
    return res.json({ ok: true, upload_id: uploadId, total_chunks: totalChunks });
  } catch (err) {
    return res.status(400).json({ ok: false, error: String(err.message || err) });
  }
});

app.post('/api/releases/upload/chunk', requirePublisher, express.raw({ type: 'application/octet-stream', limit: '60mb' }), async (req, res) => {
  const uploadId = String(req.headers['x-upload-id'] || '');
  const chunkIndex = parseInt(String(req.headers['x-chunk-index'] || '0'), 10);
  const sess = uploadSessions.get(uploadId);
  if (!sess) return res.status(400).json({ ok: false, error: 'Unknown upload_id' });
  if (isNaN(chunkIndex) || chunkIndex < 0 || chunkIndex >= sess.totalChunks) {
    return res.status(400).json({ ok: false, error: 'Invalid chunk_index' });
  }
  const chunkData = req.body;
  if (!Buffer.isBuffer(chunkData) || chunkData.length === 0) {
    return res.status(400).json({ ok: false, error: 'Empty chunk body' });
  }
  const maxBytes = MAX_UPLOAD_MB * 1024 * 1024;
  if (sess.bytesReceived + chunkData.length > maxBytes) {
    cleanupSession(sess);
    uploadSessions.delete(uploadId);
    return res.status(413).json({ ok: false, error: `Upload exceeds MAX_UPLOAD_MB (${MAX_UPLOAD_MB} MB)` });
  }
  const tmpFile = path.join(tmpDir, `upload_${uploadId}_${chunkIndex}`);
  try {
    await fsp.mkdir(tmpDir, { recursive: true });
    await fsp.writeFile(tmpFile, chunkData);
    if (sess.tmpFiles[chunkIndex] && sess.tmpFiles[chunkIndex] !== tmpFile) {
      await fsp.unlink(sess.tmpFiles[chunkIndex]).catch(() => {});
    }
    sess.tmpFiles[chunkIndex] = tmpFile;
    sess.receivedChunks.add(chunkIndex);
    sess.bytesReceived += chunkData.length;
    return res.json({ ok: true, chunk_index: chunkIndex, received: sess.receivedChunks.size, total: sess.totalChunks });
  } catch (err) {
    await fsp.unlink(tmpFile).catch(() => {});
    return res.status(500).json({ ok: false, error: String(err.message || err) });
  }
});

app.post('/api/releases/upload/finalize', requirePublisher, async (req, res) => {
  const uploadId = String(req.body.upload_id || '');
  const sess = uploadSessions.get(uploadId);
  if (!sess) return res.status(400).json({ ok: false, error: 'Unknown upload_id' });
  uploadSessions.delete(uploadId);
  try {
    if (sess.receivedChunks.size !== sess.totalChunks) {
      throw new Error(`Missing chunks: got ${sess.receivedChunks.size}/${sess.totalChunks}`);
    }
    await ensureStorage(sess.channel);
    const filename = `HackerOS-${sess.version}.zip`;
    const target = path.join(storagePaths(sess.channel).base, filename);
    const writeStream = fs.createWriteStream(target);
    for (let i = 0; i < sess.totalChunks; i++) {
      await new Promise((resolve, reject) => {
        const rs = fs.createReadStream(sess.tmpFiles[i]);
        rs.on('error', reject);
        rs.on('end', resolve);
        rs.pipe(writeStream, { end: false });
      });
    }
    await new Promise((resolve, reject) => {
      writeStream.end();
      writeStream.on('finish', resolve);
      writeStream.on('error', reject);
    });
    cleanupSession(sess);
    const actualSha = await sha256File(target);
    if (sess.sha256 && actualSha !== sess.sha256) {
      await fsp.unlink(target).catch(() => {});
      throw new Error(`SHA256 mismatch: expected ${sess.sha256}, got ${actualSha}`);
    }
    const existingIndex = await readIndex(sess.channel);
    const existingRelease = existingIndex.releases.find(r => r.version === sess.version) || {};
    const release = {
      version: sess.version,
      channel: sess.channel,
      filename,
      sha256: actualSha,
      size: sess.size || (await fsp.stat(target)).size,
      notes: sess.notes,
      created_at: new Date().toISOString(),
      installer_filename: existingRelease.installer_filename || null,
      installer_sha256: existingRelease.installer_sha256 || null,
    };
    if (sess.packageMode) release.package_mode = sess.packageMode;
    existingIndex.releases = existingIndex.releases.filter(r => r.version !== sess.version);
    existingIndex.releases.push(release);
    existingIndex.latest = sess.version;
    await writeIndex(sess.channel, existingIndex);
    return res.json({ ok: true, release, manifest: manifestForRelease(req, release) });
  } catch (err) {
    cleanupSession(sess);
    return res.status(400).json({ ok: false, error: String(err.message || err) });
  }
});

// ── Auth helpers ────────────────────────────────────────────────────────────

async function readUsers() {
  try {
    await fsp.mkdir(path.dirname(USERS_PATH), { recursive: true });
    if (!fs.existsSync(USERS_PATH)) {
      await fsp.writeFile(USERS_PATH, JSON.stringify({ users: [] }, null, 2), 'utf8');
    }
    const data = JSON.parse(await fsp.readFile(USERS_PATH, 'utf8'));
    return Array.isArray(data.users) ? data.users : [];
  } catch (_) {
    return [];
  }
}

async function writeUsers(users) {
  await fsp.mkdir(path.dirname(USERS_PATH), { recursive: true });
  await fsp.writeFile(USERS_PATH, JSON.stringify({ users }, null, 2), 'utf8');
}

function signToken(user_id, username) {
  const exp = Math.floor(Date.now() / 1000) + JWT_DAYS * 24 * 3600;
  const token = jwt.sign({ user_id, username }, JWT_SECRET, { expiresIn: `${JWT_DAYS}d` });
  const expires_at = new Date(exp * 1000).toISOString();
  return { token, expires_at };
}

function requireJwt(req, res, next) {
  if (!JWT_SECRET) return res.status(503).json({ ok: false, error: 'Auth not configured (JWT_SECRET missing)' });
  const header = String(req.get('authorization') || '');
  if (!header.startsWith('Bearer ')) return res.status(401).json({ ok: false, error: 'Missing token' });
  try {
    req.jwtPayload = jwt.verify(header.slice(7), JWT_SECRET);
    return next();
  } catch (e) {
    return res.status(401).json({ ok: false, error: 'Invalid or expired token' });
  }
}

// ── Auth routes ──────────────────────────────────────────────────────────────

app.post('/api/auth/register', async (req, res) => {
  if (!JWT_SECRET) return res.status(503).json({ ok: false, error: 'Auth not configured (JWT_SECRET missing)' });
  try {
    const username = String(req.body.username || '').trim();
    const password = String(req.body.password || '');
    if (!USERNAME_RE.test(username)) {
      return res.status(400).json({ ok: false, error: 'Pseudo invalide (3-20 chars, lettres/chiffres/_-)' });
    }
    if (password.length < 8) {
      return res.status(400).json({ ok: false, error: 'Mot de passe trop court (min 8 caractères)' });
    }
    const users = await readUsers();
    if (users.find(u => u.username.toLowerCase() === username.toLowerCase())) {
      return res.status(409).json({ ok: false, error: 'Ce pseudo est déjà pris' });
    }
    const user_id = crypto.randomBytes(12).toString('hex');
    const password_hash = await bcrypt.hash(password, 10);
    users.push({ user_id, username, password_hash, created_at: new Date().toISOString() });
    await writeUsers(users);
    const { token, expires_at } = signToken(user_id, username);
    return res.json({ ok: true, token, user_id, username, expires_at });
  } catch (err) {
    return res.status(500).json({ ok: false, error: String(err.message || err) });
  }
});

app.post('/api/auth/login', async (req, res) => {
  if (!JWT_SECRET) return res.status(503).json({ ok: false, error: 'Auth not configured (JWT_SECRET missing)' });
  try {
    const username = String(req.body.username || '').trim();
    const password = String(req.body.password || '');
    if (!username || !password) {
      return res.status(400).json({ ok: false, error: 'Pseudo et mot de passe requis' });
    }
    const users = await readUsers();
    const user = users.find(u => u.username.toLowerCase() === username.toLowerCase());
    if (!user) return res.status(401).json({ ok: false, error: 'Pseudo ou mot de passe incorrect' });
    const ok = await bcrypt.compare(password, user.password_hash);
    if (!ok) return res.status(401).json({ ok: false, error: 'Pseudo ou mot de passe incorrect' });
    const { token, expires_at } = signToken(user.user_id, user.username);
    return res.json({ ok: true, token, user_id: user.user_id, username: user.username, expires_at });
  } catch (err) {
    return res.status(500).json({ ok: false, error: String(err.message || err) });
  }
});

app.get('/api/auth/verify', requireJwt, (req, res) => {
  const { user_id, username } = req.jwtPayload;
  return res.json({ ok: true, user_id, username });
});

// ── Error handler ────────────────────────────────────────────────────────────

app.use((err, _req, res, _next) => {
  res.status(500).json({ ok: false, error: String(err.message || err) });
});

if (require.main === module) {
  ensureStorage(DEFAULT_CHANNEL)
    .then(() => app.listen(PORT, () => console.log(`HackerOS update server listening on ${PORT}`)))
    .catch(err => {
      console.error(err);
      process.exit(1);
    });
}

module.exports = { app, safeName, manifestForRelease, storagePaths };
