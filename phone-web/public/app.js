"use strict";

const MAX_IMAGE_SIDE = 1280;
const MAX_OCR_IMAGE_SIDE = 2400;
const JPEG_QUALITY = 0.82;

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
const copySelectedTextButton = document.querySelector("#copySelectedTextButton");
const copyAllTextButton = document.querySelector("#copyAllTextButton");
const readSelectedTextButton = document.querySelector("#readSelectedTextButton");
const readAllTextButton = document.querySelector("#readAllTextButton");
const stopTextButton = document.querySelector("#stopTextButton");
const recognizedText = document.querySelector("#recognizedText");
const textScanStatus = document.querySelector("#textScanStatus");
const fontSizeInput = document.querySelector("#fontSize");
const letterSpacingInput = document.querySelector("#letterSpacing");
const speechRateInput = document.querySelector("#speechRate");
const voiceChoice = document.querySelector("#voiceChoice");

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
let speechVoices = [];
let textOcrWorkerPromise = null;
let textScanInProgress = false;
let activeSpeechMode = null;
let speechRequestId = 0;

const descriptions = {
  apple: "It is a crisp fruit people can eat as a snack or add to a meal.",
  backpack: "It is used to carry items on your back.",
  banana: "It is a soft, sweet fruit with a yellow peel.",
  book: "It contains pages that people can read to learn or enjoy a story.",
  bottle: "It can hold drinks, such as water.",
  cup: "It is used for drinking hot or cold drinks.",
  fork: "It helps people pick up and eat food.",
  glasses: "They help people see more clearly when worn in front of the eyes.",
  handbag: "It is used to carry personal items.",
  headphones: "They are worn over or in the ears to listen to sound.",
  keyboard: "It is used to type letters and numbers into a computer.",
  laptop: "It is a portable computer for work, learning, and communication.",
  phone: "It can be used to call or message people.",
  "cell phone": "It can be used to call or message people.",
  cellphone: "It can be used to call or message people.",
  "mobile phone": "It can be used to call or message people.",
  mouse: "It helps control a pointer on a computer screen.",
  pen: "It is a writing tool that uses ink to make marks on paper.",
  person: "A person is someone you can talk with or ask for help.",
  plate: "It is used to hold and serve food.",
  remote: "It is used to control a device from a short distance.",
  scissors: "They are used to cut paper and other materials. Handle them carefully.",
  shoe: "It protects the foot and is worn for walking.",
  shoes: "They protect the feet and are worn for walking.",
  spoon: "It helps people eat or serve food.",
  stapler: "It joins pieces of paper together using small metal staples.",
  toothbrush: "It is used with toothpaste to clean teeth.",
  umbrella: "It helps protect people from rain or strong sun.",
  wallet: "It is a small case used to carry money and cards.",
};

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
  const hasSelection = recognizedText.selectionStart !== recognizedText.selectionEnd;
  const isReadingText = activeSpeechMode === "text";
  copySelectedTextButton.disabled = !hasSelection;
  copyAllTextButton.disabled = !hasText;
  readSelectedTextButton.disabled = !hasSelection || isReadingText || !("speechSynthesis" in window);
  readAllTextButton.disabled = !hasText || isReadingText || !("speechSynthesis" in window);
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
}

