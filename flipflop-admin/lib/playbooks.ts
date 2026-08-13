/**
 * PC Playbooks - Define ideal component specs for different user types
 * Each playbook has 3 tiers: Budget, Mid-range, High-end
 */

export type PlaybookTier = "budget" | "midrange" | "highend";
export type ComponentType = "CPU" | "Motherboard" | "RAM" | "PSU" | "SSD" | "GPU" | "Cooler" | "Case" | "Fan";

export interface ComponentSpec {
  type: ComponentType;
  minPerf?: string;
  preferredBrand?: string[];
  maxPrice?: number;
  notes?: string;
}

export interface BuildProfile {
  tier: PlaybookTier;
  budgetUSD: number;
  components: ComponentSpec[];
  description: string;
}

export interface Playbook {
  id: string;
  name: string;
  description: string;
  icon: string;
  useCase: string;
  audience: string;
  builds: {
    budget: BuildProfile;
    midrange: BuildProfile;
    highend: BuildProfile;
  };
}

export const PLAYBOOKS: Record<string, Playbook> = {
  gaming: {
    id: "gaming",
    name: "Gaming PC",
    description: "High-performance gaming with ray tracing and 1440p+ gaming",
    icon: "🎮",
    useCase: "Competitive gaming, AAA titles, streaming gameplay",
    audience: "Gamers seeking high FPS and visual fidelity",
    builds: {
      budget: {
        tier: "budget",
        budgetUSD: 700,
        description: "1080p gaming @ 100+ FPS, entry ray tracing",
        components: [
          { type: "CPU", minPerf: "Ryzen 5 or Intel Core i5", preferredBrand: ["AMD", "Intel"], maxPrice: 200 },
          { type: "Motherboard", minPerf: "AM4/LGA1700", maxPrice: 120 },
          { type: "RAM", minPerf: "16GB DDR4/DDR5", preferredBrand: ["Corsair", "G.Skill"], maxPrice: 80 },
          { type: "GPU", minPerf: "RTX 4060 / RX 7600", maxPrice: 250 },
          { type: "SSD", minPerf: "500GB-1TB NVMe", maxPrice: 60 },
          { type: "PSU", minPerf: "550W 80+", maxPrice: 70 },
          { type: "Case", minPerf: "Mid tower", maxPrice: 60 },
          { type: "Cooler", minPerf: "Stock or budget tower", maxPrice: 30 },
        ],
      },
      midrange: {
        tier: "midrange",
        budgetUSD: 1300,
        description: "1440p gaming @ 100+ FPS, full ray tracing enabled",
        components: [
          { type: "CPU", minPerf: "Ryzen 7 or Intel Core i7", preferredBrand: ["AMD", "Intel"], maxPrice: 400 },
          { type: "Motherboard", minPerf: "AM5/LGA1700, PCIe 5.0", maxPrice: 200 },
          { type: "RAM", minPerf: "32GB DDR5", preferredBrand: ["Corsair", "G.Skill"], maxPrice: 150 },
          { type: "GPU", minPerf: "RTX 4070 / RX 7800 XT", maxPrice: 500 },
          { type: "SSD", minPerf: "1TB NVMe PCIe 4.0", maxPrice: 100 },
          { type: "PSU", minPerf: "750W 80+ Gold", maxPrice: 120 },
          { type: "Case", minPerf: "Mid-tower, good cooling", maxPrice: 100 },
          { type: "Cooler", minPerf: "240mm AIO or tower", maxPrice: 80 },
        ],
      },
      highend: {
        tier: "highend",
        budgetUSD: 2500,
        description: "4K gaming @ 60+ FPS, max settings, ray tracing ultra",
        components: [
          { type: "CPU", minPerf: "Ryzen 9 or Intel Core i9", preferredBrand: ["AMD", "Intel"], maxPrice: 600 },
          { type: "Motherboard", minPerf: "AM5/LGA1700, PCIe 5.0, top tier", maxPrice: 350 },
          { type: "RAM", minPerf: "64GB DDR5 high speed", preferredBrand: ["Corsair", "G.Skill"], maxPrice: 300 },
          { type: "GPU", minPerf: "RTX 4090 / RX 7900 XTX", maxPrice: 1000 },
          { type: "SSD", minPerf: "2TB NVMe PCIe 5.0", maxPrice: 250 },
          { type: "PSU", minPerf: "1000W 80+ Platinum", maxPrice: 200 },
          { type: "Case", minPerf: "Premium, excellent cooling", maxPrice: 200 },
          { type: "Cooler", minPerf: "360mm AIO or premium tower", maxPrice: 150 },
        ],
      },
    },
  },

  workstation: {
    id: "workstation",
    name: "Content Creator",
    description: "Video editing, 3D rendering, photo processing, streaming",
    icon: "🎬",
    useCase: "4K video editing, 3D render farms, photo batch processing",
    audience: "Content creators, video editors, graphic designers",
    builds: {
      budget: {
        tier: "budget",
        budgetUSD: 1000,
        description: "1080p/4K timeline scrubbing, basic rendering",
        components: [
          { type: "CPU", minPerf: "Ryzen 7 or Intel Core i7 (12+ cores)", preferredBrand: ["AMD", "Intel"], maxPrice: 300 },
          { type: "Motherboard", minPerf: "AM4/LGA1700", maxPrice: 150 },
          { type: "RAM", minPerf: "32GB DDR4/DDR5", preferredBrand: ["Corsair", "G.Skill"], maxPrice: 150 },
          { type: "GPU", minPerf: "RTX 4060 Ti / RX 7600", maxPrice: 300 },
          { type: "SSD", minPerf: "2x1TB NVMe", maxPrice: 150 },
          { type: "PSU", minPerf: "650W 80+", maxPrice: 80 },
          { type: "Case", minPerf: "Mid tower", maxPrice: 80 },
          { type: "Cooler", minPerf: "Good airflow cooler", maxPrice: 60 },
        ],
      },
      midrange: {
        tier: "midrange",
        budgetUSD: 2000,
        description: "Smooth 4K editing, fast renders, streaming capable",
        components: [
          { type: "CPU", minPerf: "Ryzen 9 7950X / Intel Core i9 (16+ cores)", preferredBrand: ["AMD", "Intel"], maxPrice: 600 },
          { type: "Motherboard", minPerf: "AM5/LGA1700, PCIe 5.0", maxPrice: 250 },
          { type: "RAM", minPerf: "64GB DDR5", preferredBrand: ["Corsair", "G.Skill"], maxPrice: 400 },
          { type: "GPU", minPerf: "RTX 4070 / RX 7800 XT", maxPrice: 500 },
          { type: "SSD", minPerf: "NVMe RAID setup, 4TB total", maxPrice: 300 },
          { type: "PSU", minPerf: "850W 80+ Gold", maxPrice: 140 },
          { type: "Case", minPerf: "Good airflow, cable mgmt", maxPrice: 120 },
          { type: "Cooler", minPerf: "280mm+ AIO", maxPrice: 100 },
        ],
      },
      highend: {
        tier: "highend",
        budgetUSD: 4000,
        description: "8K timeline, instant renders, professional workflows",
        components: [
          { type: "CPU", minPerf: "Ryzen Threadripper / Intel Xeon (32+ cores)", preferredBrand: ["AMD"], maxPrice: 1500 },
          { type: "Motherboard", minPerf: "TRX50 or professional platform", maxPrice: 500 },
          { type: "RAM", minPerf: "192GB DDR5 ECC", preferredBrand: ["Corsair", "G.Skill"], maxPrice: 1000 },
          { type: "GPU", minPerf: "RTX 6000 Ada or RTX 4090", maxPrice: 1500 },
          { type: "SSD", minPerf: "8TB+ NVMe multi-drive setup", maxPrice: 800 },
          { type: "PSU", minPerf: "1500W Titanium", maxPrice: 400 },
          { type: "Case", minPerf: "Professional workstation case", maxPrice: 300 },
          { type: "Cooler", minPerf: "Custom loop or premium AIO", maxPrice: 300 },
        ],
      },
    },
  },

  productivity: {
    id: "productivity",
    name: "Productivity",
    description: "Office work, multitasking, coding, general computing",
    icon: "💼",
    useCase: "Programming, office work, browsing, light multitasking",
    audience: "Developers, office workers, general users",
    builds: {
      budget: {
        tier: "budget",
        budgetUSD: 500,
        description: "Smooth office work, light coding",
        components: [
          { type: "CPU", minPerf: "Ryzen 5 or Intel Core i5", preferredBrand: ["AMD", "Intel"], maxPrice: 150 },
          { type: "Motherboard", minPerf: "AM4/LGA1700", maxPrice: 100 },
          { type: "RAM", minPerf: "16GB DDR4", preferredBrand: ["Corsair", "G.Skill"], maxPrice: 60 },
          { type: "GPU", minPerf: "Integrated (no discrete GPU)", maxPrice: 0 },
          { type: "SSD", minPerf: "512GB NVMe", maxPrice: 50 },
          { type: "PSU", minPerf: "400W 80+", maxPrice: 50 },
          { type: "Case", minPerf: "Budget mid tower", maxPrice: 50 },
          { type: "Cooler", minPerf: "Stock cooler", maxPrice: 0 },
        ],
      },
      midrange: {
        tier: "midrange",
        budgetUSD: 900,
        description: "Fluid multitasking, heavy IDE work, video calls",
        components: [
          { type: "CPU", minPerf: "Ryzen 7 or Intel Core i7", preferredBrand: ["AMD", "Intel"], maxPrice: 300 },
          { type: "Motherboard", minPerf: "AM5/LGA1700", maxPrice: 150 },
          { type: "RAM", minPerf: "32GB DDR5", preferredBrand: ["Corsair", "G.Skill"], maxPrice: 200 },
          { type: "GPU", minPerf: "RTX 3060 or iGPU", maxPrice: 150 },
          { type: "SSD", minPerf: "1TB NVMe", maxPrice: 80 },
          { type: "PSU", minPerf: "550W 80+ Bronze", maxPrice: 70 },
          { type: "Case", minPerf: "Mid tower with good airflow", maxPrice: 80 },
          { type: "Cooler", minPerf: "120mm tower cooler", maxPrice: 40 },
        ],
      },
      highend: {
        tier: "highend",
        budgetUSD: 1500,
        description: "Ultimate multitasking, virtualization, heavy dev work",
        components: [
          { type: "CPU", minPerf: "Ryzen 9 or Intel Core i9", preferredBrand: ["AMD", "Intel"], maxPrice: 500 },
          { type: "Motherboard", minPerf: "AM5/LGA1700 premium", maxPrice: 250 },
          { type: "RAM", minPerf: "64GB DDR5", preferredBrand: ["Corsair", "G.Skill"], maxPrice: 400 },
          { type: "GPU", minPerf: "RTX 4070 Super or better", maxPrice: 300 },
          { type: "SSD", minPerf: "2TB NVMe PCIe 4.0", maxPrice: 150 },
          { type: "PSU", minPerf: "750W 80+ Gold", maxPrice: 120 },
          { type: "Case", minPerf: "Premium mid tower", maxPrice: 120 },
          { type: "Cooler", minPerf: "240mm AIO", maxPrice: 80 },
        ],
      },
    },
  },

  streaming: {
    id: "streaming",
    name: "Streaming PC",
    description: "Twitch/YouTube streaming with high bitrate encoding",
    icon: "📡",
    useCase: "Live streaming, encoding to multiple platforms, secondary stream PC",
    audience: "Twitch/YouTube streamers, live event broadcasters",
    builds: {
      budget: {
        tier: "budget",
        budgetUSD: 800,
        description: "1080p60 stream @ 6Mbps with light gameplay",
        components: [
          { type: "CPU", minPerf: "Ryzen 7 5700X or Intel i7-10700 (8+ cores)", preferredBrand: ["AMD", "Intel"], maxPrice: 250 },
          { type: "Motherboard", minPerf: "AM4/LGA1200", maxPrice: 120 },
          { type: "RAM", minPerf: "32GB DDR4", preferredBrand: ["Corsair", "G.Skill"], maxPrice: 120 },
          { type: "GPU", minPerf: "RTX 3050 or GTX 1050 Ti", maxPrice: 150 },
          { type: "SSD", minPerf: "1TB NVMe for OS + cache", maxPrice: 80 },
          { type: "PSU", minPerf: "600W 80+", maxPrice: 70 },
          { type: "Case", minPerf: "Mid tower", maxPrice: 60 },
          { type: "Cooler", minPerf: "Stock or budget tower", maxPrice: 40 },
        ],
      },
      midrange: {
        tier: "midrange",
        budgetUSD: 1400,
        description: "1440p60 stream + gameplay, or 4K30 stream",
        components: [
          { type: "CPU", minPerf: "Ryzen 7 7700X or Intel i7-13700KF (12+ cores)", preferredBrand: ["AMD", "Intel"], maxPrice: 400 },
          { type: "Motherboard", minPerf: "AM5/LGA1700", maxPrice: 200 },
          { type: "RAM", minPerf: "32GB DDR5", preferredBrand: ["Corsair", "G.Skill"], maxPrice: 200 },
          { type: "GPU", minPerf: "RTX 4070 Super or RX 7800 XT", maxPrice: 450 },
          { type: "SSD", minPerf: "2TB NVMe", maxPrice: 150 },
          { type: "PSU", minPerf: "800W 80+ Gold", maxPrice: 130 },
          { type: "Case", minPerf: "Mid-tower, good cooling", maxPrice: 100 },
          { type: "Cooler", minPerf: "240mm AIO", maxPrice: 80 },
        ],
      },
      highend: {
        tier: "highend",
        budgetUSD: 2200,
        description: "4K60 stream + high-end gameplay simultaneously",
        components: [
          { type: "CPU", minPerf: "Ryzen 9 9900X3D or Intel Core i9-14900KS", preferredBrand: ["AMD", "Intel"], maxPrice: 700 },
          { type: "Motherboard", minPerf: "AM5/LGA1700 premium", maxPrice: 300 },
          { type: "RAM", minPerf: "64GB DDR5 high speed", preferredBrand: ["Corsair", "G.Skill"], maxPrice: 350 },
          { type: "GPU", minPerf: "RTX 4080 Super or RX 7900 XT", maxPrice: 700 },
          { type: "SSD", minPerf: "2x2TB NVMe setup", maxPrice: 300 },
          { type: "PSU", minPerf: "1000W 80+ Gold", maxPrice: 180 },
          { type: "Case", minPerf: "Premium airflow case", maxPrice: 180 },
          { type: "Cooler", minPerf: "360mm AIO or custom", maxPrice: 150 },
        ],
      },
    },
  },

  homelabserver: {
    id: "homelabserver",
    name: "Home Server",
    description: "NAS, media server, home automation, virtualization host",
    icon: "🖥️",
    useCase: "NAS/storage, Plex media server, VM host, 24/7 operation",
    audience: "Homelab enthusiasts, server administrators, digital archivists",
    builds: {
      budget: {
        tier: "budget",
        budgetUSD: 600,
        description: "4-bay NAS, light virtualization, media serving",
        components: [
          { type: "CPU", minPerf: "Ryzen 5 5600H or Intel Core i5-11400", preferredBrand: ["AMD", "Intel"], maxPrice: 150 },
          { type: "Motherboard", minPerf: "AM4/LGA1200", maxPrice: 100 },
          { type: "RAM", minPerf: "32GB ECC DDR4 (if supported)", preferredBrand: ["Corsair", "Kingston"], maxPrice: 150 },
          { type: "GPU", minPerf: "None needed (iGPU suffices)", maxPrice: 0 },
          { type: "SSD", minPerf: "256GB NVMe for OS", maxPrice: 30 },
          { type: "PSU", minPerf: "500W 80+ (low power draw)", maxPrice: 60 },
          { type: "Case", minPerf: "NAS case 4-bay", maxPrice: 100 },
          { type: "Cooler", minPerf: "Stock cooler", maxPrice: 0 },
        ],
      },
      midrange: {
        tier: "midrange",
        budgetUSD: 1200,
        description: "8-bay NAS, smooth virtualization, 4K transcoding",
        components: [
          { type: "CPU", minPerf: "Ryzen 7 5700 or Intel Xeon E-2388G", preferredBrand: ["AMD", "Intel"], maxPrice: 400 },
          { type: "Motherboard", minPerf: "AM4 or C422 chipset", maxPrice: 200 },
          { type: "RAM", minPerf: "64GB ECC DDR4/DDR5", preferredBrand: ["Corsair", "Kingston"], maxPrice: 350 },
          { type: "GPU", minPerf: "RTX 3050 for transcoding", maxPrice: 150 },
          { type: "SSD", minPerf: "512GB NVMe + large HDD array", maxPrice: 100 },
          { type: "PSU", minPerf: "750W 80+ Silver (24/7)", maxPrice: 100 },
          { type: "Case", minPerf: "NAS case 8-bay professional", maxPrice: 200 },
          { type: "Cooler", minPerf: "Quiet tower cooler", maxPrice: 50 },
        ],
      },
      highend: {
        tier: "highend",
        budgetUSD: 2500,
        description: "16+ bay NAS, high VM density, perfect transcoding",
        components: [
          { type: "CPU", minPerf: "Ryzen 9 7900 or Xeon Platinum (16+ cores)", preferredBrand: ["AMD", "Intel"], maxPrice: 800 },
          { type: "Motherboard", minPerf: "TRX50 or Xeon platform", maxPrice: 400 },
          { type: "RAM", minPerf: "256GB ECC DDR5", preferredBrand: ["Corsair", "Kingston"], maxPrice: 1000 },
          { type: "GPU", minPerf: "RTX 4070 or RTX 6000 Ada", maxPrice: 500 },
          { type: "SSD", minPerf: "2TB NVMe + redundant HDD array", maxPrice: 400 },
          { type: "PSU", minPerf: "1200W 80+ Gold (24/7 rated)", maxPrice: 250 },
          { type: "Case", minPerf: "Professional 16+ bay chassis", maxPrice: 400 },
          { type: "Cooler", minPerf: "Premium quiet tower/AIO", maxPrice: 150 },
        ],
      },
    },
  },
};

export function getPlaybook(id: string): Playbook | undefined {
  return PLAYBOOKS[id];
}

export function getAllPlaybooks(): Playbook[] {
  return Object.values(PLAYBOOKS);
}

export function getBuildProfile(playbookId: string, tier: PlaybookTier): BuildProfile | null {
  const playbook = getPlaybook(playbookId);
  if (!playbook) return null;
  return playbook.builds[tier];
}
