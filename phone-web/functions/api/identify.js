const MAX_IMAGE_BYTES = 4 * 1024 * 1024;
// Cloudflare retired LLaVA (@cf/llava-hf/llava-1.5-7b-hf) on 2026-11-20, so one
// vision model now both describes the object and reads its label.
const VISION_MODEL = "@cf/moondream/moondream3.1-9B-A2B";
const DESCRIBE_QUESTION = "What is the main object in this photo? Answer in one or two short sentences "
  + "using simple, everyday words, starting with its name (for example: \"A computer mouse. It is "
  + "used to move the pointer on a computer screen.\"). Be specific when you can (a tea bottle, not "
  + "just a bottle) and mention useful visible features such as colour or contents. Do not guess "
  + "details that are not visible.";
const LABEL_QUESTION = "Read only the visible label text, especially Traditional Chinese characters. "
  + "Transcribe the characters exactly without translating or guessing. Return JSON only: "
  + "{\"visible_text\":\"exact text, or empty string if none\",\"product\":\"product name in "
  + "English if the text identifies it, otherwise empty string\"}.";
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

// Workers AI usually returns plain data, but some models hand back a Response or
// a stream (server-sent events). Normalise all three to an object with `answer`.
export async function readAiResult(result) {
  if (result && typeof result.json === "function" && typeof result.text === "function") {
    return parseAiText(await result.text(), "response");
  }
  if (result && typeof result.getReader === "function") {
    return parseAiText(await new Response(result).text(), "stream");
  }
  return result;
}

export function parseAiText(text, kind) {
  try {
    return JSON.parse(text);
  } catch {
    // Server-sent events: "data: {...}" lines, each with a piece of the answer.
    let answer = "";
    for (const line of text.split(/\r?\n/)) {
      const data = line.replace(/^data:\s*/, "").trim();
      if (!line.startsWith("data:") || !data || data === "[DONE]") continue;
      try {
        const piece = JSON.parse(data);
        answer += piece.answer ?? piece.response ?? piece.text ?? piece.caption ?? "";
      } catch {
        // Ignore lines that aren't JSON.
      }
    }
    return { answer, receivedAs: kind };
  }
}

function describeResultType(value) {
  if (value === null || value === undefined) return String(value);
  return `${value.constructor?.name || typeof value} with fields [${Object.keys(value).join(", ")}]`;
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

// Every call spends Workers AI quota, so only ClearView may use this endpoint.
// Browsers always send Origin on POST: it must be this site, which blocks
// other websites from borrowing the API. Non-browser callers (the desktop
// app) must identify themselves. This stops casual misuse, not a determined
// attacker; set a usage alert in the Cloudflare dashboard as the real backstop.
export const CLIENT_HEADER = "X-ClearView-Client";

export function isAllowedCaller(request) {
  const origin = request.headers.get("Origin");
  if (origin) {
    return origin === new URL(request.url).origin;
  }
  return Boolean(request.headers.get(CLIENT_HEADER));
}

export async function onRequestPost({ request, env }) {
  if (!isAllowedCaller(request)) {
    return jsonResponse({ error: "This endpoint is only for the ClearView app." }, 403);
  }
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
    const imageUri = imageDataUri(image, contentType);
    const rawTypes = {};
    const ask = async (name, question, maxTokens) => {
      const raw = await env.AI.run(VISION_MODEL, {
      task: "query",
      image: imageUri,
      question,
      reasoning: false,
      stream: false,
      temperature: 0.1,
      max_tokens: maxTokens,
      });
      rawTypes[name] = describeResultType(raw);
      return readAiResult(raw);
    };
    // Describe and read the label at the same time; a failed label read
    // doesn't block the description.
    const [objectResult, textResult] = await Promise.all([
      ask("describe", DESCRIBE_QUESTION, 128),
      ask("label", LABEL_QUESTION, 256).catch((error) => {
        console.error("Workers AI label reading failed; keeping object result", error);
        return null;
      }),
    ]);
    const objectAnswer = typeof objectResult?.answer === "string"
      ? objectResult.answer
      : "";
    const label = normalizeLabel(objectAnswer);
    const textAnswer = typeof textResult?.answer === "string"
      ? textResult.answer
      : "";

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
      resultType: objectAnswer ? undefined : rawTypes.describe,
      outputTokens: objectAnswer ? undefined : objectResult?.metrics?.output_tokens,
    });
  } catch (error) {
    console.error("Workers AI object recognition failed", error);
    return jsonResponse({
      error: "Cloudflare could not identify this photo. Please try again.",
    }, 502);
  }
}
