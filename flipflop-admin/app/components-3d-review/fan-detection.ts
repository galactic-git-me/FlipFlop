export interface DetectedFan {
  centerX: number;
  centerY: number;
  radius: number;
  confidence: number;
}

const ANALYSIS_SIZE = 384;
const ANGLE_COUNT = 32;
const MIN_RING_COVERAGE = 0.3;
const MAX_DETECTIONS = 24;

export async function detectRgbFans(imageUrl: string): Promise<DetectedFan[]> {
  const response = await fetch(`/api/proxy-image?url=${encodeURIComponent(imageUrl)}`);
  if (!response.ok) throw new Error(`Could not read reference photo (${response.status})`);

  const bitmap = await createImageBitmap(await response.blob());
  const scale = Math.min(1, ANALYSIS_SIZE / Math.max(bitmap.width, bitmap.height));
  const width = Math.max(1, Math.round(bitmap.width * scale));
  const height = Math.max(1, Math.round(bitmap.height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) {
    bitmap.close();
    throw new Error("Image analysis is unavailable in this browser");
  }

  context.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();
  const pixels = context.getImageData(0, 0, width, height).data;
  const colored = new Uint8Array(width * height);
  for (let index = 0; index < colored.length; index += 1) {
    const offset = index * 4;
    const red = pixels[offset];
    const green = pixels[offset + 1];
    const blue = pixels[offset + 2];
    const high = Math.max(red, green, blue);
    const low = Math.min(red, green, blue);
    // Keep lit colour, while discarding neutral white highlights and dark chassis pixels.
    colored[index] = high > 72 && high - low > Math.max(28, high * 0.16) ? 1 : 0;
  }

  const minDimension = Math.min(width, height);
  const minRadius = Math.max(7, Math.floor(minDimension * 0.025));
  const maxRadius = Math.floor(minDimension * 0.14);
  const candidates: DetectedFan[] = [];

  for (let radius = minRadius; radius <= maxRadius; radius += 2) {
    const ringOffsets = Array.from({ length: ANGLE_COUNT }, (_, index) => {
      const angle = (index / ANGLE_COUNT) * Math.PI * 2;
      return [Math.cos(angle), Math.sin(angle)] as const;
    });
    const innerRadius = Math.round(radius * 0.72);
    const outerRadius = Math.round(radius * 0.92);
    const coreRadius = Math.max(2, Math.round(radius * 0.28));

    for (let centerY = radius; centerY < height - radius; centerY += 2) {
      for (let centerX = radius; centerX < width - radius; centerX += 2) {
        let innerHits = 0;
        let outerHits = 0;
        let coreHits = 0;
        for (const [cosine, sine] of ringOffsets) {
          const innerX = Math.round(centerX + cosine * innerRadius);
          const innerY = Math.round(centerY + sine * innerRadius);
          const outerX = Math.round(centerX + cosine * outerRadius);
          const outerY = Math.round(centerY + sine * outerRadius);
          const coreX = Math.round(centerX + cosine * coreRadius);
          const coreY = Math.round(centerY + sine * coreRadius);
          innerHits += colored[innerY * width + innerX];
          outerHits += colored[outerY * width + outerX];
          coreHits += colored[coreY * width + coreX];
        }

        const innerCoverage = innerHits / ANGLE_COUNT;
        const outerCoverage = outerHits / ANGLE_COUNT;
        const coreCoverage = coreHits / ANGLE_COUNT;
        const ringCoverage = (innerCoverage + outerCoverage) * 0.5;
        // A fan has colour around its frame and a less-coloured central hub.
        // This rejects broad coloured patches that the old perimeter-only scan accepted.
        const hollowCore = Math.max(0, ringCoverage - coreCoverage);
        const score = ringCoverage * 0.72 + hollowCore * 0.28;
        if (ringCoverage < MIN_RING_COVERAGE || hollowCore < 0.08 || score < 0.28) continue;

        candidates.push({
          centerX: centerX / width,
          centerY: centerY / height,
          radius: radius / minDimension,
          confidence: Math.min(0.99, score),
        });
      }
    }
  }

  candidates.sort((left, right) => right.confidence - left.confidence || right.radius - left.radius);
  const selected: DetectedFan[] = [];
  for (const candidate of candidates) {
    const duplicate = selected.some(existing => {
      const dx = (candidate.centerX - existing.centerX) * width;
      const dy = (candidate.centerY - existing.centerY) * height;
      const candidateRadiusPx = candidate.radius * minDimension;
      const existingRadiusPx = existing.radius * minDimension;
      const similarScale = Math.min(candidateRadiusPx, existingRadiusPx) /
        Math.max(candidateRadiusPx, existingRadiusPx) > 0.58;
      return similarScale && Math.hypot(dx, dy) < Math.max(candidateRadiusPx, existingRadiusPx) * 0.9;
    });
    if (!duplicate) selected.push(candidate);
    if (selected.length === MAX_DETECTIONS) break;
  }

  return selected.sort((left, right) => left.centerY - right.centerY || left.centerX - right.centerX);
}
