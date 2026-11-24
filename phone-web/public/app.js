"use strict";

const MAX_IMAGE_SIDE = 1280;
const MAX_OCR_IMAGE_SIDE = 2400;
const JPEG_QUALITY = 0.82;
// Below this on-device confidence, a name is presented as a guess ("might be").
const UNSURE_BELOW = 0.6;

const menuToggle = document.querySelector("#menuToggle");
const featureMenu = document.querySelector("#featureMenu");
const screenLinks = document.querySelectorAll("[data-screen-target]");
const cameraButton = document.querySelector("#cameraButton");
const photoButton = document.querySelector("#photoButton");
const photoInput = document.querySelector("#photoInput");
const scanButton = document.querySelector("#scanButton");
const cameraVideo = document.querySelector("#cameraVideo");
const photoPreview = document.querySelector("#photoPreview");
const cameraPlaceholder = document.querySelector("#cameraPlaceholder");
const cameraTip = document.querySelector("#cameraTip");
const captureCanvas = document.querySelector("#captureCanvas");
const scanStatus = document.querySelector("#scanStatus");
const resultContent = document.querySelector("#resultContent");
const readButton = document.querySelector("#readButton");
const stopButton = document.querySelector("#stopButton");
const textCameraButton = document.querySelector("#textCameraButton");
const textCameraVideo = document.querySelector("#textCameraVideo");
const textPhotoPreview = document.querySelector("#textPhotoPreview");
const textCameraPlaceholder = document.querySelector("#textCameraPlaceholder");
const textPhotoInput = document.querySelector("#textPhotoInput");
const scanTextButton = document.querySelector("#scanTextButton");
const textPhotoButton = document.querySelector("#textPhotoButton");
const textScanActions = document.querySelector("#textScanActions");
const readTextButton = document.querySelector("#readTextButton");
const copyTextButton = document.querySelector("#copyTextButton");
const recognizedText = document.querySelector("#recognizedText");
const textReadingPreview = document.querySelector("#textReadingPreview");
const textScanStatus = document.querySelector("#textScanStatus");
const fontSizeInput = document.querySelector("#fontSize");
const letterSpacingInput = document.querySelector("#letterSpacing");
const speechRateInput = document.querySelector("#speechRate");
const voiceChoice = document.querySelector("#voiceChoice");
const rulerViewButton = document.querySelector("#rulerViewButton");
const rulerControls = document.querySelector("#rulerControls");
const rulerPrevButton = document.querySelector("#rulerPrevButton");
const rulerNextButton = document.querySelector("#rulerNextButton");
const rulerLinesInput = document.querySelector("#rulerLines");
const rulerAwayInput = document.querySelector("#rulerAway");
const cameraView = document.querySelector("#cameraView");
const textCameraView = document.querySelector("#textCameraView");
const textCameraTip = document.querySelector("#textCameraTip");
const autoCaptureInput = document.querySelector("#autoCapture");
const retryButton = document.querySelector("#retryButton");
const historyCard = document.querySelector("#historyCard");
const historyList = document.querySelector("#historyList");
const lineSpacingInput = document.querySelector("#lineSpacing");
const readingFontInput = document.querySelector("#readingFont");
const autoReadInput = document.querySelector("#autoRead");

let cameraStream = null;
let textCameraStream = null;
let textCameraRequestId = 0;
let selectedImage = null;
let selectedImageUrl = null;
let textSelectedImage = null;
let textSelectedImageUrl = null;
let currentDescription = "";
let wordElements = [];
let activeWord = null;
let textPreviewWords = [];
let activeTextPreviewWord = null;
let speechVoices = [];
let textOcrWorkerPromise = null;
let textOcrWorkerLanguage = null;
// Text-reader language files for each choice. English is always included because
// Chinese pages often contain English words and numbers. Reading a page with the
// wrong kind of Chinese costs about 20 points of accuracy (evaluation, 2026-11-22).
const OCR_LANGUAGES = {
  eng: { codes: ["eng"], name: "English" },
  chi_tra: { codes: ["eng", "chi_tra"], name: "Traditional Chinese" },
  chi_sim: { codes: ["eng", "chi_sim"], name: "Simplified Chinese" },
};
let textScanInProgress = false;
let activeSpeechMode = null;
let activeSpeechState = null;
let speechRequestId = 0;
let rulerView = false;
let rulerLines = [];
let rulerIndex = 0;
let rulerParts = null;
let stopCameraWatch = null;
let stopTextCameraWatch = null;
// The last scan of the current photo, so "Not right? Try again" can look again.
let lastScan = null;
// Results from this visit, newest first. Kept in memory only, never saved.
const recentScans = [];
const RECENT_SCANS_KEPT = 10;

// Short built-in descriptions, shared with the desktop app. Used when the cloud
// can't describe the object; until the file loads, a general sentence is used.
let descriptions = {};
fetch("/object_descriptions.json")
  .then((response) => (response.ok ? response.json() : {}))
  .then((loaded) => {
    descriptions = Object.fromEntries(
      Object.entries(loaded).map(([name, text]) => [name.trim().toLowerCase(), text]),
    );
  })
  .catch((error) => console.error("Could not load object descriptions", error));

function setStatus(message, kind = "info") {
  scanStatus.textContent = message;
  scanStatus.dataset.kind = kind;
}

function setTextScanStatus(message, kind = "info") {
  textScanStatus.textContent = message;
  textScanStatus.dataset.kind = kind;
}

function updateTextScanControls() {
  scanTextButton.disabled = textScanInProgress || !textSelectedImage;
  textCameraButton.disabled = textScanInProgress;
  textPhotoButton.disabled = textScanInProgress;
  const hasText = Boolean(recognizedText.value.trim());
  const isReadingText = activeSpeechMode === "text";
  // The buttons only appear once there is text to act on.
  textScanActions.hidden = !hasText && !rulerView;
  readTextButton.disabled = !("speechSynthesis" in window);
  if (isReadingText) readTextButton.textContent = "Stop";
  else if (rulerView) readTextButton.textContent = "Read from this line";
  else readTextButton.textContent = hasWordsSelected() ? "Read selected words" : "Read all aloud";
  copyTextButton.textContent = hasWordsSelected() ? "Copy selected" : "Copy all";
}

// While reading, the box's selection is just the highlighted word, and in
// ruler view the box is hidden, so neither counts as the user's selection.
function hasWordsSelected() {
  return activeSpeechMode !== "text"
    && !rulerView
    && recognizedText.selectionStart !== recognizedText.selectionEnd;
}

function closeFeatureMenu() {
  featureMenu.hidden = true;
  menuToggle.setAttribute("aria-expanded", "false");
  menuToggle.setAttribute("aria-label", "Open feature menu");
}

