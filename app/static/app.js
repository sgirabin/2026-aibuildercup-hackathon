const form = document.querySelector('#analyze-form');
const queryInput = document.querySelector('#query');
const imageInput = document.querySelector('#image');
const fileChip = document.querySelector('#file-chip');
const loading = document.querySelector('#loading');
const results = document.querySelector('#results');
const errorPanel = document.querySelector('#error');
const submitButton = form.querySelector('button[type="submit"]');

const initialQuery = new URLSearchParams(location.search).get('q');
if (initialQuery) queryInput.value = initialQuery;

function decodeSharedComparison() {
  const marker = '#comparison=';
  if (!location.hash.startsWith(marker)) return null;
  try {
    let encoded = location.hash.slice(marker.length).replaceAll('-', '+').replaceAll('_', '/');
    encoded += '='.repeat((4 - encoded.length % 4) % 4);
    return JSON.parse(decodeURIComponent(escape(atob(encoded))));
  } catch (_) { return null; }
}

const money = (value, currency = 'SGD') => value == null ? 'Price unavailable' :
  new Intl.NumberFormat('en-SG', { style: 'currency', currency }).format(value);

const escapeHtml = (value) => String(value ?? '')
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

imageInput.addEventListener('change', () => {
  const file = imageInput.files[0];
  fileChip.classList.toggle('hidden', !file);
  fileChip.textContent = file ? `Screenshot: ${file.name}` : '';
});

document.querySelectorAll('[data-sample]').forEach(button => {
  button.addEventListener('click', () => {
    queryInput.value = button.dataset.sample;
    queryInput.focus();
  });
});

function renderFingerprint(fp) {
  const fields = [
    ['Brand', fp.brand], ['Model', fp.model_number], ['Variant', fp.variant],
    ['Colour', fp.colour], ['Storage', fp.storage], ['Bundle', fp.bundle],
    ['Original shop', fp.source_marketplace], ['Seller', fp.source_seller]
  ].filter(([, value]) => value);
  document.querySelector('#fingerprint').innerHTML = fields
    .map(([label, value]) => `<span><b>${escapeHtml(label)}</b>${escapeHtml(value)}</span>`).join('');
}

function renderOffer(item) {
  const mismatch = item.verdict === 'Variant mismatch';
  const saving = item.savings > 0 ? `<span class="saving">Save ${money(item.savings, item.currency)}</span>` : '';
  const seller = item.seller ? `<span>${escapeHtml(item.seller)}</span>` : '<span>Seller not indexed</span>';
  const sellerScore = item.seller_match_score == null ? '' : `<span>Seller similarity ${item.seller_match_score}%</span>`;
  return `<a class="offer-card" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">
    <div class="score" style="--score:${item.product_match_score}">
      <strong>${item.product_match_score}%</strong><small>PRODUCT</small>
    </div>
    <div class="offer-info">
      <span class="marketplace">${escapeHtml(item.marketplace)}</span>
      <h3>${escapeHtml(item.title)}</h3>
      <div class="meta">
        <span class="verdict ${mismatch ? 'mismatch' : ''}">${escapeHtml(item.verdict)}</span>
        <span class="confidence ${String(item.evidence_confidence_level).toLowerCase()}">${item.evidence_confidence_score}% evidence · ${escapeHtml(item.evidence_confidence_level)}</span>
        ${seller}${sellerScore}
      </div>
    </div>
    <div class="offer-price">
      <strong>${money(item.visible_price, item.currency)}</strong>
      ${saving}
      ${item.promotion ? `<span class="promo">${escapeHtml(item.promotion)}</span>` : ''}
    </div>
  </a>`;
}

function render(data) {
  const fp = data.fingerprint;
  document.querySelector('#product-name').textContent = fp.product_name;
  document.querySelector('#original-price').innerHTML = fp.visible_price == null ? '' :
    `Observed price<strong>${money(fp.visible_price, fp.currency)}</strong>`;
  renderFingerprint(fp);
  renderAgent(data.agent);
  document.querySelector('#offer-count').textContent = `${data.candidates.length} results checked`;
  document.querySelector('#offers').innerHTML = data.candidates.map(renderOffer).join('');

  const banner = document.querySelector('#mode-banner');
  banner.classList.toggle('live', data.mode === 'live');
  banner.innerHTML = `<strong>${data.mode === 'live' ? 'Live grounded comparison' : 'Demonstration mode'}</strong> — ${escapeHtml(data.warning || '')}`;

  const sourcesWrap = document.querySelector('#sources-wrap');
  sourcesWrap.classList.toggle('hidden', !data.sources?.length);
  document.querySelector('#sources').innerHTML = (data.sources || []).map(source =>
    `<li><a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.title)}</a></li>`
  ).join('');
}

function renderAgent(agent) {
  if (!agent) return;
  document.querySelector('#agent-status').textContent = `${agent.iterations} investigation${agent.iterations === 1 ? '' : 's'} · ${agent.tools_used.length} tools`;
  document.querySelector('#agent-confidence').textContent = `${agent.evidence_confidence_score}% ${agent.evidence_confidence_level} evidence confidence`;
  document.querySelector('#agent-confidence').className = String(agent.evidence_confidence_level).toLowerCase();
  document.querySelector('#agent-steps').innerHTML = agent.steps.map(step =>
    `<li><span>${escapeHtml(step.stage)}</span><p>${escapeHtml(step.summary)}</p>${step.tool ? `<code>${escapeHtml(step.tool)}</code>` : ''}</li>`
  ).join('');
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  results.classList.add('hidden');
  errorPanel.classList.add('hidden');
  loading.classList.remove('hidden');
  submitButton.disabled = true;

  const steps = ['Reading the product identity…', 'Searching publicly indexed listings…', 'Checking model and variant evidence…'];
  let step = 0;
  document.querySelector('#loading-step').textContent = steps[step];
  const timer = setInterval(() => {
    step = Math.min(step + 1, steps.length - 1);
    document.querySelector('#loading-step').textContent = steps[step];
  }, 2600);

  try {
    const payload = new FormData(form);
    if (!imageInput.files.length || !imageInput.files[0]?.size) payload.delete('image');
    const response = await fetch('/api/analyze', { method: 'POST', body: payload });
    const raw = await response.text();
    let data;
    try { data = raw ? JSON.parse(raw) : {}; }
    catch (_) {
      throw new Error(/upstream|timeout|deadline/i.test(raw)
        ? 'The live marketplace search timed out. Please retry with a more exact product name or model.'
        : `KiasuCheck received an invalid response from the backend (HTTP ${response.status}).`);
    }
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Unexpected response');
    render(data);
    results.classList.remove('hidden');
    results.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) {
    document.querySelector('#error-message').textContent = error.message;
    errorPanel.classList.remove('hidden');
  } finally {
    clearInterval(timer);
    loading.classList.add('hidden');
    submitButton.disabled = false;
  }
});

const sharedComparison = decodeSharedComparison();
if (sharedComparison) {
  render(sharedComparison);
  results.classList.remove('hidden');
  setTimeout(() => results.scrollIntoView({ behavior:'smooth', block:'start' }), 0);
}

