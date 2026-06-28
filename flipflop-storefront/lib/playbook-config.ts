interface PlaybookMeta {
  slug: string;
  emoji: string;
  tagline: string;
  description: string;
}

// Keys are lowercase substrings matched against playbook.name
const PLAYBOOK_META: Record<string, PlaybookMeta> = {
  gaming: {
    slug: "gaming-rig",
    emoji: "🎮",
    tagline: "Built to dominate",
    description: "High-refresh gaming with curated GPUs and CPUs scored for frame-rate performance.",
  },
  ai: {
    slug: "ai-machine",
    emoji: "🤖",
    tagline: "Train, infer, iterate",
    description: "VRAM-heavy builds optimised for local AI inference and model training.",
  },
  creative: {
    slug: "creative-studio",
    emoji: "🎨",
    tagline: "Render at full speed",
    description: "Multi-core CPU and GPU builds for video editing, 3D, and creative workloads.",
  },
  build: {
    slug: "build-your-own",
    emoji: "⚙️",
    tagline: "Full control",
    description: "Pick every component yourself from our curated catalogue of verified gems.",
  },
  home: {
    slug: "home-office",
    emoji: "🏠",
    tagline: "Quiet, fast, reliable",
    description: "Balanced everyday computing — fast enough for anything, quiet enough for any room.",
  },
  business: {
    slug: "business-workstation",
    emoji: "💼",
    tagline: "Professional grade",
    description: "Reliable, maintainable workstations for business productivity and remote work.",
  },
  student: {
    slug: "student-pc",
    emoji: "📚",
    tagline: "More power, less spend",
    description: "Capable builds at student budget — great for coursework, coding, and light gaming.",
  },
};

const DEFAULT_META: Omit<PlaybookMeta, "slug"> = {
  emoji: "💻",
  tagline: "Quality components, expert assembly",
  description: "Curated PC builds from verified second-hand components — tested before delivery.",
};

export function getPlaybookMeta(name: string): PlaybookMeta {
  const lower = name.toLowerCase();
  for (const [key, meta] of Object.entries(PLAYBOOK_META)) {
    if (lower.includes(key)) return meta;
  }
  return { slug: slugifyFallback(name), ...DEFAULT_META };
}

function slugifyFallback(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

// Used on the landing page to build hrefs
export function playbookSlug(name: string): string {
  return getPlaybookMeta(name).slug;
}
