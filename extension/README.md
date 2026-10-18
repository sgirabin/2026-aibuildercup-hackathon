# ShopProof Chrome extension

The extension is a Manifest V3 demo client for the same ShopProof API used by the mobile web app.

## Load locally

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked** and choose this `extension` directory.
4. Open a product page on Shopee SG, Lazada SG, or TikTok Shop.
5. Click the ShopProof toolbar action.
6. The published Cloud Run URL is configured by default. Use the gear button only to change it; for local development use `http://localhost:8080`.

The popup reads visible page metadata and JSON-LD only after the user opens it. The shopper can then choose **Find the same product**, **Find similar products**, **Check this seller elsewhere**, or **Check on Lazada**. The extension sends the selected intent and visible product evidence to the ShopProof backend only when the user clicks an action.

