/* ── Goggins API client ──────────────────────────────────────────────── */
const API = (() => {
  const BASE = '/api/v1';

  function showToast(msg, isError = false) {
    const old = document.querySelector('.toast');
    if (old) old.remove();
    const t = document.createElement('div');
    t.className = 'toast' + (isError ? ' error' : '');
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }

  async function request(method, path, body) {
    const opts = {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    };
    const res = await fetch(`${BASE}${path}`, opts);
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try { detail = (await res.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }
    return res.json();
  }

  /**
   * Stream a POST via Server-Sent Events (fetch + ReadableStream).
   * Reliable on iOS Safari (avoids EventSource quirks).
   *
   * @param {string}   path
   * @param {object|null} body
   * @param {(text:string)=>void}  onChunk  – called for every text chunk
   * @param {(data:object)=>void}  onDone   – called with the final {type:'done',...} payload
   * @param {(err:Error)=>void}    onError  – called on error
   */
  async function stream(path, body, onChunk, onDone, onError) {
    let res;
    try {
      res = await fetch(`${BASE}${path}`, {
        method: 'POST',
        headers: body ? { 'Content-Type': 'application/json' } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try { detail = (await res.json()).detail || detail; } catch (_) {}
        onError?.(new Error(detail));
        return;
      }
    } catch (err) {
      onError?.(err);
      return;
    }

    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '';

    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split('\n\n');
        buf = parts.pop() ?? '';
        for (const part of parts) {
          if (!part.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(part.slice(6));
            if (data.type === 'chunk') onChunk?.(data.text);
            else if (data.type === 'done')  onDone?.(data);
            else if (data.type === 'error') onError?.(new Error(data.message));
          } catch (e) {
            console.warn('SSE parse error', e, part);
          }
        }
      }
    } catch (err) {
      onError?.(err);
    }
  }

  return {
    get:   (path) => request('GET', path),
    post:  (path, body) => request('POST', path, body),
    put:   (path, body) => request('PUT', path, body),
    stream,
    showToast,
  };
})();
