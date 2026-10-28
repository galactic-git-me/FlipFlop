export type PhotoScreeningResult = {
  reasons: string[];
  visualSignature: string | null;
};

const SAMPLE_SIZE = 128;
const COLOR_DISTANCE_LIMIT = 50;

export function inspectProductPhoto(image: HTMLImageElement): PhotoScreeningResult {
  try {
    const canvas = document.createElement("canvas");
    canvas.width = SAMPLE_SIZE;
    canvas.height = SAMPLE_SIZE;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context || !image.naturalWidth || !image.naturalHeight) {
      return { reasons: ["could not inspect automatically"], visualSignature: null };
    }

    context.fillStyle = "#fff";
    context.fillRect(0, 0, SAMPLE_SIZE, SAMPLE_SIZE);
    const scale = Math.min(120 / image.naturalWidth, 120 / image.naturalHeight);
    const width = image.naturalWidth * scale;
    const height = image.naturalHeight * scale;
    const left = (SAMPLE_SIZE - width) / 2;
    const top = (SAMPLE_SIZE - height) / 2;
    context.drawImage(image, left, top, width, height);

    const pixels = context.getImageData(0, 0, SAMPLE_SIZE, SAMPLE_SIZE).data;
    const gray = new Uint8Array(SAMPLE_SIZE * SAMPLE_SIZE);
    const signatureBytes: number[] = [];
    for (let y = 0; y < SAMPLE_SIZE; y += 1) {
      for (let x = 0; x < SAMPLE_SIZE; x += 1) {
        const index = (y * SAMPLE_SIZE + x) * 4;
        const r = pixels[index];
        const g = pixels[index + 1];
        const b = pixels[index + 2];
        gray[y * SAMPLE_SIZE + x] = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
        if (x % 3 === 0 && y % 3 === 0) signatureBytes.push(r, g, b);
      }
    }

    const reasons: string[] = [];
    if (hasTextOverlay(gray)) reasons.push("text or promotional overlay");
    if (isTightlyCropped(pixels, gray, image.naturalWidth / image.naturalHeight)) {
      reasons.push("product fills the frame; likely a close-up");
    }

    return {
      reasons,
      visualSignature: String.fromCharCode(...signatureBytes),
    };
  } catch {
    return { reasons: ["could not inspect automatically"], visualSignature: null };
  }
}

function hasTextOverlay(gray: Uint8Array) {
  let runRows = 0;
  let lastQualifiedY = -3;
  let groupHeight = 0;

  for (let y = 2; y < SAMPLE_SIZE - 2; y += 1) {
    let transitions = 0;
    let firstX = SAMPLE_SIZE;
    let lastX = 0;
    const row = y * SAMPLE_SIZE;
    for (let x = 2; x < SAMPLE_SIZE - 2; x += 1) {
      if (Math.abs(gray[row + x] - gray[row + x - 1]) >= 65) {
        transitions += 1;
        firstX = Math.min(firstX, x);
        lastX = Math.max(lastX, x);
      }
    }

    const looksLikeTextRow = transitions >= 12 && lastX - firstX >= 36;
    if (!looksLikeTextRow) {
      if (runRows >= 3 && groupHeight <= 18) return true;
      runRows = 0;
      groupHeight = 0;
      lastQualifiedY = y - 2;
      continue;
    }

    if (y - lastQualifiedY <= 2) {
      runRows += 1;
      groupHeight = y - lastQualifiedY;
    } else {
      runRows = 1;
      groupHeight = 1;
    }
    lastQualifiedY = y;
  }
  return runRows >= 3 && groupHeight <= 18;
}

function isTightlyCropped(pixels: Uint8ClampedArray, gray: Uint8Array, aspectRatio: number) {
  const cornerColors: number[][] = [];
  for (const [startX, startY] of [[0, 0], [SAMPLE_SIZE - 8, 0], [0, SAMPLE_SIZE - 8], [SAMPLE_SIZE - 8, SAMPLE_SIZE - 8]]) {
    for (let y = startY; y < startY + 8; y += 1) {
      for (let x = startX; x < startX + 8; x += 1) {
        const index = (y * SAMPLE_SIZE + x) * 4;
        cornerColors.push([pixels[index], pixels[index + 1], pixels[index + 2]]);
      }
    }
  }
  const background = [0, 1, 2].map(channel => median(cornerColors.map(color => color[channel])));
  let foregroundCount = 0;
  let minX = SAMPLE_SIZE;
  let minY = SAMPLE_SIZE;
  let maxX = -1;
  let maxY = -1;
  for (let y = 0; y < SAMPLE_SIZE; y += 1) {
    for (let x = 0; x < SAMPLE_SIZE; x += 1) {
      const index = (y * SAMPLE_SIZE + x) * 4;
      const distance = Math.hypot(
        pixels[index] - background[0],
        pixels[index + 1] - background[1],
        pixels[index + 2] - background[2],
      );
      if (distance < COLOR_DISTANCE_LIMIT) continue;
      foregroundCount += 1;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    }
  }

  const foregroundRatio = foregroundCount / (SAMPLE_SIZE * SAMPLE_SIZE);
  const reachesOppositeEdges = (minX <= 4 && maxX >= SAMPLE_SIZE - 5)
    || (minY <= 4 && maxY >= SAMPLE_SIZE - 5);
  if (foregroundRatio >= 0.28 && reachesOppositeEdges) return true;

  // Busy or dark backgrounds make corner-colour separation unreliable. For
  // square detail shots, look for strong edges spanning almost the full frame.
  if (aspectRatio < 0.85 || aspectRatio > 1.18) return false;
  let edgeCount = 0;
  minX = SAMPLE_SIZE;
  minY = SAMPLE_SIZE;
  maxX = -1;
  maxY = -1;
  for (let y = 1; y < SAMPLE_SIZE - 1; y += 1) {
    for (let x = 1; x < SAMPLE_SIZE - 1; x += 1) {
      const index = y * SAMPLE_SIZE + x;
      const edge = Math.abs(gray[index + 1] - gray[index - 1])
        + Math.abs(gray[index + SAMPLE_SIZE] - gray[index - SAMPLE_SIZE]);
      if (edge < 70) continue;
      edgeCount += 1;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    }
  }
  return edgeCount / (SAMPLE_SIZE * SAMPLE_SIZE) > 0.12
    && minX <= 4 && maxX >= SAMPLE_SIZE - 5
    && minY <= 4 && maxY >= SAMPLE_SIZE - 5;
}

function median(values: number[]) {
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.floor(sorted.length / 2)] ?? 255;
}
