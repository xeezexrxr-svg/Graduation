"use strict";

// On-device object detection with two models working together:
// - ClearView's everyday-object model (YOLOE), built from vocabulary.txt by
//   build_detector.py: knows 175 everyday objects, including wallet, keys, pen.
// - YOLO26: knows only 80 object types, but is more reliable on those.
// When both find the same object, YOLO26's name wins if the everyday model also
// thought it was one of YOLO26's types (that fixes a mouse seen from above being
// called a cell phone). Objects only the everyday model knows keep its name.
// The desktop app combines them the same way (app.py, merge_with_coco).
const ORT_VERSION = "1.20.1";
const EVERYDAY_MODEL = { model: "/models/clearview-detector.onnx", labels: "/models/labels.json", minScore: 0.4 };
const COCO_MODEL = { model: "/models/yolo26n.onnx", labels: "/models/yolo26-labels.json", minScore: 0.3 };
const DETECTOR_INPUT_SIZE = 640;
const DETECTOR_IOU_LIMIT = 0.45;
const SAME_OBJECT_IOU = 0.45;
const DETECTOR_HUMAN_LABELS = new Set(["person"]);
// YOLO26's names, written the way vocabulary.txt writes them.
const COCO_TO_EVERYDAY = new Map([
  ["mouse", "computer mouse"],
  ["remote", "remote control"],
  ["couch", "sofa"],
  ["dining table", "table"],
  ["donut", "doughnut"],
  ["sports ball", "ball"],
  ["hair drier", "hair dryer"],
]);

let detectorModels = null;

function loadModel({ model, labels, minScore }) {
  return Promise.all([
    ort.InferenceSession.create(model, { executionProviders: ["wasm"] }),
    fetch(labels).then((response) => {
      if (!response.ok) throw new Error("An object list did not load.");
      return response.json();
    }),
  ]).then(([session, names]) => ({ session, labels: names, minScore }));
}

// Resolves to { everyday, coco }; coco is null if YOLO26 couldn't load, in
// which case the everyday model works alone.
function loadDetector() {
  if (!detectorModels) {
    if (!globalThis.ort) {
      return Promise.reject(new Error("The object detector library did not load."));
    }
    ort.env.wasm.wasmPaths = `https://cdn.jsdelivr.net/npm/onnxruntime-web@${ORT_VERSION}/dist/`;
    ort.env.wasm.numThreads = 1;
    detectorModels = Promise.all([
      loadModel(EVERYDAY_MODEL),
      loadModel(COCO_MODEL).catch((error) => {
        console.error("YOLO26 did not load; using the everyday-object model alone", error);
        return null;
      }),
    ]).then(([everyday, coco]) => ({ everyday, coco })).catch((error) => {
      detectorModels = null;
      throw error;
    });
  }
  return detectorModels;
}

function boxArea(box) {
  return Math.max(0, box[2] - box[0]) * Math.max(0, box[3] - box[1]);
}

function boxIou(first, second) {
  const width = Math.max(0, Math.min(first[2], second[2]) - Math.max(first[0], second[0]));
  const height = Math.max(0, Math.min(first[3], second[3]) - Math.max(first[1], second[1]));
  const intersection = width * height;
  const union = boxArea(first) + boxArea(second) - intersection;
  return union > 0 ? intersection / union : 0;
}

// output: model data shaped [rows, candidates]: cx, cy, w, h, then one score per
// label (any rows after that, such as mask data, are ignored).
// scale: how much the photo was shrunk to fit the 640px model input.
function decodeDetections(output, candidates, scale, labels, minScore = EVERYDAY_MODEL.minScore) {
  const classCount = labels.length;
  const found = [];
  for (let index = 0; index < candidates; index += 1) {
    let bestClass = 0;
    let bestScore = 0;
    for (let classId = 0; classId < classCount; classId += 1) {
      const score = output[(4 + classId) * candidates + index];
      if (score > bestScore) {
        bestScore = score;
        bestClass = classId;
      }
    }
    if (bestScore < minScore) continue;
    const centerX = output[index] / scale;
    const centerY = output[candidates + index] / scale;
    const width = output[2 * candidates + index] / scale;
    const height = output[3 * candidates + index] / scale;
    found.push({
      label: labels[bestClass],
      confidence: bestScore,
      box: [centerX - width / 2, centerY - height / 2, centerX + width / 2, centerY + height / 2],
    });
  }

  found.sort((first, second) => second.confidence - first.confidence);
  const kept = [];
  for (const detection of found) {
    const duplicate = kept.some((other) => other.label === detection.label
      && boxIou(other.box, detection.box) > DETECTOR_IOU_LIMIT);
    if (!duplicate) kept.push(detection);
  }
  return kept;
}

