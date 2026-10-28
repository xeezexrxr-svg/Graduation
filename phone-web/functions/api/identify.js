const MAX_IMAGE_BYTES = 4 * 1024 * 1024;
const MODEL = "@cf/moondream/moondream3.1-9B-A2B";
const ALLOWED_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const HUMAN_LABELS = new Set(["person", "people", "human", "hand", "arm", "finger"]);

function jsonResponse(payload, status = 200) {
  return Response.json(payload, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

async function readImage(request) {
  const declaredLength = Number(request.headers.get("Content-Length"));
  if (Number.isFinite(declaredLength) && declaredLength > MAX_IMAGE_BYTES) {
    return null;
  }
  if (!request.body) {
    return new Uint8Array();
  }

  const reader = request.body.getReader();
  const chunks = [];
  let totalBytes = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    totalBytes += value.byteLength;
    if (totalBytes > MAX_IMAGE_BYTES) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }

  const image = new Uint8Array(totalBytes);
  let offset = 0;
  for (const chunk of chunks) {
    image.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return image;
}

function toBase64(bytes) {
  let binary = "";
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    const chunk = bytes.subarray(offset, offset + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary);
}

function normalizeLabel(answer) {
  const label = answer
    .split(/\r?\n/, 1)[0]
    .replace(/^\s*(?:object|item|answer)\s*[:=-]\s*/i, "")
    .replace(/^[\s"'`]+|[\s"'`]+$/g, "")
    .replace(/^(?:a|an|the)\s+/i, "")
    .replace(/[.!?].*$/, "")
    .replace(/[.,;:]+$/, "")
    .trim()
    .replace(/\s+/g, " ");
  if (
    !label
    || label.length > 48
    || /^(none|unknown|unclear|no object)$/i.test(label)
    || HUMAN_LABELS.has(label.toLowerCase())
  ) {
    return null;
  }
  return label;
}

export async function onRequestPost({ request, env }) {
  if (!env.AI || typeof env.AI.run !== "function") {
    return jsonResponse({
      error: "Object recognition is not configured yet. Add the Workers AI binding named AI to this Pages project.",
    }, 503);
  }

  const contentType = (request.headers.get("Content-Type") || "")
    .split(";", 1)[0]
    .trim()
    .toLowerCase();
  if (!ALLOWED_IMAGE_TYPES.has(contentType)) {
    return jsonResponse({ error: "Upload a JPEG, PNG, or WebP photo." }, 415);
  }

  let image;
  try {
    image = await readImage(request);
  } catch (error) {
    console.error("Could not read uploaded image", error);
    return jsonResponse({ error: "Could not read the uploaded photo." }, 400);
  }
  if (image === null) {
    return jsonResponse({ error: "Photo is too large. Choose an image under 4 MB." }, 413);
  }
  if (!image.length) {
    return jsonResponse({ error: "Choose a photo before starting the scan." }, 400);
  }

  try {
    const result = await env.AI.run(MODEL, {
      task: "query",
      image: `data:${contentType};base64,${toBase64(image)}`,
      question: "Identify the largest clearly visible everyday object in this image. Choose its most likely common name, even if you are not certain. Reply with only a short label, such as computer mouse, keyboard, laptop, bottle, cup, or book. Do not reply none if an object is visible.",
      reasoning: false,
      temperature: 0,
      max_tokens: 32,
    });
    const answer = typeof result?.answer === "string" ? result.answer : "";
    const label = normalizeLabel(answer);
    return jsonResponse({
      found: Boolean(label),
      label,
      answer: label ? undefined : answer.slice(0, 120),
    });
  } catch (error) {
    console.error("Workers AI object recognition failed", error);
    return jsonResponse({
      error: "Cloudflare could not identify this photo. Please try again.",
    }, 502);
  }
}