function stopCamera() {
  if (cameraStream) {
    for (const track of cameraStream.getTracks()) {
      track.stop();
    }
    cameraStream = null;
  }
  cameraVideo.srcObject = null;
  cameraVideo.hidden = true;
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
    cameraButton.textContent = "Capture photo";
    await cameraVideo.play();
    setStatus("Camera ready. Center one item, then capture it.", "success");
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
    setStatus("Photo captured. Choose Identify object to scan it.", "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
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
    setStatus("Photo ready. Choose Identify object to scan it.", "success");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    photoInput.value = "";
  }
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
  const wordPattern = /[\p{L}\p{N}_]+(?:['’][\p{L}\p{N}_]+)*/gu;
  const words = [];
  for (const match of text.matchAll(wordPattern)) {
    words.push({
      start: match.index,
      end: match.index + match[0].length,
      text: match[0],
    });
  }
  return words;
}

function sentenceRangeAt(text, index) {
  const pattern = /[^.!?]+[.!?]*|[.!?]+/gu;
  for (const match of text.matchAll(pattern)) {
    if (match.index <= index && index < match.index + match[0].length) {
      return { start: match.index, end: match.index + match[0].length };
    }
  }
  return { start: 0, end: text.length };
}

function renderDescription(label, explanation, recognizedText = "", product = "") {
  currentDescription = `This is ${label}. ${explanation}`;
  if (product) {
    currentDescription += ` The label suggests this is ${product}.`;
  }
  if (recognizedText) {
    currentDescription += ` The visible text reads: ${recognizedText}.`;
  }
  wordElements = [];
  activeWord = null;
  resultContent.replaceChildren();

  const title = document.createElement("h3");
  title.className = "object-title";
  title.textContent = label;
  const paragraph = document.createElement("p");
  paragraph.className = "object-description";
  const words = splitIntoWords(currentDescription);
  const sentences = [];
  for (const word of words) {
    const range = sentenceRangeAt(currentDescription, word.start);
    let sentence = sentences.find((item) => item.start === range.start && item.end === range.end);
    if (!sentence) {
      sentence = { ...range, element: document.createElement("span") };
      sentence.element.className = "reading-sentence";
      sentences.push(sentence);
    }
    const wordElement = document.createElement("span");
    wordElement.textContent = word.text;
    sentence.element.append(wordElement);
    wordElements.push({
      ...word,
      element: wordElement,
      sentenceElement: sentence.element,
    });
  }

  let cursor = 0;
  for (const sentence of sentences.sort((left, right) => left.start - right.start)) {
    if (sentence.start > cursor) {
      paragraph.append(document.createTextNode(currentDescription.slice(cursor, sentence.start)));
    }
    const sentenceWords = wordElements.filter((word) => word.sentenceElement === sentence.element);
    let sentenceCursor = sentence.start;
    for (const word of sentenceWords) {
      if (word.start > sentenceCursor) {
        sentence.element.insertBefore(
          document.createTextNode(currentDescription.slice(sentenceCursor, word.start)),
          word.element,
        );
      }
      sentenceCursor = word.end;
    }
    if (sentenceCursor < sentence.end) {
      sentence.element.append(document.createTextNode(currentDescription.slice(sentenceCursor, sentence.end)));
    }
    paragraph.append(sentence.element);
    cursor = sentence.end;
  }
  if (cursor < currentDescription.length) {
    paragraph.append(document.createTextNode(currentDescription.slice(cursor)));
  }
  resultContent.append(title, paragraph);
  readButton.disabled = !("speechSynthesis" in window);
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

function refreshVoices() {
  if (!("speechSynthesis" in window)) return;
  speechVoices = window.speechSynthesis.getVoices();
  const previous = voiceChoice.value;
  voiceChoice.replaceChildren(new Option("Default voice", ""));
  for (const [index, voice] of speechVoices.entries()) {
    const option = new Option(voice.name, String(index));
    voiceChoice.add(option);
  }
  if (speechVoices.some((voice, index) => String(index) === previous)) {
    voiceChoice.value = previous;
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
  const utterance = new SpeechSynthesisUtterance(currentDescription);
  utterance.rate = Number(speechRateInput.value);
  const selectedVoice = voiceChoice.value === ""
    ? null
    : speechVoices[Number(voiceChoice.value)];
  if (selectedVoice) utterance.voice = selectedVoice;
  utterance.onboundary = (event) => {
    if (
      requestId === speechRequestId
      && activeSpeechMode === "description"
      && (event.name === "word" || Number.isFinite(event.charIndex))
    ) {
      updateSpeechBoundary(event.charIndex);
    }
  };
  utterance.onend = () => {
    if (requestId !== speechRequestId || activeSpeechMode !== "description") return;
    if (activeWord) {
      activeWord.element.classList.remove("reading-word");
      activeWord.sentenceElement.classList.remove("reading-sentence-active");
      activeWord = null;
    }
    activeSpeechMode = null;
    readButton.disabled = false;
    stopButton.disabled = true;
    setStatus("Finished reading. You can listen again at any time.", "success");
  };
  utterance.onerror = (event) => {
    if (requestId !== speechRequestId || activeSpeechMode !== "description") return;
    activeSpeechMode = null;
    readButton.disabled = false;
    stopButton.disabled = true;
    if (event.error !== "canceled" && event.error !== "interrupted") {
      setStatus("The browser could not read this explanation aloud.", "error");
    }
  };
  readButton.disabled = true;
  stopButton.disabled = false;
  setStatus("Reading the explanation aloud…", "success");
  window.speechSynthesis.speak(utterance);
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
  if (stoppedMode === "text") {
    stopTextButton.disabled = true;
    updateTextScanControls();
    setTextScanStatus("Reading stopped.", "info");
  } else if (stoppedMode === "description") {
    readButton.disabled = false;
    stopButton.disabled = true;
  }
  activeSpeechMode = null;
}

function updateOcrProgress(message) {
  if (!textScanInProgress || !message?.status) return;
  const percent = Number.isFinite(message.progress)
    ? ` ${Math.round(message.progress * 100)}%`
    : "";
  setTextScanStatus(`${message.status}${percent}…`);
}

async function getTextOcrWorker() {
  if (!window.Tesseract?.createWorker) {
    throw new Error(
      "The on-device text reader could not load. Check your internet connection and reload the page.",
    );
  }
  if (!textOcrWorkerPromise) {
    textOcrWorkerPromise = window.Tesseract.createWorker(
      ["eng", "chi_tra"],
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
  context.filter = "grayscale(1) contrast(1.18) brightness(1.03)";
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas;
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
    setTextScanStatus("Loading English and Traditional Chinese text models…");
    const worker = await getTextOcrWorker();
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
      const confidence = Number.isFinite(data.confidence)
        ? ` Average recognition confidence: ${Math.round(data.confidence)}%.`
        : "";
      setTextScanStatus(
        `Text recognized on this device.${confidence} Proofread the result; OCR can make mistakes.`,
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
  const selectionStart = selectedOnly ? recognizedText.selectionStart : 0;
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
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = Number(speechRateInput.value);
  if (selectedVoice) utterance.voice = selectedVoice;
  utterance.onboundary = (event) => {
    if (requestId !== speechRequestId || activeSpeechMode !== "text") return;
    const start = Math.max(0, Math.min(text.length, event.charIndex || 0));
    const boundaryLength = Number.isFinite(event.charLength) && event.charLength > 0
      ? event.charLength
      : splitIntoWords(text).find((word) => word.start <= start && start < word.end)?.end - start || 1;
    recognizedText.setSelectionRange(
      sourceStart + start,
      Math.min(sourceStart + text.length, sourceStart + start + boundaryLength),
    );
  };
  utterance.onend = () => {
    if (requestId !== speechRequestId || activeSpeechMode !== "text") return;
    activeSpeechMode = null;
    stopTextButton.disabled = true;
    updateTextScanControls();
    setTextScanStatus("Finished reading the selected text.", "success");
  };
  utterance.onerror = (event) => {
    if (requestId !== speechRequestId || activeSpeechMode !== "text") return;
    activeSpeechMode = null;
    stopTextButton.disabled = true;
    updateTextScanControls();
    if (event.error !== "canceled" && event.error !== "interrupted") {
      setTextScanStatus("The browser could not read this text aloud.", "error");
    }
  };
  updateTextScanControls();
  readSelectedTextButton.disabled = true;
  readAllTextButton.disabled = true;
  stopTextButton.disabled = false;
  setTextScanStatus(selectedOnly ? "Reading selected text…" : "Reading all recognized text…", "success");
  window.speechSynthesis.speak(utterance);
}

async function scanImage() {
  if (!selectedImage) {
    setStatus("Capture a photo or choose one before scanning.", "error");
    return;
  }
  scanButton.disabled = true;
  scanButton.textContent = "Identifying…";
  setStatus("Looking for the main everyday object…");
  try {
    const response = await fetch("/api/identify", {
      method: "POST",
      headers: { "Content-Type": selectedImage.type || "image/jpeg" },
      body: selectedImage,
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(payload?.error || "Could not identify that photo. Please try again.");
    }
    if (!payload?.found || (!payload.label && !payload.recognizedText)) {
      const modelAnswer = typeof payload?.answer === "string" && payload.answer.trim()
        ? ` The AI replied: “${payload.answer.trim()}”`
        : ` The AI returned no caption${Array.isArray(payload?.modelFields) && payload.modelFields.length
          ? ` (response fields: ${payload.modelFields.join(", ")})`
          : ""}${payload?.finishReason ? ` (finish: ${payload.finishReason})` : ""}${payload?.responseSummary
          ? ` (response: ${payload.responseSummary})`
          : ""}.`;
      throw new Error(`I could not identify a clear everyday object.${modelAnswer}`);
    }
    const recognizedText = typeof payload.recognizedText === "string"
      ? payload.recognizedText.trim().slice(0, 240)
      : "";
    const label = typeof payload.label === "string" && payload.label.trim()
      ? payload.label.trim()
      : "Labeled item";
    const modelDescription = typeof payload.description === "string"
      ? payload.description.trim().slice(0, 360)
      : "";
    const explanation = modelDescription && modelDescription.toLowerCase() !== label.toLowerCase()
      ? modelDescription
      : label === "Labeled item"
        ? "I could read some label text, but could not identify the object itself."
        : descriptions[label.toLowerCase()]
          || "It is an everyday object. Its exact purpose may depend on the item.";
    const product = typeof payload.product === "string"
      ? payload.product.trim().slice(0, 120)
      : "";
    renderDescription(label, explanation, recognizedText, product);
    setStatus(
      recognizedText
        ? "Label text read. Check the text and product identification; AI can make mistakes."
        : payload.textReaderAvailable === false
          ? "Object identified, but label reading returned no text. Try scanning a closer, sharper photo."
          : "Object identified, but I couldn't read clear label text. Move closer and keep the label in focus.",
      recognizedText ? "success" : "warning",
    );
  } catch (error) {
    setStatus(error.message || "Could not identify that photo. Please try again.", "error");
  } finally {
    scanButton.disabled = false;
    scanButton.textContent = "Identify object";
  }
}

cameraButton.addEventListener("click", () => {
  if (cameraStream) {
    capturePhoto();
  } else {
    startCamera();
  }
});
photoButton.addEventListener("click", () => photoInput.click());
photoInput.addEventListener("change", () => preparePhoto(photoInput.files?.[0]));
scanButton.addEventListener("click", scanImage);
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
copySelectedTextButton.addEventListener("click", () => copyScannerText(true));
copyAllTextButton.addEventListener("click", () => copyScannerText(false));
readSelectedTextButton.addEventListener("click", () => readScannerText(true));
readAllTextButton.addEventListener("click", () => readScannerText(false));
stopTextButton.addEventListener("click", stopReading);
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
fontSizeInput.addEventListener("input", () => {
  document.querySelector("#fontSizeValue").value = `${fontSizeInput.value}px`;
  resultContent.style.fontSize = `${fontSizeInput.value}px`;
});
letterSpacingInput.addEventListener("input", () => {
  const spacing = Number(letterSpacingInput.value) * 0.025;
  document.querySelector("#letterSpacingValue").value = letterSpacingInput.value;
  resultContent.style.letterSpacing = `${spacing}em`;
});
speechRateInput.addEventListener("input", () => {
  document.querySelector("#speechRateValue").value = `${Number(speechRateInput.value).toFixed(1)}×`;
});

if ("speechSynthesis" in window) {
  refreshVoices();
  window.speechSynthesis.addEventListener("voiceschanged", refreshVoices);
} else {
  readButton.disabled = true;
  voiceChoice.disabled = true;
}
updateTextScanControls();
