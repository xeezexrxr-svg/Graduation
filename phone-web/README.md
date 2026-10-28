# ClearView Phone

A separate, mobile-friendly ClearView website. The existing Windows desktop app is unchanged.

## What it does

- Uses the phone's rear camera or photo picker to capture one image.
- Sends the resized image to a Pages Function, which asks Cloudflare Workers AI to identify the main everyday object.
- Shows a short explanation and reads it aloud using the browser's built-in speech synthesis, with sentence and current-word highlighting when the browser reports speech boundaries.
- Does not save photos. Images are sent to Cloudflare for inference.

The website needs HTTPS for camera access, so use the deployed Cloudflare Pages URL on your phone. The photo picker remains available when camera access is denied or unavailable.

## Deploy to Cloudflare Pages

1. Push this repository to a Git provider connected to Cloudflare, or use the Cloudflare Pages dashboard to create a project from this repository.
2. Set the Pages project root directory to `phone-web`.
3. Use `public` as the build output directory. There is no build command.
4. The Workers AI binding is configured as `ai.binding: "AI"` in `wrangler.jsonc`. Commit and push that configuration so Cloudflare deploys it with the Pages project.
5. Open the deployed `*.pages.dev` address on your phone and allow camera access. The phone and computer should be using the same public HTTPS site.

The Pages Function is `functions/api/identify.js`; its `/api/identify` endpoint uses Cloudflare Workers AI's `@cf/llava-hf/llava-1.5-7b-hf` vision model. The Wrangler configuration file is the source of truth for this Pages project's settings, including the Workers AI binding.

For cost protection, configure a Cloudflare rate-limiting rule for `POST /api/identify` in the Cloudflare dashboard before sharing the public URL. The endpoint also limits image uploads to 4 MB and accepts only JPEG, PNG, and WebP.

## Local preview

Install Node.js, then from this directory run:

```sh
npx wrangler pages dev public
```

This serves the static site and Pages Function locally. For local scans, start Wrangler with `npx wrangler pages dev public --ai AI`; Workers AI usage may incur charges.

## Limitations

- Browser camera and speech features vary by phone and browser.
- Recognition is an AI estimate and can be wrong, especially for small, obscured, or unusual objects.
- Cloudflare Workers AI usage may be subject to account limits or charges.
- This site does not provide the desktop app's local YOLO detector, camera controls, or Windows voices.