// Combines the two models' detections (see the top of this file).
// cocoLabels: YOLO26's 80 names, used to tell which everyday names it also knows.
function mergeDetections(everyday, coco, cocoLabels) {
  const cocoNames = new Set(cocoLabels.map((name) => COCO_TO_EVERYDAY.get(name) || name));
  const merged = everyday.map((detection) => ({ ...detection, source: "everyday" }));
  for (const detection of coco) {
    const label = COCO_TO_EVERYDAY.get(detection.label) || detection.label;
    let match = null;
    let matchIou = 0;
    for (const candidate of merged) {
      const iou = boxIou(candidate.box, detection.box);
      if (iou > matchIou) {
        match = candidate;
        matchIou = iou;
      }
    }
    if (match && matchIou >= SAME_OBJECT_IOU) {
      const yolo26KnowsIt = cocoNames.has(match.label);
      if (yolo26KnowsIt && (match.source === "everyday" || detection.confidence > match.confidence)) {
        Object.assign(match, { label, confidence: detection.confidence, source: "coco" });
      }
    } else {
      merged.push({ label, confidence: detection.confidence, box: detection.box, source: "coco" });
    }
  }
  return merged;
}

// Returns { closest, objects }: the largest non-person box (best guess for the
// closest object) and every distinct object label, biggest first.
function summarizeDetections(detections) {
  const things = detections
    .filter((detection) => !DETECTOR_HUMAN_LABELS.has(detection.label))
    .sort((first, second) => boxArea(second.box) - boxArea(first.box));
  return {
    closest: things[0] || null,
    objects: [...new Set(things.map((detection) => detection.label))],
  };
}

async function runModel({ session, labels, minScore }, tensor, scale) {
  const results = await session.run({ [session.inputNames[0]]: tensor });
  const output = results[session.outputNames[0]];
  return decodeDetections(output.data, output.dims[2], scale, labels, minScore);
}

async function detectObjects(blob) {
  const [{ everyday, coco }, bitmap] = await Promise.all([loadDetector(), createImageBitmap(blob)]);
  try {
    const scale = DETECTOR_INPUT_SIZE / Math.max(bitmap.width, bitmap.height);
    const canvas = document.createElement("canvas");
    canvas.width = DETECTOR_INPUT_SIZE;
    canvas.height = DETECTOR_INPUT_SIZE;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    context.fillStyle = "rgb(114, 114, 114)";
    context.fillRect(0, 0, DETECTOR_INPUT_SIZE, DETECTOR_INPUT_SIZE);
    context.drawImage(bitmap, 0, 0, Math.round(bitmap.width * scale), Math.round(bitmap.height * scale));

    const pixels = context.getImageData(0, 0, DETECTOR_INPUT_SIZE, DETECTOR_INPUT_SIZE).data;
    const planeSize = DETECTOR_INPUT_SIZE * DETECTOR_INPUT_SIZE;
    const input = new Float32Array(3 * planeSize);
    for (let pixel = 0; pixel < planeSize; pixel += 1) {
      input[pixel] = pixels[pixel * 4] / 255;
      input[planeSize + pixel] = pixels[pixel * 4 + 1] / 255;
      input[2 * planeSize + pixel] = pixels[pixel * 4 + 2] / 255;
    }

    const tensor = new ort.Tensor("float32", input, [1, 3, DETECTOR_INPUT_SIZE, DETECTOR_INPUT_SIZE]);
    const everydayFound = await runModel(everyday, tensor, scale);
    const detections = coco
      ? mergeDetections(everydayFound, await runModel(coco, tensor, scale), coco.labels)
      : everydayFound;
    return summarizeDetections(detections);
  } finally {
    bitmap.close();
  }
}

// Crops the photo around one detection (with a little padding) for the cloud describer.
async function cropDetection(blob, detection) {
  const bitmap = await createImageBitmap(blob);
  try {
    const [x1, y1, x2, y2] = detection.box;
    const padX = Math.max(12, (x2 - x1) * 0.08);
    const padY = Math.max(12, (y2 - y1) * 0.08);
    const left = Math.max(0, Math.floor(x1 - padX));
    const top = Math.max(0, Math.floor(y1 - padY));
    const right = Math.min(bitmap.width, Math.ceil(x2 + padX));
    const bottom = Math.min(bitmap.height, Math.ceil(y2 + padY));
    if (right <= left || bottom <= top) return blob;
    const canvas = document.createElement("canvas");
    canvas.width = right - left;
    canvas.height = bottom - top;
    canvas.getContext("2d").drawImage(bitmap, left, top, canvas.width, canvas.height, 0, 0, canvas.width, canvas.height);
    return canvasToJpeg(canvas);
  } finally {
    bitmap.close();
  }
}
