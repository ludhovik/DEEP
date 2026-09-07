// One compute worker bounds concurrent allocations. Termination interrupts even
// a synchronous geometry loop; a later request starts a fresh worker.
export class GeometryClient {
  constructor(createWorker = () => new Worker(new URL("./geometry-worker.js", import.meta.url), { type: "module" })) {
    this.createWorker = createWorker;
    this.queue = [];
    this.active = null;
    this.serial = 0;
    this.worker = null;
  }
  run(type, payload, { signal, onProgress = () => {} } = {}) {
    return new Promise((resolve, reject) => {
      if (signal?.aborted) { reject(signal.reason); return; }
      const job = { id: ++this.serial, type, payload, resolve, reject, signal, onProgress };
      job.abort = () => {
        if (this.active === job) {
          this.worker?.terminate(); this.worker = null;
          this.finish(job, signal.reason || new DOMException("Cancelled", "AbortError"));
        } else {
          this.queue = this.queue.filter(item => item !== job);
          signal.removeEventListener("abort", job.abort);
          reject(signal.reason || new DOMException("Cancelled", "AbortError"));
        }
      };
      signal?.addEventListener("abort", job.abort, { once: true });
      this.queue.push(job);
      this.next();
    });
  }
  next() {
    if (this.active || !this.queue.length) return;
    const job = this.active = this.queue.shift();
    try {
      if (!this.worker) {
        const worker = this.worker = this.createWorker();
        worker.onmessage = ({ data }) => {
          if (this.worker !== worker || this.active?.id !== data.id) return;
          if (data.progress) { this.active.onProgress(data.progress); return; }
          const error = data.error ? Object.assign(new Error(data.error.message), { name: data.error.name }) : null;
          this.finish(this.active, error, data.result);
        };
        worker.onerror = event => {
          event.preventDefault?.();
          if (this.worker !== worker) return;
          worker.terminate(); this.worker = null;
          this.finish(this.active, new Error(event.message || "Geometry worker failed. Retry the operation."));
        };
        worker.onmessageerror = () => {
          if (this.worker !== worker) return;
          worker.terminate(); this.worker = null;
          this.finish(this.active, new Error("Could not receive geometry from the worker. Retry with less detail."));
        };
      }
      // Cached source buffers must remain owned by the viewer. Only result
      // buffers are transferred back from the worker without a second copy.
      this.worker.postMessage({ id: job.id, type: job.type, payload: job.payload });
      job.payload = null;
    } catch (error) {
      this.worker?.terminate(); this.worker = null;
      this.finish(job, new Error(`Could not start geometry work: ${error.message}`));
    }
  }
  finish(job, error, result) {
    if (!job) return;
    job.signal?.removeEventListener("abort", job.abort);
    this.active = null;
    if (error) job.reject(error); else job.resolve(result);
    this.next();
  }
  cancelAll() {
    const jobs = [...this.queue, ...(this.active ? [this.active] : [])];
    this.queue = []; this.active = null;
    this.worker?.terminate(); this.worker = null;
    for (const job of jobs) {
      job.signal?.removeEventListener("abort", job.abort);
      job.reject(new DOMException("Geometry calculation cancelled", "AbortError"));
    }
  }
}
