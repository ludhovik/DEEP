export function createWorkProgress({ panel, label, bar, cancel }) {
  const jobs = new Set();
  function draw() {
    panel.hidden = jobs.size === 0;
    const job = [...jobs].at(-1);
    if (!job) return;
    label.textContent = job.label;
    if (Number.isFinite(job.fraction)) bar.value = Math.max(0, Math.min(1, job.fraction));
    else bar.removeAttribute("value");
  }
  cancel.addEventListener("click", () => {
    for (const job of [...jobs]) job.onCancel();
  });
  return {
    begin(text, onCancel) {
      const job = { label: text, onCancel };
      jobs.add(job); draw();
      return {
        update({ label: text, fraction } = {}) {
          if (!jobs.has(job)) return;
          if (text) job.label = text;
          job.fraction = fraction;
          draw();
        },
        finish() { jobs.delete(job); draw(); },
      };
    },
  };
}

export async function readResponseWithProgress(response, method, { signal, onProgress = () => {} } = {}) {
  signal?.throwIfAborted();
  if (!response.body?.getReader) {
    const result = await response[method]();
    signal?.throwIfAborted();
    return result;
  }
  const reader = response.body.getReader();
  const chunks = [];
  let received = 0, lastReport = 0;
  // Content-Length can describe compressed bytes; do not display a false %.
  const advertised = response.headers.get("Content-Encoding") ? 0 : Number(response.headers.get("Content-Length"));
  const total = Number.isSafeInteger(advertised) && advertised > 0 ? advertised : null;
  const abort = () => { void reader.cancel(signal.reason).catch(() => {}); };
  signal?.addEventListener("abort", abort, { once: true });
  try {
    while (true) {
      signal?.throwIfAborted();
      const { done, value } = await reader.read();
      signal?.throwIfAborted();
      if (done) break;
      chunks.push(value); received += value.byteLength;
      const now = performance.now();
      if (now - lastReport > 100) {
        onProgress({ received, total: received <= total ? total : null }); lastReport = now;
      }
    }
    const buffer = new Uint8Array(received);
    let at = 0;
    for (const chunk of chunks) { buffer.set(chunk, at); at += chunk.byteLength; }
    onProgress({ received, total: received });
    signal?.throwIfAborted();
    if (method === "arrayBuffer") return buffer.buffer;
    const text = new TextDecoder().decode(buffer);
    if (method === "text") return text;
    if (method === "json") return JSON.parse(text);
    throw new Error(`Unsupported dataset response method: ${method}`);
  } finally {
    signal?.removeEventListener("abort", abort);
    reader.releaseLock();
  }
}
