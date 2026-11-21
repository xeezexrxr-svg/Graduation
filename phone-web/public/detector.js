"use strict";

// On-device object detection with the same YOLO26 model the desktop app uses.
const ORT_VERSION = "1.20.1";
const DETECTOR_MODEL_URL = "/models/yolo26n.onnx";
const DETECTOR_INPUT_SIZE = 640;
const DETECTOR_MIN_SCORE = 0.3;
const DETECTOR_IOU_LIMIT = 0.45;
const DETECTOR_HUMAN_LABELS = new Set(["person"]);
const COCO_LABELS = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"];

let detectorSession = null;

function loadDetector() {
  if (!detectorSession) {
    if (!globalThis.ort) {
      return Promise.reject(new Error("The object detector library did not load."));
    }
    ort.env.wasm.wasmPaths = `https://cdn.jsdelivr.net/npm/onnxruntime-web@${ORT_VERSION}/dist/`;
    ort.env.wasm.numThreads = 1;
    detectorSession = ort.InferenceSession.create(DETECTOR_MODEL_URL, {
      executionProviders: ["wasm"],
    }).catch((error) => {
      detectorSession = null;
      throw error;
    });
  }
  return detectorSession;
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

// output: model data shaped [84, candidates] (cx, cy, w, h, then 80 class scores).
// scale: how much the photo was shrunk to fit the 640px model input.
function decodeDetections(output, candidates, scale) {
  const classCount = COCO_LABELS.length;
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
    if (bestScore < DETECTOR_MIN_SCORE) continue;
    const centerX = output[index] / scale;
    const centerY = output[candidates + index] / scale;
    const width = output[2 * candidates + index] / scale;
    const height = output[3 * candidates + index] / scale;
    found.push({
      label: COCO_LABELS[bestClass],
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

async function detectObjects(blob) {
  const [session, bitmap] = await Promise.all([loadDetector(), createImageBitmap(blob)]);
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
    const results = await session.run({ [session.inputNames[0]]: tensor });
    const output = results[session.outputNames[0]];
    return summarizeDetections(decodeDetections(output.data, output.dims[2], scale));
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
