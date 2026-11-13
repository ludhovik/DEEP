import { COMPARISON_CHANNEL } from './comparison-bridge.js';
import { validCameraPose } from './view-workspace.js';

export function mountComparison(document, window) {
  const frames = [...document.querySelectorAll('iframe')], ready = [false,false], queue = [null,null];
  const origin = window.location.origin, status = document.querySelector('#comparison-status');
  const link = document.querySelector('#link-cameras');
  const frameLink = document.querySelector('#link-frames'), colourLink = document.querySelector('#link-colours');
  let nextRequest = 0;
  const requests = new Map();
  const notice = (text, error = false) => { status.textContent = text; status.classList.toggle('error', error); };
  const send = (index, type, payload = {}) => frames[index].contentWindow.postMessage({channel:COMPARISON_CHANNEL,type,...payload}, origin);
  const load = (index, bundle) => {
    if (!ready[index]) { queue[index] = bundle; return; }
    try { send(index, 'load-dataset', {bundle}); notice(`Loading view ${index ? 'B' : 'A'}…`); }
    catch(error) { notice(`Could not copy local folder access: ${error.message}. Open the folder directly in the destination pane.`, true); }
  };
  window.addEventListener('message', event => {
    if (event.origin !== origin || event.data?.channel !== COMPARISON_CHANNEL) return;
    const data = event.data, index = frames.findIndex(frame => frame.contentWindow === event.source);
    if (index < 0) {
      if (event.source === window.opener && data.type === 'bootstrap') load(0, data.bundle);
      return;
    }
    if (data.type === 'viewer-ready') {
      ready[index] = true;
      if (queue[index]) { const bundle = queue[index]; queue[index] = null; load(index,bundle); }
      else notice('Choose datasets in the panes. Each pane has its own Views & comparison controls.');
    } else if (data.type === 'camera' && validCameraPose(data.pose) && link.checked && ready[1-index]) {
      send(1-index, 'camera', {pose:data.pose});
    } else if (data.type === 'frame' && frameLink.checked && ready[1-index] && Number.isInteger(data.frame) && data.frame >= 0) {
      send(1-index,'frame',{frame:data.frame});
    } else if (data.type === 'colours' && colourLink.checked && ready[1-index] && data.colours && typeof data.colours === 'object') {
      send(1-index,'colours',{colours:data.colours});
    } else if (data.type === 'view' && requests.get(data.request)?.from === index) {
      const request = requests.get(data.request); requests.delete(data.request);
      if (typeof data.code !== 'string' || data.code.length > 2_000_000) { notice('Invalid comparison view code.',true); return; }
      send(request.to, 'load-view', {code:data.code});
      notice(`Applying view code to ${request.to ? 'B' : 'A'}…`);
    } else if (data.type === 'error') {
      notice(`View ${index ? 'B' : 'A'}: ${String(data.message).slice(0,2000)}`, true);
    } else if (data.type === 'view-applied') {
      notice(`View code applied to ${index ? 'B' : 'A'}. Fields and colour settings copied; its datasets, frame and radius mapping are unchanged.`);
    } else if (data.type === 'loaded') {
      notice(`View ${index ? 'B' : 'A'} loaded. Fields and grids remain independent.`);
      if (link.checked) send(0, 'request-camera');
    }
  });
  for (const [id,from,to] of [['copy-a',0,1],['copy-b',1,0]]) document.getElementById(id).addEventListener('click', () => {
    if (!ready[from] || !ready[to]) { notice('Wait for both viewers to finish starting.',true); return; }
    const request = ++nextRequest; requests.set(request,{from,to});
    send(from,'request-view',{request});
  });
  const align = () => { if (ready[0] && ready[1]) { link.checked = true; send(0,'request-camera'); } };
  document.getElementById('align-a').addEventListener('click',align);
  link.addEventListener('change', () => { if (link.checked) align(); });
  for (const [checkbox,kind] of [[frameLink,'frame'],[colourLink,'colours']]) checkbox.addEventListener('change', () => {
    if (checkbox.checked && ready[0] && ready[1]) send(0,`request-${kind}`);
    else for (let i=0;i<2;i++) if (ready[i]) send(i,'unlink',{kind});
  });
  document.getElementById('comparison-layout').addEventListener('change', event => {
    document.getElementById('comparison-panes').classList.toggle('rows', event.target.value === 'rows');
  });
  // Cover both cold loads and a cached child that became ready before the host.
  frames.forEach((frame,index) => {
    frame.addEventListener('load', () => send(index,'hello'));
    send(index,'hello');
  });
  if (window.opener) window.opener.postMessage({channel:COMPARISON_CHANNEL,type:'host-ready'},origin);
  return {ready};
}