function showAppScreen(screenId) {
  const screens = document.querySelectorAll(".app-screen");
  for (const screen of screens) {
    screen.hidden = screen.id !== screenId;
  }
  for (const link of screenLinks) {
    if (link.dataset.screenTarget === screenId && link.matches("button")) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  }
  if (screenId === "objectReaderScreen") {
    stopTextCamera();
  } else {
    stopCamera();
  }
  closeFeatureMenu();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function releaseSelectedImage() {
  if (selectedImageUrl) {
    URL.revokeObjectURL(selectedImageUrl);
    selectedImageUrl = null;
  }
}

function showSelectedImage(blob) {
  releaseSelectedImage();
  selectedImage = blob;
  selectedImageUrl = URL.createObjectURL(blob);
  photoPreview.src = selectedImageUrl;
  photoPreview.hidden = false;
  cameraVideo.hidden = true;
  cameraPlaceholder.hidden = true;
  scanButton.disabled = false;
  lastScan = null;
  retryButton.hidden = true;
}

// Light, zoom and tap-to-focus, on phones whose camera offers them to websites
// (mostly Android Chrome; iPhones offer none, so the controls stay hidden there).
function attachCameraTools(view, video, stream) {
  const track = stream.getVideoTracks()[0];
  const offers = track?.getCapabilities?.() || {};
  const tools = view.querySelector(".camera-tools");
  const torch = tools.querySelector('[data-tool="torch"]');
  const zoomControl = tools.querySelector(".camera-zoom");
  const zoom = zoomControl.querySelector("input");
  const ring = view.querySelector(".focus-ring");
  const setting = (constraint) => track.applyConstraints({ advanced: [constraint] });

  torch.hidden = !offers.torch;
  torch.setAttribute("aria-pressed", "false");
  torch.textContent = "Light on";
  torch.onclick = async () => {
    const on = torch.getAttribute("aria-pressed") !== "true";
    try {
      await setting({ torch: on });
      torch.setAttribute("aria-pressed", String(on));
      torch.textContent = on ? "Light off" : "Light on";
    } catch (error) {
      console.warn("Could not switch the light", error);
    }
  };

  zoomControl.hidden = !offers.zoom;
  if (offers.zoom) {
    zoom.min = offers.zoom.min;
    zoom.max = offers.zoom.max;
    zoom.step = offers.zoom.step || 0.1;
    zoom.value = track.getSettings().zoom ?? offers.zoom.min;
    zoom.oninput = () => setting({ zoom: Number(zoom.value) }).catch(() => {});
  }
  tools.hidden = torch.hidden && zoomControl.hidden;

  const focusModes = Array.isArray(offers.focusMode) ? offers.focusMode : [];
  ring.hidden = true;
  video.onclick = async (event) => {
    if (!focusModes.length || !video.videoWidth) return;
    // The video is shown whole ("contain"), so leave out the bars around it.
    const box = video.getBoundingClientRect();
    const scale = Math.min(box.width / video.videoWidth, box.height / video.videoHeight);
    const shownWidth = video.videoWidth * scale;
    const shownHeight = video.videoHeight * scale;
    const x = (event.clientX - box.left - (box.width - shownWidth) / 2) / shownWidth;
    const y = (event.clientY - box.top - (box.height - shownHeight) / 2) / shownHeight;
    if (x < 0 || x > 1 || y < 0 || y > 1) return;
    try {
      await setting({
        pointsOfInterest: [{ x, y }],
        focusMode: focusModes.includes("single-shot") ? "single-shot" : focusModes[0],
      });
      ring.style.left = `${event.clientX - box.left}px`;
      ring.style.top = `${event.clientY - box.top}px`;
      ring.hidden = false;
      setTimeout(() => { ring.hidden = true; }, 900);
    } catch (error) {
      console.warn("This camera can't focus on a tapped point", error);
    }
  };
}

function hideCameraTools(view, video) {
  view.querySelector(".camera-tools").hidden = true;
  view.querySelector(".focus-ring").hidden = true;
  video.onclick = null;
}

// While the camera is on, checks the picture a few times a second with the same
// blur and dark test as a taken photo, and says what to fix. With onSteady, calls
// it once the picture has stayed sharp for about two seconds (auto photo).
const LIVE_CHECK_MS = 400;
const SHARP_CHECKS_BEFORE_PHOTO = 5;
const LIVE_TIPS = {
  dark: "Too dark. Add light.",
  blurry: "Hold still. Keep it in the frame.",
};

function watchCamera(video, tip, sharpTip, onSteady = null) {
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d", { willReadFrequently: true });
  let sharpChecks = 0;
  const timer = setInterval(() => {
    if (!video.videoWidth || document.hidden) return;
    const scale = PHOTO_CHECK_SIDE / Math.max(video.videoWidth, video.videoHeight);
    canvas.width = Math.max(3, Math.round(video.videoWidth * scale));
    canvas.height = Math.max(3, Math.round(video.videoHeight * scale));
    context.imageSmoothingQuality = "high";
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    const problem = photoProblem(pixels, canvas.width, canvas.height);
    sharpChecks = problem ? 0 : sharpChecks + 1;
    const message = problem ? LIVE_TIPS[problem] : onSteady ? "Sharp. Hold still, taking the photo…" : sharpTip;
    if (tip.textContent !== message) tip.textContent = message;
    if (onSteady && sharpChecks >= SHARP_CHECKS_BEFORE_PHOTO) {
      clearInterval(timer);
      onSteady();
    }
  }, LIVE_CHECK_MS);
  return () => clearInterval(timer);
}

// Also re-run when Auto photo is switched while the camera is on.
function watchObjectCamera() {
  stopCameraWatch?.();
  stopCameraWatch = watchCamera(
    cameraVideo,
    cameraTip,
    "Sharp. Tap Capture photo.",
    autoCaptureInput.checked ? capturePhoto : null,
  );
}

function stopCamera() {
  stopCameraWatch?.();
  stopCameraWatch = null;
  hideCameraTools(cameraView, cameraVideo);
  if (cameraStream) {
    for (const track of cameraStream.getTracks()) {
      track.stop();
    }
    cameraStream = null;
  }
  cameraVideo.srcObject = null;
  cameraVideo.hidden = true;
  cameraTip.hidden = true;
  cameraButton.textContent = "Start camera";
  if (!selectedImage) {
    cameraPlaceholder.hidden = false;
  }
}

async function startCamera() {
  if (cameraStream) {
    stopCamera();
    if (!selectedImage) {
      cameraPlaceholder.hidden = false;
    }
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    setStatus("Camera access is not available in this browser. Choose a photo instead.", "error");
    photoInput.click();
    return;
  }
  try {
    stopCamera();
    releaseSelectedImage();
    selectedImage = null;
    scanButton.disabled = true;
    cameraPlaceholder.hidden = true;
    photoPreview.hidden = true;
    cameraStream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: { ideal: "environment" },
        width: { ideal: 1280 },
        height: { ideal: 960 },
      },
    });
    cameraVideo.srcObject = cameraStream;
    cameraVideo.hidden = false;
    cameraTip.hidden = false;
    cameraButton.textContent = "Capture photo";
    await cameraVideo.play();
    attachCameraTools(cameraView, cameraVideo, cameraStream);
    watchObjectCamera();
    setStatus(autoCaptureInput.checked
      ? "Camera ready. Hold one item still and the photo is taken by itself."
      : "Camera ready. Center one item, then capture it.", "success");
  } catch (error) {
    stopCamera();
    cameraPlaceholder.hidden = false;
    const message = error.name === "NotAllowedError"
      ? "Camera permission was denied. Allow access in your browser settings or choose a photo."
      : "Could not start the camera. Choose a photo or check your browser's camera permission.";
    setStatus(message, "error");
  }
}

function canvasToJpeg(canvas, quality = JPEG_QUALITY) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob);
      } else {
        reject(new Error("Could not prepare that image."));
      }
    }, "image/jpeg", quality);
  });
}

async function captureVideoJpeg(video, maxSide, quality) {
  const scale = Math.min(
    1,
    maxSide / Math.max(video.videoWidth, video.videoHeight),
  );
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
  canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("This browser could not prepare the camera image.");
  }
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvasToJpeg(canvas, quality);
}

async function capturePhoto() {
  if (!cameraStream || !cameraVideo.videoWidth || !cameraVideo.videoHeight) {
    setStatus("Wait for the camera preview, then try capturing again.", "error");
    return;
  }
  try {
    const image = await captureVideoJpeg(cameraVideo, MAX_IMAGE_SIDE, JPEG_QUALITY);
    showSelectedImage(image);
    stopCamera();
  } catch (error) {
    setStatus(error.message, "error");
    return;
  }
  await checkThenScan();
}

const PHOTO_PROBLEMS = {
  blurry: "This photo looks blurry. Hold still and take it again.",
  dark: "This photo is too dark. Add light and take it again.",
};

// A new photo is identified straight away, unless it's clearly unusable; then
// Identify object stays available to try it anyway.
async function checkThenScan() {
  const problem = await checkPhoto(selectedImage).catch(() => null);
  if (problem) {
    setStatus(PHOTO_PROBLEMS[problem], "warning");
    return;
  }
  await scanImage();
}

