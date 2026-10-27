// Customer requirements for the current cells, not measured performance claims.
// Keep presentation copy separate from the hashed hardware/pricing definitions.
const CUSTOMER_NEEDS: Record<string, string> = {
  "FF-GVG-01": "I want my first gaming PC for a 1080p screen, esports and everyday games. I need sensible running costs and room for my game library.",
  "FF-GVG-02": "I want to move up to 1440p gaming and occasionally stream or record my sessions. I need enough graphics memory and storage for newer games.",
  "FF-GVG-03": "I want smoother 1440p gaming and the option to try 4K. I am happy to adjust game settings to get better value from the hardware.",
  "FF-HPG-01": "I spend a lot of time gaming at 1440p and also make clips or stream. I need the PC to handle the game and those background tasks together.",
  "FF-HPG-02": "I want a premium gaming setup for demanding games at 1440p or 4K. Appearance, cooling and keeping noise comfortable during long sessions matter to me.",
  "FF-HPG-03": "I want to build around a high-refresh 4K screen or a VR headset. Gaming is the priority, with capacity for demanding creative work as well.",
  "FF-STU-01": "I need a dependable study desktop for assignments, research, video lessons and learning to code. It should handle several apps at once and be easy to repair or upgrade.",
  "FF-STU-02": "I need one PC for university work, coding and gaming after classes. It should keep coursework, development tools and a growing game library together.",
  "FF-STU-03": "My course involves design, engineering or creative software as well as coding. I need memory and graphics capacity for larger projects, plus gaming in my downtime.",
  "FF-BOF-01": "I need everyday office work to feel responsive: email, accounts, browser tabs and documents. A tidy desk and support for my office displays matter more than gaming graphics.",
  "FF-BOF-02": "I work across spreadsheets, video meetings and several business systems all day. I need comfortable multitasking, multiple displays and a quiet machine beside my desk.",
  "FF-BOF-03": "I work with large spreadsheets, many open applications and demanding local business software. I need more memory and processing headroom, with serviceable parts for long-term use.",
  "FF-CCR-01": "I create photos, videos and streams and want to bring that work onto one desktop. I need room for source files and a practical starting point for 4K editing.",
  "FF-CCR-02": "I edit larger video projects and use effects or 3D tools for client work. I need more memory, graphics capacity and separate space for projects and working files.",
  "FF-CCR-03": "I handle complex post-production, high-resolution footage, VFX or large 3D scenes. I need substantial processing, graphics memory and storage capacity for demanding projects.",
  "FF-AIW-01": "I want to try private local AI, coding assistants and smaller quantised language models. I need a practical entry point, with model size chosen to fit the available graphics memory.",
  "FF-AIW-02": "I want to work with larger local AI models and data without relying on cloud services for everything. I need more graphics memory and software that supports the selected GPU.",
  "FF-AIW-03": "I need a dedicated local AI workstation for larger models and repeated inference work. Graphics memory, system memory and sustained cooling matter; model fit and concurrent users need checking for my workload.",
  "FF-SWD-01": "I need a responsive coding desktop for my editor, containers and local databases. I want enough memory to run the application and its supporting services together.",
  "FF-SWD-02": "I work with larger codebases, several containers or virtual machines and local AI tools. I need more memory, fast project storage and graphics capacity for supported AI workloads.",
  "FF-SWD-03": "I need to compile large projects and run several development or test environments locally. I need substantial CPU and memory capacity, plus GPU compute for tools that can use it.",
  "FF-FAM-01": "We need a dependable shared PC for homework, browsing, video calls and family photos. It should be straightforward to use and handle everyday tasks without unnecessary cost.",
  "FF-FAM-02": "We want one family PC for schoolwork, photos, entertainment and proper gaming. We need space for several people's files and enough graphics capacity for a 1440p gaming setup.",
  "FF-FAM-03": "We want a shared home hub for photo and video projects, home-office work, media and gaming. We need more storage and multitasking capacity as the family's needs grow.",
};

export function customerNeeds(cell: { cell_id: string; definition: { use?: string } }): string {
  return CUSTOMER_NEEDS[cell.cell_id] ?? cell.definition.use ?? "Customer requirements have not been recorded for this build.";
}
