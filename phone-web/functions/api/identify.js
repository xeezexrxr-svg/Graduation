const MAX_IMAGE_BYTES = 4 * 1024 * 1024;
const MODEL = "@cf/llava-hf/llava-1.5-7b-hf";
const ALLOWED_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const HUMAN_LABELS = new Set(["person", "people", "human", "hand", "arm", "finger"]);
const OBJECT_LABELS = [
  "cell phone",
  "mobile phone",
  "computer mouse",
  "cellphone",
  "headphones",
  "toothbrush",
  "backpack",
  "keyboard",
  "laptop",
  "mouse",
  "apple",
  "banana",
  "book",
  "bottle",
  "cup",
  "fork",
  "glasses",
  "handbag",
  "phone",
  "pen",
  "plate",
  "remote",
  "scissors",
  "shoe",
  "shoes",
  "spoon",
  "stapler",
  "umbrella",
  "wallet",
];
const LABEL_ALIASES = new Map([
  ["computer mouse", "mouse"],
  ["mobile phone", "cell phone"],
  ["cellphone", "cell phone"],
]);

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

function normalizeLabel(answer) {
  const knownLabel = OBJECT_LABELS.reduce((bestMatch, candidate) => {
    const escaped = candidate.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const match = new RegExp(`(^|[^a-z])${escaped}(?=$|[^a-z])`, "i").exec(answer);
    if (!match) return bestMatch;
    const index = match.index + match[1].length;
    return !bestMatch || index < bestMatch.index
      ? { index, label: candidate }
      : bestMatch;
  }, null);
  if (knownLabel) {
    return LABEL_ALIASES.get(knownLabel.label) || knownLabel.label;
  }

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
      image: Array.from(image),
      prompt: "Identify the main everyday object in this image. Reply with its short common name.",
      max_tokens: 48,
    });
    const answer = typeof result?.description === "string" ? result.description : "";
    const label = normalizeLabel(answer);
    const responseSummary = answer
      ? undefined
      : JSON.stringify(result)?.slice(0, 240) || String(result);
    return jsonResponse({
      found: Boolean(label),
      label,
      answer: label ? undefined : answer.slice(0, 120),
      modelFields: answer ? undefined : Object.keys(result || {}).slice(0, 12),
      responseSummary,
      finishReason: answer ? undefined : result?.finish_reason,
      outputTokens: answer ? undefined : result?.metrics?.output_tokens,
    });
  } catch (error) {
    console.error("Workers AI object recognition failed", error);
    return jsonResponse({
      error: "Cloudflare could not identify this photo. Please try again.",
    }, 502);
  }
}
