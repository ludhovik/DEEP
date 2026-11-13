import { validCameraPose } from './view-workspace.js';
export const COMPARISON_CHANNEL = 'deepscope-comparison-v1';
const cameraSignature = pose => JSON.stringify(pose, (_, value) => typeof value === 'number' ? Math.round(value * 1e7) / 1e7 : value);

// Same-origin, explicitly known window peers only. Never accept arbitrary URLs
// or messages from other tabs/sites. Files/handles stay in the browser.
export function createComparisonBridge({captureCamera, applyCamera, captureDataset, applyDataset, ready, onError,
  captureView, applyView, captureFrame = () => null, applyFrame = async () => {}, captureColours = () => null, applyColours = async () => {}}) {
  const origin = window.location.origin, embedded = window.parent !== window;
  const opened = new Map();
  let lastCamera = cameraSignature(captureCamera()), applying = false, applyingView = false;
  let lastFrame = captureFrame(), lastColours = JSON.stringify(captureColours()), colourCandidate = lastColours, colourSince = 0;
  const pending = new Map();
  const send = (target, type, payload = {}) => target.postMessage({channel:COMPARISON_CHANNEL,type,...payload}, origin);
  window.addEventListener('message', async event => {
    if (event.origin !== origin || event.data?.channel !== COMPARISON_CHANNEL) return;
    const message = event.data;
    try {
      if (opened.has(event.source) && message.type === 'host-ready') {
        send(event.source, 'bootstrap', {bundle:opened.get(event.source)});
        opened.delete(event.source);
        return;
      }
      if (!embedded || event.source !== window.parent) return;
      if (message.type === 'hello') {
        send(window.parent, 'viewer-ready');
      } else if (message.type === 'camera' && validCameraPose(message.pose) && ready() && !applying && !applyingView) {
        applyCamera(message.pose);
        lastCamera = cameraSignature(captureCamera()); // suppress echo to peer
      } else if (message.type === 'request-camera' && ready()) {
        send(window.parent, 'camera', {pose:captureCamera()});
      } else if (message.type === 'request-frame' && ready()) {
        if (captureFrame() !== null) send(window.parent,'frame',{frame:captureFrame()});
      } else if (message.type === 'request-colours' && ready()) {
        send(window.parent,'colours',{colours:captureColours()});
      } else if (message.type === 'frame' && Number.isInteger(message.frame) && message.frame >= 0) {
        pending.set('frame',message.frame);
      } else if (message.type === 'colours' && message.colours && typeof message.colours === 'object') {
        pending.set('colours',message.colours);
      } else if (message.type === 'unlink') {
        pending.delete(message.kind);
      } else if (message.type === 'request-view') {
        if (!ready() || applying || applyingView) throw new Error('Wait for this pane to finish loading or restoring its view.');
        send(window.parent, 'view', {code:captureView(), request:message.request});
      } else if (message.type === 'load-view') {
        if (!ready() || applying || applyingView) throw new Error('Load a dataset in this pane and wait for loading or restoring to finish.');
        if (typeof message.code !== 'string' || message.code.length > 2_000_000) throw new Error('Invalid comparison view code.');
        // The workspace journal owns the view transaction and its undo/rollback.
        // Keep link events out, without blocking that journal's readiness check.
        applyingView = true;
        try {
          await applyView(message.code);
          lastCamera = cameraSignature(captureCamera());
          lastFrame = captureFrame(); lastColours = colourCandidate = JSON.stringify(captureColours());
          send(window.parent, 'view-applied');
        } finally { applyingView = false; }
      } else if (message.type === 'load-dataset') {
        if (applying || applyingView) throw new Error('This pane is already loading or restoring a comparison view.');
        applying = true;
        try {
          await applyDataset(message.bundle);
          lastCamera = cameraSignature(captureCamera());
          lastFrame = captureFrame(); lastColours = colourCandidate = JSON.stringify(captureColours());
          send(window.parent, 'loaded');
        } finally { applying = false; }
      }
    } catch(error) {
      const text = error?.message || String(error);
      onError(text);
      if (embedded && event.source === window.parent) send(window.parent, 'error', {message:text});
    }
  });
  if (embedded) {
    const timer = window.setInterval(async () => {
      if (!ready() || applying || applyingView) return;
      if (pending.size) {
        const [kind,value] = pending.entries().next().value; pending.delete(kind); applying = true;
        try {
          if (kind === 'frame') { await applyFrame(value); lastFrame = captureFrame(); }
          else { await applyColours(value); lastColours = colourCandidate = JSON.stringify(captureColours()); }
          lastCamera = cameraSignature(captureCamera());
        } catch(error) { onError(error.message); send(window.parent,'error',{message:error.message}); }
        finally { applying = false; }
        return;
      }
      const pose = captureCamera(), key = cameraSignature(pose);
      if (key !== lastCamera) { lastCamera = key; send(window.parent, 'camera', {pose}); }
      const frame = captureFrame();
      if (frame !== lastFrame) { lastFrame = frame; if (frame !== null) send(window.parent,'frame',{frame}); }
      const colours = captureColours(), colourKey = JSON.stringify(colours), now = Date.now();
      if (colourKey !== colourCandidate) { colourCandidate = colourKey; colourSince = now; }
      else if (colourKey !== lastColours && now - colourSince > 400) { lastColours = colourKey; send(window.parent,'colours',{colours}); }
    }, 80);
    window.addEventListener('pagehide', () => window.clearInterval(timer), {once:true});
    send(window.parent, 'viewer-ready');
  }
  return {
    get busy() { return applying; },
    open() {
      if (embedded) throw new Error('Use the comparison toolbar above these panes.');
      const bundle = captureDataset();
      const target = window.open(new URL('compare.html', window.location.href), '_blank');
      if (!target) throw new Error('Allow this site to open the comparison tab, then try again.');
      opened.set(target, bundle);
    },
  };
}
