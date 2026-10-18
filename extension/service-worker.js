chrome.runtime.onInstalled.addListener(details => {
  if (details.reason === 'update') chrome.storage.local.remove('lastAnalysis');
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type !== 'ANALYZE') return false;
  const form = new FormData();
  form.append('query', message.query);
  form.append('force_demo', String(Boolean(message.forceDemo)));
  form.append('intent', message.intent || 'exact');
  form.append('objectives', (message.objectives || []).join(','));
  if (message.targetMarketplace) form.append('target_marketplace', message.targetMarketplace);
  fetch(`${message.apiBase}/api/analyze`, { method:'POST', body:form })
    .then(async response => {
      const raw = await response.text();
      let body;
      try { body = raw ? JSON.parse(raw) : {}; }
      catch (_) {
        const timedOut = /upstream|timeout|deadline/i.test(raw);
        throw new Error(timedOut
          ? 'The live marketplace search timed out. Please retry with only one comparison option.'
          : `KiasuCheck received an invalid response from the backend (HTTP ${response.status}).`);
      }
      if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `API returned ${response.status}`);
      sendResponse({ ok:true, data:body });
    })
    .catch(error => sendResponse({ ok:false, error:error.message }));
  return true;
});

