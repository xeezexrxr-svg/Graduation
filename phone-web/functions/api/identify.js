const MAX_IMAGE_BYTES = 4 * 1024 * 1024;
const OBJECT_MODEL = "@cf/llava-hf/llava-1.5-7b-hf";
const OCR_MODEL = "@cf/moondream/moondream3.1-9B-A2B";
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

function imageDataUri(image, contentType) {
  let binary = "";
  const chunkSize = 0x8000;
  for (let offset = 0; offset < image.length; offset += chunkSize) {
    binary += String.fromCharCode(...image.subarray(offset, offset + chunkSize));
  }
  return `data:${contentType};base64,${btoa(binary)}`;
}

function parseRecognition(answer) {
  let objectText = "";
  let visibleText = "";
  let product = "";
  let structuredResult;

  const jsonMatch = answer.match(/\{[\s\S]*\}/);
  if (jsonMatch) {
    try {
      structuredResult = JSON.parse(jsonMatch[0]);
    } catch {
      structuredResult = null;
    }
  }

  if (structuredResult && typeof structuredResult === "object") {
    objectText = typeof structuredResult.object === "string"
      ? structuredResult.object
      : "";
    visibleText = typeof structuredResult.visible_text === "string"
      ? structuredResult.visible_text
      : "";
    product = typeof structuredResult.product === "string"
      ? structuredResult.product
      : "";
  } else {
    objectText = answer.match(/^\s*(?:object|item)\s*[:=-]\s*(.+)$/im)?.[1] || "";
    visibleText = answer.match(/^\s*visible[_ ]text\s*[:=-]\s*(.+)$/im)?.[1] || "";
    product = answer.match(/^\s*product\s*[:=-]\s*(.+)$/im)?.[1] || "";
  }

  const label = normalizeLabel(objectText || answer);
  const normalizedVisibleText = visibleText
    .replace(/^\s*["'`]+|["'`]+\s*$/g, "")
    .replace(/\s+/g, " ")
    .trim();

  return {
    label,
    recognizedText: /^(none|no readable text|n\/a)$/i.test(normalizedVisibleText)
      ? ""
      : normalizedVisibleText.slice(0, 240),
    product: product
      .replace(/^\s*["'`]+|["'`]+\s*$/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 120),
  };
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
    const objectResult = await env.AI.run(OBJECT_MODEL, {
      image: Array.from(image),
      prompt: "Describe the main object in one or two short sentences, not just its broad category. Identify the specific kind of item when visible (for example, a drink bottle or tea bottle), and mention useful visible features such as material, color, shape, contents, or purpose. Read any clearly legible label text, including Traditional Chinese, exactly; do not guess text or details that are not visible. Reply with the description only.",
      max_tokens: 128,
    });
    const objectAnswer = typeof objectResult?.description === "string"
      ? objectResult.description
      : "";
    const label = normalizeLabel(objectAnswer);

    let textResult = null;
    let textAnswer = "";
    if (image.length <= MAX_IMAGE_BYTES) {
      try {
        textResult = await env.AI.run(OCR_MODEL, {
          task: "query",
          image: imageDataUri(image, contentType),
          question: "Read only the visible label text, especially Traditional Chinese characters. Transcribe the characters exactly without translating or guessing. Return JSON only: {\"visible_text\":\"exact text, or empty string if none\",\"product\":\"product name in English if the text identifies it, otherwise empty string\"}.",
          reasoning: false,
          temperature: 0.1,
          max_tokens: 256,
        });
        textAnswer = typeof textResult?.answer === "string"
          ? textResult.answer
          : "";
      } catch (error) {
        console.error("Workers AI label reading failed; keeping object result", error);
      }
    }

    const ocrResult = parseRecognition(textAnswer);
    const recognizedText = ocrResult.recognizedText;
    return jsonResponse({
      found: Boolean(label || recognizedText),
      label,
      description: objectAnswer.trim().replace(/\s+/g, " ").slice(0, 360) || undefined,
      recognizedText: recognizedText || undefined,
      product: recognizedText ? ocrResult.product || undefined : undefined,
      textReaderAvailable: Boolean(textAnswer),
      answer: label ? undefined : objectAnswer.slice(0, 120),
      modelFields: objectAnswer ? undefined : Object.keys(objectResult || {}).slice(0, 12),
      responseSummary: objectAnswer
        ? undefined
        : JSON.stringify(objectResult)?.slice(0, 240) || "The object model returned no text.",
      finishReason: objectAnswer ? undefined : objectResult?.finish_reason,
      outputTokens: objectAnswer ? undefined : objectResult?.metrics?.output_tokens,
    });
  } catch (error) {
    console.error("Workers AI object recognition failed", error);
    return jsonResponse({
      error: "Cloudflare could not identify this photo. Please try again.",
    }, 502);
  }
}
