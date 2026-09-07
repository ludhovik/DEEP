import { executeGeometryJob, geometryTransferList } from "./geometry-jobs.js";

self.onmessage = ({ data: { id, type, payload } }) => {
  let lastProgress = 0;
  try {
    const result = executeGeometryJob(type, payload, progress => {
      const now = performance.now();
      if (now - lastProgress < 100 && progress.fraction !== 1) return;
      lastProgress = now;
      self.postMessage({ id, progress });
    });
    self.postMessage({ id, result }, geometryTransferList(result));
  } catch (error) {
    self.postMessage({ id, error: { name: error.name, message: error.message } });
  }
};
