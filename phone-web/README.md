# ClearView Phone

A separate, mobile-friendly ClearView website. The existing Windows desktop app is unchanged.

## What it does

- Uses the phone's rear camera or photo picker to capture one image.
- Provides a separate Text scanner screen from the three-line feature menu, with its own camera capture and photo picker.
- Scans full-page English and Traditional Chinese text locally in the browser, then lets users edit or select recognized text to copy or read aloud.
- Sends the resized image to a Pages Function, which asks Cloudflare Workers AI's LLaVA model for a free-form description of the specific visible item, then Moondream 3.1 to read visible label text (including Traditional Chinese) and infer a product from the readable label.
- Shows the generated item description, recognized label text, and any product identification based on that text, then reads the result aloud using the browser's built-in speech synthesis, with sentence and current-word highlighting when the browser reports speech boundaries.
- Does not save photos. Images are sent to Cloudflare for inference.

The website needs HTTPS for camera access and clipboard access, so use the deployed Cloudflare Pages URL on your phone. The photo picker remains available when camera access is denied or unavailable.

The separate text scanner uses Tesseract.js in the browser to recognize English and Traditional Chinese. Open it from the three-line menu; its camera and photo picker are separate from object scanning. Its OCR models are downloaded on first use and cached by the browser; the selected image is processed on-device and is not uploaded for text scanning. Object identification still sends the image to Cloudflare Workers AI.

## Deploy to Cloudflare Pages

1. Push this repository to a Git provider connected to Cloudflare, or use the Cloudflare Pages dashboard to create a project from this repository.
2. Set the Pages project root directory to `phone-web`.
3. Use `public` as the build output directory. There is no build command.
4. The Workers AI binding is configured as `ai.binding: "AI"` in `wrangler.jsonc`. Commit and push that configuration so Cloudflare deploys it with the Pages project.
5. Open the deployed `*.pages.dev` address on your phone and allow camera access. The phone and computer should be using the same public HTTPS site.

The Pages Function is `functions/api/identify.js`; its `/api/identify` endpoint uses Cloudflare Workers AI's LLaVA model for object identification and Moondream 3.1 for English/Traditional Chinese label reading. OCR failures do not block object identification. Product identification is inferred from the recognized text and can still be wrong. The phone site uses hosted vision models rather than the desktop app's YOLO-World and EasyOCR pipeline. The Wrangler configuration file is the source of truth for this Pages project's settings, including the Workers AI binding.

For cost protection, configure a Cloudflare rate-limiting rule for `POST /api/identify` in the Cloudflare dashboard before sharing the public URL. The endpoint also limits image uploads to 4 MB and accepts only JPEG, PNG, and WebP.

## Local preview

Install Node.js, then from this directory run:

```sh
npx wrangler pages dev public
```

This serves the static site and Pages Function locally. For local scans, start Wrangler with `npx wrangler pages dev public --ai AI`; Workers AI usage may incur charges.

## Limitations

- Browser camera and speech features vary by phone and browser.
- Text recognition works best with a sharp, upright, evenly lit page; proofread OCR results. Selecting text works in the editable recognized-text area, and the browser reads the selected passage or all text.
- Speech pronunciation depends on the selected browser voice; choose one that supports Traditional Chinese to hear Chinese text read naturally.
- Recognition is an AI estimate and can be wrong, especially for small, obscured, or unusual objects.
- Cloudflare Workers AI usage may be subject to account limits or charges.
- This site does not provide the desktop app's local YOLO detector, camera controls, or Windows voices.
