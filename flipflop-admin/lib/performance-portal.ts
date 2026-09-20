import * as fs from "fs/promises";
import * as path from "path";

const repoRoot = path.resolve(process.cwd(), "..");
const buildsRoot = path.join(repoRoot, "builds");
const templateRoot = path.join(repoRoot, "Personalised Website");

async function directoryExists(directory: string): Promise<boolean> {
  try {
    return (await fs.stat(directory)).isDirectory();
  } catch {
    return false;
  }
}

export async function resolveBuildDirectory(buildId: string): Promise<string> {
  if (!/^\d+$/.test(buildId)) {
    throw new Error("A valid numeric build_id is required");
  }

  const candidates = [
    path.join(buildsRoot, buildId.padStart(3, "0")),
    path.join(buildsRoot, buildId),
  ];
  for (const candidate of candidates) {
    if (await directoryExists(candidate)) return candidate;
  }

  // Keep the canonical folder name stable for newly created builds.
  return candidates[0];
}

/**
 * Materialise the shared Personalised Website template inside one build's
 * listing pack. The uploaded JSON is the only build-specific input; the HTML
 * shell, renderer, and shared assets remain the single source of truth in the
 * sibling Personalised Website project.
 */
export async function createBuildPerformancePortal(
  buildId: string,
  performanceData: unknown,
): Promise<{ buildDir: string; targetDir: string; portalPath: string }> {
  const buildDir = await resolveBuildDirectory(buildId);
  const targetDir = path.join(buildDir, "Performance");
  const sourceIndex = path.join(templateRoot, "index.html");
  const sourceRenderer = path.join(templateRoot, "render.js");
  const sourceAssets = path.join(templateRoot, "assets");

  await Promise.all([
    fs.access(sourceIndex),
    fs.access(sourceRenderer),
    fs.access(sourceAssets),
  ]);
  await fs.mkdir(targetDir, { recursive: true });

  // The URL exposed in the listing pack is deliberately named performance.html
  // while the source project keeps index.html as its local entry point.
  await Promise.all([
    fs.copyFile(sourceIndex, path.join(targetDir, "performance.html")),
    fs.copyFile(sourceRenderer, path.join(targetDir, "render.js")),
    fs.writeFile(
      path.join(targetDir, "performance-data.json"),
      JSON.stringify(performanceData, null, 2),
      "utf-8",
    ),
  ]);
  await fs.cp(sourceAssets, path.join(targetDir, "assets"), {
    recursive: true,
    force: true,
  });

  return {
    buildDir,
    targetDir,
    portalPath: path.join(targetDir, "performance.html"),
  };
}
