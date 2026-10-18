const DEFAULT_API = 'https://shopproof-133701402785.asia-southeast1.run.app';
const supportedHosts = ['shopee.sg', 'lazada.sg', 'shop.tiktok.com'];
let page = null;

const $ = selector => document.querySelector(selector);
const show = selector => $(selector).classList.remove('hidden');
const hide = selector => $(selector).classList.add('hidden');
const money = (value, currency = 'SGD') => value == null ? '—' : new Intl.NumberFormat('en-SG', { style:'currency', currency }).format(value);
const escapeHtml = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');

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
  const seller = sellerObject.name || text('[class*="shop-name"], [class*="seller-name"], [class*="sellerName"]');
  return { url:location.href, title, price, seller, marketplace };
}

async function init() {
  const { apiBase = DEFAULT_API } = await chrome.storage.local.get('apiBase');
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
  show('#product');
}

$('#settings-button').addEventListener('click', () => $('#settings').classList.toggle('hidden'));
$('#save-settings').addEventListener('click', async () => {
  const apiBase = $('#api-base').value.trim().replace(/\/$/, '');
  await chrome.storage.local.set({ apiBase });
  hide('#settings');
});

async function runAnalysis(button) {
  hide('#product'); hide('#results'); hide('#error'); show('#loading');
  const intent = button.dataset.intent || 'exact';
  const targetMarketplace = button.dataset.target || '';
  const labels = {
    exact: targetMarketplace ? `Searching ${targetMarketplace}` : 'Checking exact identity',
    similar: 'Finding comparable products',
    seller: 'Tracing the seller across platforms'
  };
  $('#loading-title').textContent = labels[intent];
  try {
    const { apiBase = DEFAULT_API } = await chrome.storage.local.get('apiBase');
    const response = await chrome.runtime.sendMessage({
      type:'ANALYZE', apiBase,
      query:`${page.title}\nMarketplace: ${page.marketplace}\nSeller: ${page.seller || 'not detected'}\nVisible price: ${page.price || 'not detected'}\nURL: ${page.url}`,
      forceDemo:$('#demo-mode').checked,
      intent,
      targetMarketplace
    });
    if (!response.ok) throw new Error(response.error);
    render(response.data, apiBase);
    show('#results');
  } catch (error) {
    $('#error').textContent = error.message || 'ShopProof could not reach the backend.';
    show('#error'); show('#product');
  } finally { hide('#loading'); }
}

document.querySelectorAll('.action-button').forEach(button => {
  button.addEventListener('click', () => runAnalysis(button));
});

function render(data, apiBase) {
  $('#mode').textContent = `${data.mode === 'live' ? 'LIVE GROUNDED RESULTS' : 'DEMONSTRATION MODE'} — ${data.warning || ''}`;
  $('#fingerprint').innerHTML = `<strong>${escapeHtml(data.fingerprint.product_name)}</strong><span>${escapeHtml([data.fingerprint.brand, data.fingerprint.model_number, data.fingerprint.variant].filter(Boolean).join(' · '))}</span>`;
  $('#offers').innerHTML = data.candidates.length ? data.candidates.slice(0, 4).map(item => `<a class="offer" href="${escapeHtml(item.url)}" target="_blank">
    <span class="score">${item.product_match_score}%</span>
    <span class="offer-title"><span>${escapeHtml(item.marketplace)}</span><strong>${escapeHtml(item.title)}</strong></span>
    <span class="price">${money(item.visible_price, item.currency)}${item.savings > 0 ? `<small class="saving">Save ${money(item.savings, item.currency)}</small>` : ''}</span>
  </a>`).join('') : '<div class="notice">No supported indexed listings were found. Try “Find similar products” or check another marketplace.</div>';
  $('#open-app').onclick = () => chrome.tabs.create({ url:`${apiBase}/?q=${encodeURIComponent(page.url)}` });
}

init().catch(error => { $('#error').textContent = error.message; show('#error'); });

