# ShopProof Chrome extension

The extension is a Manifest V3 demo client for the same ShopProof API used by the mobile web app.

## Load locally

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked** and choose this `extension` directory.
4. Open a product page on Shopee SG, Lazada SG, or TikTok Shop.
5. Click the ShopProof toolbar action.
6. The published Cloud Run URL is configured by default. Use the gear button only to change it; for local development use `http://localhost:8080`.

The popup reads visible page metadata and JSON-LD only after the user opens it. The shopper can select one or more objectives: **Same shop + product**, **Same product, any seller**, and **Similar cheaper products**, then choose **Compare across platforms**. Results appear in a table with the current listing as the price baseline. The source marketplace is excluded automatically, so a Shopee page searches Lazada and TikTok Shop, for example.

When a seller is detected, **Same shop + product** is selected by default. If no seller can be detected, **Same product, any seller** becomes the default because that comparison can still be verified reliably.

