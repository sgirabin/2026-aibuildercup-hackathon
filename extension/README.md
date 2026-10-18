# ShopProof Chrome extension

The extension is a Manifest V3 demo client for the same ShopProof API used by the mobile web app.

## Load locally

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked** and choose this `extension` directory.
4. Open a product page on Shopee SG, Lazada SG, or TikTok Shop.
5. Click the ShopProof toolbar action.
6. Use the gear button to set the deployed Cloud Run URL. For local development use `http://localhost:8080`.

The popup extracts only information already visible in the active product page and sends it to the configured ShopProof backend when the user clicks **Check other offers**.