function loadImage(blob) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    const imageUrl = URL.createObjectURL(blob);
    image.onload = () => {
      URL.revokeObjectURL(imageUrl);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(imageUrl);
      reject(new Error("That photo could not be opened. Try another image."));
    };
    image.src = imageUrl;
  });
}

async function preparePhoto(file) {
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    setStatus("Choose an image file to scan.", "error");
    return;
  }
  setStatus("Preparing photo…");
  try {
    const image = await loadImage(file);
    const scale = Math.min(1, MAX_IMAGE_SIDE / Math.max(image.naturalWidth, image.naturalHeight));
    captureCanvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    captureCanvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    const context = captureCanvas.getContext("2d");
    if (!context) {
      throw new Error("This browser could not prepare that photo.");
    }
    context.drawImage(image, 0, 0, captureCanvas.width, captureCanvas.height);
    showSelectedImage(await canvasToJpeg(captureCanvas));
    stopCamera();
  } catch (error) {
    setStatus(error.message, "error");
    return;
  } finally {
    photoInput.value = "";
  }
  await checkThenScan();
}

function releaseTextSelectedImage() {
  if (textSelectedImageUrl) {
    URL.revokeObjectURL(textSelectedImageUrl);
    textSelectedImageUrl = null;
  }
}

function showTextSelectedImage(image) {
  releaseTextSelectedImage();
  textSelectedImage = image;
  textSelectedImageUrl = URL.createObjectURL(image);
  textPhotoPreview.src = textSelectedImageUrl;
  textPhotoPreview.hidden = false;
  textCameraVideo.hidden = true;
  textCameraPlaceholder.hidden = true;
  updateTextScanControls();
}

function stopTextCamera() {
  textCameraRequestId += 1;
  stopTextCameraWatch?.();
  stopTextCameraWatch = null;
  hideCameraTools(textCameraView, textCameraVideo);
  textCameraTip.hidden = true;
  if (textCameraStream) {
    for (const track of textCameraStream.getTracks()) {
      track.stop();
    }
    textCameraStream = null;
  }
  textCameraVideo.srcObject = null;
  textCameraVideo.hidden = true;
  textCameraButton.textContent = "Start camera";
  if (!textSelectedImage) {
    textCameraPlaceholder.hidden = false;
  }
}

async function startTextCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    setTextScanStatus("Camera access is not available in this browser. Choose a photo instead.", "error");
    textPhotoInput.click();
    return;
  }
  try {
    stopTextCamera();
    const requestId = textCameraRequestId;
    releaseTextSelectedImage();
    textSelectedImage = null;
    textPhotoPreview.hidden = true;
    textCameraPlaceholder.hidden = true;
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: { ideal: "environment" },
        width: { ideal: 1920 },
        height: { ideal: 1080 },
      },
    });
    if (requestId !== textCameraRequestId || document.querySelector("#textScannerScreen").hidden) {
      for (const track of stream.getTracks()) {
        track.stop();
      }
      return;
    }
    textCameraStream = stream;
    textCameraVideo.srcObject = textCameraStream;
    textCameraVideo.hidden = false;
    textCameraButton.textContent = "Capture page";
    await textCameraVideo.play();
    attachCameraTools(textCameraView, textCameraVideo, textCameraStream);
    textCameraTip.hidden = false;
    stopTextCameraWatch = watchCamera(textCameraVideo, textCameraTip, "Sharp. Tap Capture page.");
    updateTextScanControls();
    setTextScanStatus("Camera ready. Frame the page, then capture it.", "success");
  } catch (error) {
    stopTextCamera();
    const message = error.name === "NotAllowedError"
      ? "Camera permission was denied. Allow access in your browser settings or choose a photo."
      : "Could not start the camera. Choose a photo or check your browser's camera permission.";
    setTextScanStatus(message, "error");
  }
}

async function captureTextPhoto() {
  if (!textCameraStream || !textCameraVideo.videoWidth || !textCameraVideo.videoHeight) {
    setTextScanStatus("Wait for the camera preview, then try capturing again.", "error");
    return;
  }
  try {
    setTextScanStatus("Capturing a high-resolution page photo…");
    const image = await captureVideoJpeg(textCameraVideo, MAX_OCR_IMAGE_SIDE, 0.9);
    showTextSelectedImage(image);
    stopTextCamera();
    setTextScanStatus("Page photo ready. Choose Scan text to recognize it.", "success");
  } catch (error) {
    setTextScanStatus(error.message || "Could not capture the page photo.", "error");
  }
}

function prepareTextPhoto(file) {
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    setTextScanStatus("Choose an image file to scan.", "error");
    textPhotoInput.value = "";
    return;
  }
  stopTextCamera();
  showTextSelectedImage(file);
  setTextScanStatus("Photo ready. Choose Scan text to recognize it.", "success");
  textPhotoInput.value = "";
}

function splitIntoWords(text) {
  return [...text.matchAll(READING_WORD)].map((match) => ({
    start: match.index,
    end: match.index + match[0].length,
    text: match[0],
  }));
}

function sentenceRangeAt(text, index) {
  const pattern = /[^.!?。！？\n]+[.!?。！？]*|[.!?。！？]+/gu;
  for (const match of text.matchAll(pattern)) {
    if (match.index <= index && index < match.index + match[0].length) {
      return { start: match.index, end: match.index + match[0].length };
    }
  }
  return { start: 0, end: text.length };
}

