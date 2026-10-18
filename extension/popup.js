const DEFAULT_API = 'https://shopproof-133701402785.asia-southeast1.run.app';
const RESULT_CACHE_VERSION = '0.6.4';
const supportedHosts = ['shopee.sg', 'lazada.sg', 'shop.tiktok.com'];
const allPlatforms = ['Shopee', 'Lazada', 'TikTok Shop'];
let page = null;
let progressTimer = null;

const $ = selector => document.querySelector(selector);
const show = selector => $(selector).classList.remove('hidden');
const hide = selector => $(selector).classList.add('hidden');
const money = (value, currency = 'SGD') => value == null || Number.isNaN(Number(value)) ? '—' :
  new Intl.NumberFormat('en-SG', { style:'currency', currency }).format(Number(value));
const escapeHtml = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
const numericPrice = value => {
  const match = String(value ?? '').replaceAll(',', '').match(/\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
};

async function configuredApi() {
  const stored = await chrome.storage.local.get(['apiBase', 'apiBaseVersion']);
  let apiBase = stored.apiBase || DEFAULT_API;
  if (!stored.apiBaseVersion) {
    apiBase = apiBase === 'http://localhost:8080' ? DEFAULT_API : apiBase;
    await chrome.storage.local.set({ apiBase, apiBaseVersion:2 });
  }
  return apiBase;
}

function extractProductPage() {
  const meta = name => document.querySelector(`meta[property="${name}"],meta[name="${name}"]`)?.content;
  const text = selector => document.querySelector(selector)?.textContent?.trim();
  const objects = [];
  document.querySelectorAll('script[type="application/ld+json"]').forEach(script => {
    try {
      const parsed = JSON.parse(script.textContent);
      const visit = value => {
        if (!value || typeof value !== 'object') return;
        if (Array.isArray(value)) return value.forEach(visit);
        objects.push(value);
        Object.values(value).forEach(visit);
      };
      visit(parsed);
    } catch (_) { /* Some marketplaces publish invalid or partial JSON-LD. */ }
  });
  const product = objects.find(item => {
    const type = item['@type'];
    return type === 'Product' || (Array.isArray(type) && type.includes('Product'));
  }) || {};
  const offer = Array.isArray(product.offers) ? product.offers[0] : (product.offers || {});
  const host = location.hostname;
  const marketplace = host.includes('shopee') ? 'Shopee' : host.includes('lazada') ? 'Lazada' : host.includes('tiktok') ? 'TikTok Shop' : host;
  const title = product.name || meta('og:title') || text('h1') || document.title;
  const price = offer.price || offer.lowPrice || meta('product:price:amount') || meta('og:price:amount') ||
    text('[class*="product-price"], [class*="pdp-price"], [class*="price"]');
  const sellerObject = offer.seller || product.seller || {};
  const seller = sellerObject.name || text('[class*="shop-name"], [class*="seller-name"], [class*="sellerName"], [class*="shop"] [class*="name"], a[href*="/shop/"]');
  return { url:location.href, title, price, seller, marketplace };
}

async function init() {
  const apiBase = await configuredApi();
  $('#api-base').value = apiBase;
  const [tab] = await chrome.tabs.query({ active:true, currentWindow:true });
  if (!tab?.url) return show('#unsupported');
  const host = new URL(tab.url).hostname;
  if (!supportedHosts.some(item => host === item || host.endsWith(`.${item}`))) return show('#unsupported');
  const [{ result }] = await chrome.scripting.executeScript({ target:{ tabId:tab.id }, func:extractProductPage });
  page = result;
  $('#marketplace').textContent = page.marketplace;
  $('#title').textContent = page.title;
  $('#page-price').textContent = page.price || 'Price not detected';
  const targets = allPlatforms.filter(platform => platform !== page.marketplace);
  $('#target-platforms').textContent = `Searching ${targets.join(' + ')}`;

  // Shop comparison is the most distinctive check, but it requires a detected seller.
  $('#objective-shop').checked = Boolean(page.seller);
  $('#objective-product').checked = !page.seller;
  if (!page.seller) {
    $('#objective-shop').closest('label').title = 'Seller was not detected on this page; results may be limited.';
  }
  show('#product');

  const { lastAnalysis } = await chrome.storage.local.get('lastAnalysis');
  if (lastAnalysis && lastAnalysis.cacheVersion !== RESULT_CACHE_VERSION) {
    await chrome.storage.local.remove('lastAnalysis');
  } else if (lastAnalysis?.pageUrl === page.url && lastAnalysis?.data) {
    render(lastAnalysis.data, apiBase);
    hide('#product');
    show('#results');
  }
}

$('#settings-button').addEventListener('click', () => $('#settings').classList.toggle('hidden'));
$('#save-settings').addEventListener('click', async () => {
  const apiBase = $('#api-base').value.trim().replace(/\/$/, '');
  await chrome.storage.local.set({ apiBase, apiBaseVersion:2 });
  hide('#settings');
});

async function runAnalysis() {
  const objectives = [...document.querySelectorAll('.objectives input:checked')].map(input => input.value);
  if (!objectives.length) {
    $('#error').textContent = 'Select at least one comparison objective.';
    return show('#error');
  }

  hide('#product'); hide('#results'); hide('#error'); show('#loading');
  $('#loading-title').textContent = 'Comparing across platforms';
  const stages = [
    'Reading the exact product and variant',
    'Searching public listings on the other platforms',
    'Verifying model, seller and price evidence',
    'Preparing the comparison'
  ];
  const started = Date.now();
  let stage = 0;
  $('#loading-detail').textContent = `${stages[stage]} · 0s`;
  progressTimer = setInterval(() => {
    const elapsed = Math.round((Date.now() - started) / 1000);
    stage = Math.min(Math.floor(elapsed / 20), stages.length - 1);
    $('#loading-detail').textContent = `${stages[stage]} · ${elapsed}s elapsed`;
  }, 1000);
  try {
    const apiBase = await configuredApi();
    const response = await chrome.runtime.sendMessage({
      type:'ANALYZE', apiBase,
      query:`${page.title}\nMarketplace: ${page.marketplace}\nSeller: ${page.seller || 'not detected'}\nVisible price: ${page.price || 'not detected'}\nURL: ${page.url}`,
      forceDemo:$('#demo-mode').checked,
      intent:objectives.length > 1 ? 'multi' : ({same_shop_product:'seller', same_product:'exact', similar_product:'similar'}[objectives[0]]),
      objectives
    });
    if (!response.ok) throw new Error(response.error);
    await chrome.storage.local.set({
      lastAnalysis:{
        cacheVersion:RESULT_CACHE_VERSION,
        pageUrl:page.url,
        data:response.data,
        savedAt:Date.now()
      }
    });
    render(response.data, apiBase);
    show('#results');
  } catch (error) {
    $('#error').textContent = error.message || 'KiasuCheck could not reach the backend.';
    show('#error'); show('#product');
  } finally {
    clearInterval(progressTimer);
    progressTimer = null;
    hide('#loading');
  }
}

$('#compare-button').addEventListener('click', runAnalysis);

function differenceCell(price) {
  const current = numericPrice(page.price);
  if (current == null || price == null) return '—';
  const difference = current - Number(price);
  if (Math.abs(difference) < 0.005) return 'Same price';
  return difference > 0 ? `<span class="saving">Save ${money(difference)}</span>` :
    `<span class="extra">${money(Math.abs(difference))} more</span>`;
}

function render(data, apiBase) {
  $('#mode').textContent = `${data.mode === 'live' ? 'LIVE GROUNDED RESULTS' : 'DEMONSTRATION MODE'} — ${data.warning || ''}`;
  const agent = data.agent;
  $('#agent-summary').innerHTML = agent ? `<div><b>KiasuCheck Agent</b><strong class="${String(agent.evidence_confidence_level).toLowerCase()}">${agent.evidence_confidence_score}% ${escapeHtml(agent.evidence_confidence_level)} evidence confidence</strong></div><small>${agent.iterations} investigation${agent.iterations === 1 ? '' : 's'} · ${agent.tools_used.length} tools · ${agent.steps.length} trace steps</small>` : '';
  $('#fingerprint').innerHTML = `<strong>${escapeHtml(data.fingerprint.product_name)}</strong><span>${escapeHtml([data.fingerprint.brand, data.fingerprint.model_number, data.fingerprint.variant].filter(Boolean).join(' · '))}</span>`;
  const typeLabels = {
    same_shop_product:'Same shop + product',
    same_product:'Same product',
    similar_product:'Similar product'
  };
  const currentRow = `<tr>
    <td><span class="match-chip current-chip">Current</span></td>
    <td><b>${escapeHtml(page.marketplace)}</b><small>${escapeHtml(page.seller || 'Shop not detected')}</small></td>
    <td>${escapeHtml(page.title)}</td>
    <td><b>${money(numericPrice(page.price))}</b></td><td>Baseline</td>
  </tr>`;
  const resultRows = data.candidates.map(item => `<tr>
    <td><span class="match-chip">${escapeHtml(typeLabels[item.match_type] || 'Result')}</span><small>${item.product_match_score}% product match</small><small class="${String(item.evidence_confidence_level).toLowerCase()}">${item.evidence_confidence_score}% evidence · ${escapeHtml(item.evidence_confidence_level)}</small></td>
    <td><b>${escapeHtml(item.marketplace)}</b><small>${escapeHtml(item.seller || 'Shop not indexed')}</small></td>
    <td><a href="${escapeHtml(item.url)}" target="_blank">${escapeHtml(item.title)}</a><small>${escapeHtml(item.promotion || '')}</small></td>
    <td><b>${money(item.visible_price, item.currency)}</b></td>
    <td>${differenceCell(item.visible_price)}</td>
  </tr>`).join('');
  $('#offers').innerHTML = currentRow + (resultRows || `<tr><td colspan="5">No supported indexed listings were found.</td></tr>`);
  $('#open-app').onclick = () => {
    const json = JSON.stringify(data);
    const encoded = btoa(unescape(encodeURIComponent(json)))
      .replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '');
    chrome.tabs.create({ url:`${apiBase}/#comparison=${encoded}` });
  };
}

init().catch(error => { $('#error').textContent = error.message; show('#error'); });
