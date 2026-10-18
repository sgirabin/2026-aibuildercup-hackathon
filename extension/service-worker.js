chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type !== 'ANALYZE') return false;
  const form = new FormData();
  form.append('query', message.query);
  form.append('force_demo', String(Boolean(message.forceDemo)));
  fetch(`${message.apiBase}/api/analyze`, { method:'POST', body:form })
    .then(async response => {
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || `API returned ${response.status}`);
      sendResponse({ ok:true, data:body });
    })
    .catch(error => sendResponse({ ok:false, error:error.message }));
  return true;
});