// Wraps text in sentence and word spans so read-aloud can highlight them.
// Chinese characters count as separate words (Chinese voices report them one by
// one). Appends to `parent` and returns the words with their elements.
const READING_WORD = /\p{Script=Han}|[\p{L}\p{N}_]+(?:['’][\p{L}\p{N}_]+)*/gu;

function renderReadableText(parent, text) {
  const sentences = new Map();
  const words = [];
  for (const match of text.matchAll(READING_WORD)) {
    const range = sentenceRangeAt(text, match.index);
    const key = `${range.start}:${range.end}`;
    if (!sentences.has(key)) {
      const element = document.createElement("span");
      element.className = "reading-sentence";
      sentences.set(key, { ...range, element, words: [] });
    }
    const sentence = sentences.get(key);
    const element = document.createElement("span");
    element.textContent = match[0];
    element.dataset.word = "";
    const word = {
      start: match.index,
      end: match.index + match[0].length,
      text: match[0],
      element,
      sentenceElement: sentence.element,
    };
    sentence.words.push(word);
    words.push(word);
  }

  // Assemble in order, keeping the spaces and punctuation between words.
  let cursor = 0;
  for (const sentence of [...sentences.values()].sort((left, right) => left.start - right.start)) {
    if (sentence.start > cursor) parent.append(text.slice(cursor, sentence.start));
    let inner = sentence.start;
    for (const word of sentence.words) {
      if (word.start > inner) sentence.element.append(text.slice(inner, word.start));
      sentence.element.append(word.element);
      inner = word.end;
    }
    if (inner < sentence.end) sentence.element.append(text.slice(inner, sentence.end));
    parent.append(sentence.element);
    cursor = sentence.end;
  }
  if (cursor < text.length) parent.append(text.slice(cursor));
  return words;
}

function renderTextReadingPreview(text) {
  textReadingPreview.style.height = `${recognizedText.offsetHeight}px`;
  textReadingPreview.replaceChildren();
  textReadingPreview.scrollTop = 0;
  textPreviewWords = renderReadableText(textReadingPreview, text);
  recognizedText.hidden = true;
  textReadingPreview.hidden = false;
  attachRuler();
}

function updateTextReadingBoundary(charIndex) {
  const word = textPreviewWords.find((item) => charIndex >= item.start && charIndex < item.end)
    ?? textPreviewWords.find((item) => item.start >= charIndex);
  if (!word || word === activeTextPreviewWord) return;
  if (activeTextPreviewWord) {
    activeTextPreviewWord.element.classList.remove("reading-word");
    activeTextPreviewWord.sentenceElement.classList.remove("reading-sentence-active");
  }
  activeTextPreviewWord = word;
  word.element.classList.add("reading-word");
  word.sentenceElement.classList.add("reading-sentence-active");
  if (!followWithRuler(word)) {
    word.element.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
}

function clearTextHighlights() {
  if (activeTextPreviewWord) {
    activeTextPreviewWord.element.classList.remove("reading-word");
    activeTextPreviewWord.sentenceElement.classList.remove("reading-sentence-active");
  }
  activeTextPreviewWord = null;
}

function clearTextReadingPreview() {
  clearTextHighlights();
  textPreviewWords = [];
  rulerLines = [];
  rulerParts = null;
  rulerControls.hidden = true;
  delete textReadingPreview.dataset.ruler;
  textReadingPreview.replaceChildren();
  textReadingPreview.style.height = "";
  textReadingPreview.hidden = true;
  recognizedText.hidden = false;
}

// Reading ruler: keeps the reader's place one line (or a few) at a time on a
// scanned page. It follows read-aloud, and can be moved by tapping a line, the
// Previous/Next line buttons, or the arrow keys.
function rulerSize() {
  return Number(rulerLinesInput.value) || 0;
}

function attachRuler() {
  const part = (className) => {
    const element = document.createElement("div");
    element.className = className;
    element.setAttribute("aria-hidden", "true");
    return element;
  };
  rulerParts = { band: part("ruler-band"), above: part("ruler-mask"), below: part("ruler-mask") };
  textReadingPreview.append(rulerParts.above, rulerParts.below, rulerParts.band);
  textReadingPreview.dataset.away = rulerAwayInput.value;
  rulerIndex = 0;
  measureRulerLines();
  drawRuler();
}

function measureRulerLines() {
  rulerLines = [];
  for (const word of textPreviewWords) {
    const top = word.element.offsetTop;
    const bottom = top + word.element.offsetHeight;
    const line = rulerLines[rulerLines.length - 1];
    if (line && Math.abs(line.top - top) < 6) {
      line.bottom = Math.max(line.bottom, bottom);
      line.words.push(word);
    } else {
      rulerLines.push({ top, bottom, words: [word] });
    }
  }
}

function drawRuler() {
  const size = rulerSize();
  const showing = Boolean(rulerParts) && size > 0 && rulerLines.length > 0 && !textReadingPreview.hidden;
  if (showing) textReadingPreview.dataset.ruler = "";
  else delete textReadingPreview.dataset.ruler;
  rulerControls.hidden = !(showing && rulerView);
  if (!showing) return;

  rulerIndex = Math.max(0, Math.min(rulerIndex, rulerLines.length - 1));
  const first = rulerLines[rulerIndex];
  const last = rulerLines[Math.min(rulerLines.length - 1, rulerIndex + size - 1)];
  const top = Math.max(0, first.top - 4);
  const bottom = last.bottom + 4;
  const { band, above, below } = rulerParts;
  band.style.top = `${top}px`;
  band.style.height = `${bottom - top}px`;
  above.style.top = "0px";
  above.style.height = `${top}px`;
  below.style.height = "0px"; // measure the page without the old mask
  below.style.top = `${bottom}px`;
  below.style.height = `${Math.max(0, textReadingPreview.scrollHeight - bottom)}px`;
  rulerPrevButton.disabled = rulerIndex === 0;
  rulerNextButton.disabled = rulerIndex + size >= rulerLines.length;

  const view = textReadingPreview;
  if (top < view.scrollTop || bottom > view.scrollTop + view.clientHeight) {
    view.scrollTo({
      top: Math.max(0, top - view.clientHeight / 3),
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
  }
}

function moveRuler(index) {
  rulerIndex = index;
  drawRuler();
}

// Moves the ruler to the spoken word's line. Returns false if the ruler is off.
function followWithRuler(word) {
  if (!rulerParts || rulerSize() === 0 || !rulerLines.length) return false;
  const index = rulerLines.findIndex((line) => line.words.includes(word));
  if (index >= 0 && (index < rulerIndex || index >= rulerIndex + rulerSize())) moveRuler(index);
  return true;
}

function refreshRuler() {
  if (textReadingPreview.hidden || !textPreviewWords.length) return;
  measureRulerLines();
  drawRuler();
}

function setRulerView(on) {
  rulerView = on;
  rulerViewButton.setAttribute("aria-pressed", String(on));
  rulerViewButton.textContent = on ? "Edit text" : "Ruler view";
  if (on) {
    if (activeSpeechMode !== "text") renderTextReadingPreview(recognizedText.value);
    drawRuler();
    if (rulerSize() === 0) {
      setTextScanStatus("The reading ruler is off. Turn it on in Reading preferences.", "info");
    }
  } else if (activeSpeechMode === "text") {
    stopReading();
  } else {
    clearTextReadingPreview();
  }
  updateTextScanControls();
}

// Shows the result in blocks: what it is, then what the label suggests. Read
// aloud speaks the blocks in order, each with a short lead-in, and highlights the words.
// unsure: the name is only a low-confidence guess, so say "might be", not "is".
function renderResult(result) {
  const { label, explanation, product, unsure } = result;
  const article = /^[aeiou]/i.test(label) ? "an" : "a";
  const blocks = [
    { body: `This ${unsure ? "might be" : "is"} ${article} ${label}. ${explanation}` },
    product && { heading: "The label suggests", lead: "The label suggests this is ", body: product },
  ].filter(Boolean);

  activeWord = null;
  resultContent.replaceChildren();
  const title = document.createElement("h3");
  title.className = "object-title";
  title.tabIndex = -1; // so focus can move here and screen readers announce the result
  title.textContent = label;
  if (unsure) {
    const question = document.createElement("span");
    question.setAttribute("aria-hidden", "true");
    question.textContent = "?";
    const maybe = document.createElement("span");
    maybe.className = "visually-hidden";
    maybe.textContent = ", maybe";
    title.append(question, maybe);
  }
  resultContent.append(title);

  currentDescription = "";
  wordElements = [];
  for (const block of blocks) {
    const section = document.createElement("div");
    section.className = "result-block";
    if (block.heading) {
      const heading = document.createElement("h4");
      heading.className = "result-block-heading";
      heading.textContent = block.heading;
      section.append(heading);
    }
    const paragraph = document.createElement("p");
    paragraph.className = "object-description";
    if (currentDescription) currentDescription += " ";
    const offset = currentDescription.length + (block.lead || "").length;
    for (const word of renderReadableText(paragraph, block.body)) {
      wordElements.push({ ...word, start: word.start + offset, end: word.end + offset });
    }
    // End each block with a full stop, so the voice pauses between them.
    currentDescription += `${block.lead || ""}${block.body}${/[.!?。！？]$/.test(block.body) ? "" : "."}`;
    section.append(paragraph);
    resultContent.append(section);
  }
  readButton.disabled = !("speechSynthesis" in window);
}

// Recent scans of this visit: tap one to see and hear it again.
function rememberScan(result) {
  recentScans.unshift({ result, time: new Date() });
  recentScans.length = Math.min(recentScans.length, RECENT_SCANS_KEPT);
  historyList.replaceChildren(...recentScans.map((scan) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    const name = document.createElement("span");
    name.textContent = scan.result.label;
    const time = document.createElement("time");
    time.dateTime = scan.time.toISOString();
    time.textContent = scan.time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    button.append(name, time);
    button.addEventListener("click", () => {
      stopReading();
      renderResult(scan.result);
      retryButton.hidden = true;
      setStatus(`Showing an earlier scan: ${scan.result.label}.`, "info");
      resultContent.querySelector(".object-title")?.focus();
    });
    item.append(button);
    return item;
  }));
  historyCard.hidden = false;
}

// Says one tapped word, in a voice that speaks its language, and marks it while speaking.
function speakWord(word) {
  if (!("speechSynthesis" in window)) return;
  stopReading();
  window.speechSynthesis.cancel();
  const chinese = /\p{Script=Han}/u.test(word.text);
  const utterance = new SpeechSynthesisUtterance(word.text);
  utterance.rate = Number(speechRateInput.value);
  const chosenVoice = voiceChoice.value === "" ? null : speechVoices[Number(voiceChoice.value)];
  const voice = voiceForRun({ chinese }, chosenVoice);
  if (voice) utterance.voice = voice;
  if (chinese) utterance.lang = voice?.lang || "zh-TW";
  const unmark = () => word.element.classList.remove("tapped-word");
  word.element.classList.add("tapped-word");
  utterance.onend = unmark;
  utterance.onerror = unmark;
  window.speechSynthesis.speak(utterance);
}

function updateSpeechBoundary(charIndex) {
  const word = wordElements.find((item) => charIndex >= item.start && charIndex < item.end)
    ?? wordElements.find((item) => item.start >= charIndex);
  if (!word || word === activeWord) return;
  if (activeWord) {
    activeWord.element.classList.remove("reading-word");
    activeWord.sentenceElement.classList.remove("reading-sentence-active");
  }
  activeWord = word;
  word.element.classList.add("reading-word");
  word.sentenceElement.classList.add("reading-sentence-active");
  word.element.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function findChineseVoice() {
  return speechVoices.find((voice) => /^zh[-_](TW|Hant)/i.test(voice.lang))
    || speechVoices.find((voice) => /^zh[-_]HK/i.test(voice.lang))
    || speechVoices.find((voice) => /^zh/i.test(voice.lang))
    || null;
}

// Reading preferences are remembered on this device. Storage can be blocked
// (private browsing), so every access is optional.
function loadSetting(name) {
  try {
    return localStorage.getItem(`clearview-${name}`);
  } catch {
    return null;
  }
}

function saveSetting(name, value) {
  try {
    localStorage.setItem(`clearview-${name}`, value);
  } catch {
    // Not saved; the setting still applies for this visit.
  }
}

function refreshVoices() {
  if (!("speechSynthesis" in window)) return;
  speechVoices = window.speechSynthesis.getVoices();
  const previousName = voiceChoice.value === ""
    ? loadSetting("voice")
    : speechVoices[Number(voiceChoice.value)]?.name;
  voiceChoice.replaceChildren(new Option("Default voice", ""));
  for (const [index, voice] of speechVoices.entries()) {
    const option = new Option(voice.name, String(index));
    voiceChoice.add(option);
  }
  const previousIndex = speechVoices.findIndex((voice) => voice.name === previousName);
  if (previousIndex >= 0) {
    voiceChoice.value = String(previousIndex);
  }
}

function readAloud() {
  if (!currentDescription || !("speechSynthesis" in window)) {
    setStatus("Text-to-speech is not available in this browser.", "error");
    return;
  }
  window.speechSynthesis.cancel();
  const requestId = ++speechRequestId;
  activeSpeechMode = "description";
  const selectedVoice = voiceChoice.value === ""
    ? null
    : speechVoices[Number(voiceChoice.value)];
  startSpeechUtterance({
    mode: "description",
    text: currentDescription,
    sourceStart: 0,
    offset: 0,
    voice: selectedVoice,
  }, 0, requestId);
  readButton.disabled = true;
  stopButton.disabled = false;
  if (scanStatus.dataset.kind !== "warning") setStatus("Reading the result aloud…", "success");
}

// Splits text (from `from` on) into runs of Chinese and non-Chinese writing, so
// each run can be read by a voice that speaks its language: an English voice
// silently skips Chinese characters, even mid-sentence ("The label reads: 烏龍茶").
// Pieces with no Latin letters (digits, punctuation, spaces) stay with the run
// before them, so "500 毫升" or "。" don't get a voice of their own.
const CHINESE_RUN = /[\p{Script=Han}　-〿＀-￯]+/gu;

function splitByLanguage(text, from = 0) {
  const pieces = [];
  let cursor = from;
  for (const match of text.slice(from).matchAll(CHINESE_RUN)) {
    const start = from + match.index;
    if (start > cursor) pieces.push({ start: cursor, end: start, chinese: false });
    pieces.push({ start, end: start + match[0].length, chinese: true });
    cursor = start + match[0].length;
  }
  if (cursor < text.length) pieces.push({ start: cursor, end: text.length, chinese: false });

  const runs = [];
  for (const piece of pieces) {
    const run = runs[runs.length - 1];
    const hasLatin = /[a-z]/i.test(text.slice(piece.start, piece.end));
    if (run && (run.chinese === piece.chinese || (!piece.chinese && !hasLatin))) {
      run.end = piece.end;
    } else {
      runs.push({ ...piece });
    }
  }
  return runs;
}

// The reader's chosen voice is used unless it can't speak the run's language.
function voiceForRun(run, chosenVoice) {
  const chosenSpeaksChinese = /^zh/i.test(chosenVoice?.lang || "");
  if (run.chinese && !chosenSpeaksChinese) return findChineseVoice();
  return chosenVoice;
}

function reportSpeechBoundary(state, charIndex, charLength) {
  state.offset = Math.min(state.text.length, charIndex);
  if (state.mode === "description") {
    updateSpeechBoundary(charIndex);
    return;
  }
  const boundaryLength = Number.isFinite(charLength) && charLength > 0
    ? charLength
    : splitIntoWords(state.text).find((word) => word.start <= charIndex && charIndex < word.end)?.end - charIndex || 1;
  recognizedText.setSelectionRange(
    state.sourceStart + charIndex,
    Math.min(state.sourceStart + state.text.length, state.sourceStart + charIndex + boundaryLength),
  );
  updateTextReadingBoundary(state.sourceStart + charIndex);
}

function endTextReading() {
  // Drop the last highlighted word, so the button doesn't switch to "Read selected words".
  recognizedText.setSelectionRange(recognizedText.selectionEnd, recognizedText.selectionEnd);
  if (rulerView) clearTextHighlights();
  else clearTextReadingPreview();
  updateTextScanControls();
}

function finishSpeech(state) {
  activeSpeechMode = null;
  activeSpeechState = null;
  if (state.mode === "description") {
    if (activeWord) {
      activeWord.element.classList.remove("reading-word");
      activeWord.sentenceElement.classList.remove("reading-sentence-active");
      activeWord = null;
    }
    readButton.disabled = false;
    stopButton.disabled = true;
    setStatus("Finished reading. You can listen again at any time.", "success");
  } else {
    endTextReading();
    setTextScanStatus("Finished reading the selected text.", "success");
  }
}

function failSpeech(state) {
  activeSpeechMode = null;
  activeSpeechState = null;
  if (state.mode === "description") {
    readButton.disabled = false;
    stopButton.disabled = true;
    setStatus("The browser could not read this explanation aloud.", "error");
  } else {
    endTextReading();
    setTextScanStatus("The browser could not read this text aloud.", "error");
  }
}

function startSpeechUtterance(state, offset, requestId) {
  if (!state.text.slice(offset).trim()) return;
  state.offset = offset;
  activeSpeechState = state;
  const isCurrent = () => requestId === speechRequestId && activeSpeechMode === state.mode;
  const runs = splitByLanguage(state.text, offset);
  let chineseWithoutVoice = false;

  // One utterance per language run; the browser plays them in order.
  runs.forEach((run, index) => {
    const utterance = new SpeechSynthesisUtterance(state.text.slice(run.start, run.end));
    utterance.rate = Number(speechRateInput.value);
    const voice = voiceForRun(run, state.voice);
    if (voice) utterance.voice = voice;
    if (run.chinese) {
      utterance.lang = voice?.lang || "zh-TW";
      if (!/^zh/i.test(voice?.lang || "")) chineseWithoutVoice = true;
    }
    // Some voices (such as Google's online ones) never report word boundaries,
    // so highlighting also moves at the start of every run.
    utterance.onstart = () => {
      if (isCurrent()) reportSpeechBoundary(state, run.start);
    };
    utterance.onboundary = (event) => {
      if (isCurrent()) {
        reportSpeechBoundary(state, run.start + Math.max(0, event.charIndex || 0), event.charLength);
      }
    };
    if (index === runs.length - 1) {
      utterance.onend = () => {
        if (isCurrent()) finishSpeech(state);
      };
    }
    utterance.onerror = (event) => {
      if (!isCurrent() || event.error === "canceled" || event.error === "interrupted") return;
      window.speechSynthesis.cancel();
      failSpeech(state);
    };
    window.speechSynthesis.speak(utterance);
  });

  if (chineseWithoutVoice) {
    const message = "This device has no Chinese voice, so Chinese text may be skipped. "
      + "Add a Chinese (Taiwan) voice in your device's text-to-speech settings.";
    if (state.mode === "text") setTextScanStatus(message, "warning");
    else setStatus(message, "warning");
  }
}

function updateReadingSpeechRate() {
  const output = document.querySelector("#speechRateValue");
  output.value = `${Number(speechRateInput.value).toFixed(1)}×`;
  if (!activeSpeechState || !("speechSynthesis" in window)) return;

  const state = { ...activeSpeechState };
  const offset = state.offset;
  if (offset >= state.text.length) return;
  const requestId = ++speechRequestId;
  window.speechSynthesis.cancel();
  activeSpeechMode = state.mode;
  startSpeechUtterance(state, offset, requestId);
  const message = "Speech speed updated; continuing from the current word.";
  if (state.mode === "text") setTextScanStatus(message, "success");
  else setStatus(message, "success");
}

function stopReading() {
  const stoppedMode = activeSpeechMode;
  speechRequestId += 1;
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  if (activeWord) {
    activeWord.element.classList.remove("reading-word");
    activeWord.sentenceElement.classList.remove("reading-sentence-active");
    activeWord = null;
  }
  // Cleared first so the scanner's Read button stops saying "Stop".
  activeSpeechMode = null;
  activeSpeechState = null;
  if (stoppedMode === "text") {
    endTextReading();
    setTextScanStatus("Reading stopped.", "info");
  } else if (stoppedMode === "description") {
    readButton.disabled = false;
    stopButton.disabled = true;
  }
}

function updateOcrProgress(message) {
  if (!textScanInProgress || !message?.status) return;
  const percent = Number.isFinite(message.progress)
    ? ` ${Math.round(message.progress * 100)}%`
    : "";
  setTextScanStatus(`${message.status}${percent}…`);
}

function selectedOcrLanguage() {
  const value = document.querySelector('input[name="ocrLanguage"]:checked')?.value;
  return OCR_LANGUAGES[value] ? value : "chi_tra";
}

async function getTextOcrWorker(language = selectedOcrLanguage()) {
  if (!window.Tesseract?.createWorker) {
    throw new Error(
      "The on-device text reader could not load. Check your internet connection and reload the page.",
    );
  }
  if (textOcrWorkerPromise && textOcrWorkerLanguage !== language) {
    // Another language was chosen: free the old reader's memory before loading the new one.
    const oldWorker = textOcrWorkerPromise;
    textOcrWorkerPromise = null;
    oldWorker.then((worker) => worker.terminate()).catch(() => {});
  }
  if (!textOcrWorkerPromise) {
    textOcrWorkerLanguage = language;
    textOcrWorkerPromise = window.Tesseract.createWorker(
      OCR_LANGUAGES[language].codes,
      1,
      {
        workerPath: "https://cdn.jsdelivr.net/npm/tesseract.js@6/dist/worker.min.js",
        corePath: "https://cdn.jsdelivr.net/npm/tesseract.js-core@6",
        langPath: "https://tessdata.projectnaptha.com/4.0.0",
        gzip: true,
        logger: updateOcrProgress,
      },
      {
        tessedit_pageseg_mode: window.Tesseract.PSM.AUTO,
        preserve_interword_spaces: "1",
      },
    ).catch((error) => {
      textOcrWorkerPromise = null;
      throw error;
    });
  }
  return textOcrWorkerPromise;
}

async function prepareOcrImage(blob) {
  const image = await loadImage(blob);
  const maxSide = Math.max(image.naturalWidth, image.naturalHeight);
  const scale = Math.min(1.6, 2000 / maxSide);
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
  canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) {
    throw new Error("This browser could not prepare the image for text recognition.");
  }
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";
  context.filter = "grayscale(1)";
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  evenOutLighting(context, image, canvas.width, canvas.height);
  return canvas;
}

// Divides each pixel by the page's local background brightness, so shadows (a
// book's fold) and coloured backgrounds (text printed on a picture) turn white
// and only the text stays dark. On a test photo of an open picture book this
// took text accuracy from 63% to 97%; flat pages were unchanged.
function evenOutLighting(context, image, width, height) {
  const pixels = context.getImageData(0, 0, width, height);
  // Background estimate: shrink the photo, keep each spot's brightest neighbour
  // (which wipes out thin dark text), then blur it back up to full size.
  const smallWidth = Math.max(1, Math.round(width / 16));
  const smallHeight = Math.max(1, Math.round(height / 16));
  const small = document.createElement("canvas");
  small.width = smallWidth;
  small.height = smallHeight;
  const smallContext = small.getContext("2d", { willReadFrequently: true });
  smallContext.filter = "grayscale(1)";
  smallContext.drawImage(image, 0, 0, smallWidth, smallHeight);
  const smallPixels = smallContext.getImageData(0, 0, smallWidth, smallHeight);
  for (let pass = 0; pass < 2; pass += 1) {
    const source = new Uint8ClampedArray(smallPixels.data);
    for (let y = 0; y < smallHeight; y += 1) {
      for (let x = 0; x < smallWidth; x += 1) {
        let brightest = 0;
        for (let dy = -1; dy <= 1; dy += 1) {
          for (let dx = -1; dx <= 1; dx += 1) {
            const nx = Math.min(smallWidth - 1, Math.max(0, x + dx));
            const ny = Math.min(smallHeight - 1, Math.max(0, y + dy));
            brightest = Math.max(brightest, source[(ny * smallWidth + nx) * 4]);
          }
        }
        const index = (y * smallWidth + x) * 4;
        smallPixels.data[index] = smallPixels.data[index + 1] = smallPixels.data[index + 2] = brightest;
      }
    }
  }
  smallContext.putImageData(smallPixels, 0, 0);
  const background = document.createElement("canvas");
  background.width = width;
  background.height = height;
  const backgroundContext = background.getContext("2d", { willReadFrequently: true });
  backgroundContext.filter = "blur(8px)";
  backgroundContext.imageSmoothingQuality = "high";
  backgroundContext.drawImage(small, 0, 0, width, height);
  const backgroundLight = backgroundContext.getImageData(0, 0, width, height).data;

  // Text is well under 55% of its background's brightness; paper is near 100%.
  const data = pixels.data;
  for (let index = 0; index < data.length; index += 4) {
    const ratio = data[index] / Math.max(1, backgroundLight[index]);
    const value = Math.max(0, Math.min(255, ((ratio - 0.55) / 0.35) * 255));
    data[index] = data[index + 1] = data[index + 2] = value;
  }
  context.putImageData(pixels, 0, 0);
}

async function scanTextImage() {
  if (textScanInProgress) return;
  if (!textSelectedImage) {
    setTextScanStatus("Start the camera and capture a page, or choose a photo first.", "warning");
    return;
  }
  textScanInProgress = true;
  scanTextButton.disabled = true;
  updateTextScanControls();
  try {
    stopReading();
    if (rulerView) setRulerView(false);
    const language = selectedOcrLanguage();
    setTextScanStatus(`Getting the ${OCR_LANGUAGES[language].name} reader ready…`);
    const worker = await getTextOcrWorker(language);
    setTextScanStatus("Enhancing the image and recognizing text…");
    const ocrImage = await prepareOcrImage(textSelectedImage);
    const { data } = await worker.recognize(ocrImage);
    const text = typeof data.text === "string" ? data.text.trim() : "";
    recognizedText.value = text;
    if (!text) {
      setTextScanStatus(
        "No text was found. Try a sharper, closer photo with the page upright and without glare.",
        "warning",
      );
    } else {
      setTextScanStatus(
        data.confidence < 55
          ? "Text read on this phone. Many words may be wrong, so check them."
          : "Text read on this phone. Some words may be wrong.",
        data.confidence < 55 ? "warning" : "success",
      );
    }
  } catch (error) {
    setTextScanStatus(
      error.message || "Text recognition failed. Check your connection and try again.",
      "error",
    );
  } finally {
    textScanInProgress = false;
    updateTextScanControls();
  }
}

async function copyScannerText(selectedOnly) {
  const start = selectedOnly ? recognizedText.selectionStart : 0;
  const end = selectedOnly ? recognizedText.selectionEnd : recognizedText.value.length;
  const text = recognizedText.value.slice(start, end).trim();
  if (!text) {
    setTextScanStatus(
      selectedOnly ? "Select some recognized text first, or choose Copy all." : "There is no recognized text to copy.",
      "warning",
    );
    return;
  }
  try {
    if (!navigator.clipboard?.writeText) {
      throw new Error("Clipboard access is unavailable in this browser. Select the text and copy it manually.");
    }
    await navigator.clipboard.writeText(text);
    setTextScanStatus(selectedOnly ? "Selected text copied." : "All recognized text copied.", "success");
  } catch (error) {
    setTextScanStatus(error.message || "Could not copy the text.", "error");
  }
}

function readScannerText(selectedOnly) {
  if (!("speechSynthesis" in window)) {
    setTextScanStatus("Text-to-speech is not available in this browser.", "error");
    return;
  }
  // In ruler view, "Read all" starts at the ruler's line.
  const rulerStart = rulerView && rulerLines.length ? rulerLines[rulerIndex].words[0].start : 0;
  const selectionStart = selectedOnly ? recognizedText.selectionStart : rulerStart;
  const selectionEnd = selectedOnly ? recognizedText.selectionEnd : recognizedText.value.length;
  const source = recognizedText.value.slice(selectionStart, selectionEnd);
  const text = source.trim();
  if (!text) {
    setTextScanStatus(
      selectedOnly ? "Select a word or passage in the recognized text first." : "There is no recognized text to read.",
      "warning",
    );
    return;
  }
  const leadingSpace = source.length - source.trimStart().length;
  const sourceStart = selectionStart + leadingSpace;
  const selectedVoice = voiceChoice.value === ""
    ? null
    : speechVoices[Number(voiceChoice.value)];

  window.speechSynthesis.cancel();
  const requestId = ++speechRequestId;
  activeSpeechMode = "text";
  const speechState = {
    mode: "text",
    text,
    sourceStart,
    offset: 0,
    voice: selectedVoice,
  };
  if (!rulerView) renderTextReadingPreview(recognizedText.value);
  startSpeechUtterance(speechState, 0, requestId);
  updateTextScanControls();
  setTextScanStatus(selectedOnly ? "Reading selected text…" : "Reading all recognized text…", "success");
}

// Long enough for a slow phone connection; after this, give up instead of
// leaving the user waiting with no answer.
const CLOUD_TIMEOUT_MS = 20000;

// Sends the photo (or the closest object's crop) to the ClearView cloud.
async function askCloud(image) {
  if (!navigator.onLine) throw new Error("You're offline. Connect to the internet and try again.");
  let response;
  try {
    response = await fetch("/api/identify", {
      method: "POST",
      headers: {
        "Content-Type": image.type || "image/jpeg",
        "X-ClearView-Client": "phone",
      },
      body: image,
      signal: AbortSignal.timeout(CLOUD_TIMEOUT_MS),
    });
  } catch (error) {
    console.error("Cloud request failed", error);
    throw new Error(error.name === "TimeoutError"
      ? "The internet is too slow right now. Please try again."
      : "Couldn't reach the internet. Please try again.");
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.error || "Could not identify that photo. Please try again.");
  }
  return payload || {};
}

function noObjectMessage(payload) {
  // The model's raw reply helps debugging but means nothing to users.
  console.warn("No object named by the cloud", payload);
  return "I couldn't tell what this is. Move closer, use more light, and try again.";
}

const trimmed = (value, limit) => (typeof value === "string" ? value.trim().slice(0, limit) : "");

// Decides what to show and say. The cloud looks at the object closely, so its
// name wins; only when it gives none does the on-device detector's name stand
// in, and then we say how sure it is ("might be").
function buildResult(payload, detected) {
  const { closest } = detected;
  const unsure = Boolean(closest && !payload.label && closest.confidence < UNSURE_BELOW);
  const label = trimmed(payload.label, 80) || closest?.label || (payload.recognizedText ? "Labeled item" : "");
  if (!label) throw new Error(noObjectMessage(payload));

  const description = trimmed(payload.description, 360);
  const explanation = description && description.toLowerCase() !== label.toLowerCase()
    ? description
    : label === "Labeled item"
      ? `I could not tell what this is. Its label reads: ${trimmed(payload.recognizedText, 240)}.`
      : descriptions[label.toLowerCase()] || "It is an everyday object. Its exact purpose may depend on the item.";
  return {
    label,
    explanation,
    product: trimmed(payload.product, 120),
    unsure,
  };
}

function resultStatus(result, describedOnline) {
  if (result.unsure) {
    return ["Not sure about this one. Try another angle, move closer, or use more light.", "warning"];
  }
  if (!describedOnline) {
    return ["Named on your phone only. The full description didn't load.", "warning"];
  }
  return ["Found it.", "success"];
}

// again: "Not right? Try again". The cloud then looks at the whole photo (the
// first try usually saw only the closest object), and the objects found before are reused.
async function scanImage({ again = false } = {}) {
  if (!selectedImage) {
    setStatus("Capture a photo or choose one before scanning.", "error");
    return;
  }
  stopReading();
  scanButton.disabled = true;
  retryButton.disabled = true;
  scanButton.textContent = "Identifying…";
  setStatus(again ? "Looking at the whole photo again…" : "Finding objects in the photo…");
  try {
    // 1. Find every object on the phone.
    let detected = { closest: null, objects: [] };
    if (again && lastScan) {
      detected = lastScan.detected;
    } else {
      try {
        detected = await detectObjects(selectedImage);
      } catch (error) {
        console.error("On-device object detection failed; describing the whole photo", error);
      }
    }

    // 2. Ask the cloud about the closest one; if that fails, use the on-device name.
    if (!again) setStatus("Describing the closest object…");
    const upload = detected.closest && !again ? await cropDetection(selectedImage, detected.closest) : selectedImage;
    let payload = {};
    let describedOnline = true;
    try {
      payload = await askCloud(upload);
    } catch (error) {
      if (!detected.closest) throw error;
      console.error("Online description failed; using the on-device name", error);
      describedOnline = false;
    }

    // 3. Show it and say how sure we are.
    const result = buildResult(payload, detected);
    const sameAgain = again && lastScan?.label.toLowerCase() === result.label.toLowerCase();
    renderResult(result);
    rememberScan(result);
    lastScan = { detected, label: result.label };
    retryButton.hidden = false;
    resultContent.parentElement.scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      block: "nearest",
    });
    if (sameAgain) {
      setStatus("Same answer again. Take a new photo from another angle, closer, or with more light.", "warning");
    } else {
      setStatus(...resultStatus(result, describedOnline));
    }
    // Screen readers stay on the scan button unless told; move them to the answer.
    resultContent.querySelector(".object-title")?.focus({ preventScroll: true });
    if (autoReadInput.checked) readAloud();
  } catch (error) {
    setStatus(error.message || "Could not identify that photo. Please try again.", "error");
  } finally {
    scanButton.disabled = false;
    retryButton.disabled = false;
    scanButton.textContent = "Identify object";
  }
}

const warmUpDetector = () => loadDetector().catch(() => {});
cameraButton.addEventListener("click", warmUpDetector);
photoButton.addEventListener("click", warmUpDetector);
cameraButton.addEventListener("click", () => {
  if (cameraStream) {
    capturePhoto();
  } else {
    startCamera();
  }
});
photoButton.addEventListener("click", () => photoInput.click());
photoInput.addEventListener("change", () => preparePhoto(photoInput.files?.[0]));
scanButton.addEventListener("click", () => scanImage());
retryButton.addEventListener("click", () => scanImage({ again: true }));
autoCaptureInput.addEventListener("change", () => {
  if (cameraStream) watchObjectCamera();
});
resultContent.addEventListener("click", (event) => {
  const word = wordElements.find((item) => item.element === event.target);
  if (word) speakWord(word);
});
textReadingPreview.addEventListener("click", (event) => {
  const word = textPreviewWords.find((item) => item.element === event.target);
  if (word) speakWord(word);
});
textCameraButton.addEventListener("click", () => {
  if (textCameraStream) {
    captureTextPhoto();
  } else {
    startTextCamera();
  }
});
textPhotoButton.addEventListener("click", () => textPhotoInput.click());
textPhotoInput.addEventListener("change", () => prepareTextPhoto(textPhotoInput.files?.[0]));
scanTextButton.addEventListener("click", scanTextImage);
copyTextButton.addEventListener("click", () => copyScannerText(hasWordsSelected()));
readTextButton.addEventListener("click", () => {
  if (activeSpeechMode === "text") stopReading();
  else readScannerText(hasWordsSelected());
});
recognizedText.addEventListener("input", updateTextScanControls);
recognizedText.addEventListener("select", updateTextScanControls);
document.addEventListener("selectionchange", updateTextScanControls);
readButton.addEventListener("click", readAloud);
stopButton.addEventListener("click", stopReading);
menuToggle.addEventListener("click", () => {
  const isExpanded = menuToggle.getAttribute("aria-expanded") === "true";
  featureMenu.hidden = isExpanded;
  menuToggle.setAttribute("aria-expanded", String(!isExpanded));
  menuToggle.setAttribute("aria-label", isExpanded ? "Open feature menu" : "Close feature menu");
});
for (const link of screenLinks) {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    showAppScreen(link.dataset.screenTarget);
  });
}
document.addEventListener("click", (event) => {
  if (!event.target.closest(".feature-nav")) {
    closeFeatureMenu();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeFeatureMenu();
});
window.addEventListener("pagehide", () => {
  stopCamera();
  stopTextCamera();
});
function updateFontSizePreference() {
  document.querySelector("#fontSizeValue").value = `${fontSizeInput.value}px`;
  const fontSize = `${fontSizeInput.value}px`;
  resultContent.style.fontSize = fontSize;
  recognizedText.style.fontSize = fontSize;
  textReadingPreview.style.fontSize = fontSize;
}
function updateLetterSpacingPreference() {
  const spacing = Number(letterSpacingInput.value) * 0.025;
  document.querySelector("#letterSpacingValue").value = letterSpacingInput.value;
  resultContent.style.letterSpacing = `${spacing}em`;
  recognizedText.style.letterSpacing = `${spacing}em`;
  textReadingPreview.style.letterSpacing = `${spacing}em`;
}
function updateLineSpacingPreference() {
  document.querySelector("#lineSpacingValue").value = Number(lineSpacingInput.value).toFixed(1);
  for (const element of [resultContent, recognizedText, textReadingPreview]) {
    element.style.lineHeight = lineSpacingInput.value;
  }
}
function updateReadingFont() {
  document.documentElement.dataset.font = readingFontInput.value;
  // The new font changes where lines break; wait for it to load, then re-measure.
  document.fonts?.ready.then(refreshRuler);
}
const themeColorMeta = document.querySelector('meta[name="theme-color"]');
function applyTint(tint) {
  document.documentElement.dataset.tint = tint;
  themeColorMeta.content = getComputedStyle(document.documentElement).getPropertyValue("--ground").trim();
}
for (const option of document.querySelectorAll('input[name="tint"]')) {
  option.checked = option.value === document.documentElement.dataset.tint;
  option.addEventListener("change", () => {
    applyTint(option.value);
    try {
      localStorage.setItem("clearview-tint", option.value);
    } catch {
      // Storage can be blocked (private mode); the tint still applies for this visit.
    }
  });
}
applyTint(document.documentElement.dataset.tint || "cream");

const savedOcrLanguage = loadSetting("ocrLanguage");
for (const option of document.querySelectorAll('input[name="ocrLanguage"]')) {
  if (OCR_LANGUAGES[savedOcrLanguage]) option.checked = option.value === savedOcrLanguage;
  option.addEventListener("change", () => saveSetting("ocrLanguage", option.value));
}

for (const [name, input] of [
  ["fontSize", fontSizeInput],
  ["letterSpacing", letterSpacingInput],
  ["speechRate", speechRateInput],
  ["rulerLines", rulerLinesInput],
  ["rulerAway", rulerAwayInput],
  ["lineSpacing", lineSpacingInput],
  ["readingFont", readingFontInput],
]) {
  const saved = loadSetting(name);
  if (saved !== null) input.value = saved;
  input.addEventListener("change", () => saveSetting(name, input.value));
}
for (const [name, input] of [["autoCapture", autoCaptureInput], ["autoRead", autoReadInput]]) {
  const saved = loadSetting(name);
  if (saved !== null) input.checked = saved === "on";
  input.addEventListener("change", () => saveSetting(name, input.checked ? "on" : "off"));
}
voiceChoice.addEventListener("change", () => {
  saveSetting("voice", voiceChoice.value === "" ? "" : speechVoices[Number(voiceChoice.value)]?.name || "");
});

fontSizeInput.addEventListener("input", updateFontSizePreference);
letterSpacingInput.addEventListener("input", updateLetterSpacingPreference);
speechRateInput.addEventListener("input", updateReadingSpeechRate);
fontSizeInput.addEventListener("input", refreshRuler);
letterSpacingInput.addEventListener("input", refreshRuler);
lineSpacingInput.addEventListener("input", updateLineSpacingPreference);
lineSpacingInput.addEventListener("input", refreshRuler);
readingFontInput.addEventListener("change", updateReadingFont);
window.addEventListener("resize", refreshRuler);

rulerViewButton.addEventListener("click", () => setRulerView(!rulerView));
rulerPrevButton.addEventListener("click", () => moveRuler(rulerIndex - 1));
rulerNextButton.addEventListener("click", () => moveRuler(rulerIndex + 1));
rulerLinesInput.addEventListener("change", drawRuler);
rulerAwayInput.addEventListener("change", () => {
  textReadingPreview.dataset.away = rulerAwayInput.value;
});
textReadingPreview.addEventListener("click", (event) => {
  if (!rulerParts || rulerSize() === 0) return;
  const box = textReadingPreview.getBoundingClientRect();
  const y = event.clientY - box.top - textReadingPreview.clientTop + textReadingPreview.scrollTop;
  const index = rulerLines.findIndex((line) => y >= line.top - 8 && y <= line.bottom + 8);
  if (index >= 0) moveRuler(index);
});
textReadingPreview.addEventListener("keydown", (event) => {
  if (!rulerParts || rulerSize() === 0) return;
  if (event.key === "ArrowDown" || event.key === "ArrowRight") moveRuler(rulerIndex + 1);
  else if (event.key === "ArrowUp" || event.key === "ArrowLeft") moveRuler(rulerIndex - 1);
  else return;
  event.preventDefault();
});

if ("speechSynthesis" in window) {
  refreshVoices();
  window.speechSynthesis.addEventListener("voiceschanged", refreshVoices);
} else {
  readButton.disabled = true;
  voiceChoice.disabled = true;
}
updateFontSizePreference();
updateLetterSpacingPreference();
updateLineSpacingPreference();
updateReadingFont();
updateReadingSpeechRate();
updateTextScanControls();
