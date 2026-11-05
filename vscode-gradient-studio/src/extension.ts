import * as vscode from "vscode";

type Gradient = { name: string; description: string; stops: [string, string, ...string[]] };

const gradients: Gradient[] = [
  { name: "Aurora", description: "Deep teal into midnight blue", stops: ["#153b42", "#172f49", "#24264b"] },
  { name: "Amethyst Haze", description: "Soft violet with a rose glow", stops: ["#392b50", "#382d4c", "#4b3048"] },
  { name: "Dusk", description: "Warm plum fading into indigo", stops: ["#452c45", "#38304e", "#292d4a"] },
  { name: "Moss Garden", description: "Muted forest greens", stops: ["#293f38", "#2c3d3b", "#2d3740"] },
  { name: "Ember", description: "Burnt coral with a cocoa base", stops: ["#53353a", "#49343d", "#3c3444"] },
  { name: "Arctic", description: "Cool slate and glacial blue", stops: ["#293f50", "#2c3c50", "#32374c"] },
  { name: "Peach Bloom", description: "A gentle rose-to-peach wash", stops: ["#543a42", "#504047", "#48414a"] },
  { name: "Sage", description: "Quiet sage over charcoal", stops: ["#34433d", "#373f3d", "#393a41"] },
  { name: "Solar Flare", description: "Golden amber into warm dusk", stops: ["#51402e", "#4b3a34", "#413341"] },
  { name: "Ocean Glass", description: "Sea glass and deep blue", stops: ["#2b4548", "#2b3e4a", "#30384a"] }
];

const ROWS = 96;
let activeGradient: Gradient | undefined;
let rowDecorations: vscode.TextEditorDecorationType[] = [];
let baseBackground: string | undefined;
let extensionContext: vscode.ExtensionContext | undefined;

function hexRgb(hex: string): [number, number, number] {
  const value = hex.replace("#", "");
  return [parseInt(value.slice(0, 2), 16), parseInt(value.slice(2, 4), 16), parseInt(value.slice(4, 6), 16)];
}

function interpolate(stops: string[], progress: number): string {
  const position = Math.max(0, Math.min(1, progress)) * (stops.length - 1);
  const segment = Math.min(Math.floor(position), stops.length - 2);
  const amount = position - segment;
  const from = hexRgb(stops[segment]);
  const to = hexRgb(stops[segment + 1]);
  const channels = from.map((channel, index) => Math.round(channel + (to[index] - channel) * amount));
  return `#${channels.map(channel => channel.toString(16).padStart(2, "0")).join("")}`;
}

function createRowDecorations(): void {
  rowDecorations.forEach(decoration => decoration.dispose());
  rowDecorations = Array.from({ length: ROWS }, (_, index) => vscode.window.createTextEditorDecorationType({
    isWholeLine: true,
    backgroundColor: interpolate(activeGradient!.stops, index / (ROWS - 1))
  }));
}

function applyGradient(editor: vscode.TextEditor): void {
  if (!activeGradient) return;
  const visible = editor.visibleRanges;
  const first = visible[0]?.start.line ?? 0;
  const last = visible[visible.length - 1]?.end.line ?? first;
  const lineCount = Math.max(1, last - first + 1);
  const decorationCount = Math.min(ROWS, lineCount);

  for (let index = 0; index < ROWS; index++) {
    const line = first + Math.round((lineCount - 1) * index / Math.max(1, decorationCount - 1));
    if (index < decorationCount && line < editor.document.lineCount) {
      editor.setDecorations(rowDecorations[index], [new vscode.Range(line, 0, line, 0)]);
    }
  }
}

function refreshVisibleEditors(): void {
  for (const editor of vscode.window.visibleTextEditors) applyGradient(editor);
}

async function selectGradient(): Promise<void> {
  const items = gradients.map(gradient => ({ label: gradient.name, description: gradient.description, gradient }));
  const selected = await vscode.window.showQuickPick(items, {
    title: "Choose an editor gradient",
    placeHolder: "Pick a colour mood"
  });
  if (!selected) return;

  const configuration = vscode.workspace.getConfiguration("workbench");
  const customizations = configuration.get<Record<string, unknown>>("colorCustomizations", {});
  if (!activeGradient) {
    baseBackground = typeof customizations["editor.background"] === "string" ? customizations["editor.background"] as string : undefined;
  }
  activeGradient = selected.gradient;
  await configuration.update("colorCustomizations", {
    ...customizations,
    "editor.background": interpolate(activeGradient.stops, 0.5)
  }, vscode.ConfigurationTarget.Global);
  createRowDecorations();
  refreshVisibleEditors();
  await extensionContext?.globalState.update("gradientStudio.active", {
    name: activeGradient.name,
    baseBackground
  });
  vscode.window.setStatusBarMessage(`Gradient Studio: ${activeGradient.name}`, 3000);
}

async function clearGradient(): Promise<void> {
  if (!activeGradient) return;
  const configuration = vscode.workspace.getConfiguration("workbench");
  const customizations = configuration.get<Record<string, unknown>>("colorCustomizations", {});
  const next = { ...customizations };
  if (baseBackground === undefined) delete next["editor.background"];
  else next["editor.background"] = baseBackground;
  await configuration.update("colorCustomizations", next, vscode.ConfigurationTarget.Global);
  activeGradient = undefined;
  for (const editor of vscode.window.visibleTextEditors) {
    for (const decoration of rowDecorations) editor.setDecorations(decoration, []);
  }
  rowDecorations.forEach(decoration => decoration.dispose());
  rowDecorations = [];
  await extensionContext?.globalState.update("gradientStudio.active", undefined);
  baseBackground = undefined;
  vscode.window.setStatusBarMessage("Gradient Studio: cleared", 3000);
}

export function activate(context: vscode.ExtensionContext): void {
  extensionContext = context;
  const saved = context.globalState.get<{ name: string; baseBackground?: string }>("gradientStudio.active");
  if (saved) {
    activeGradient = gradients.find(gradient => gradient.name === saved.name);
    baseBackground = saved.baseBackground;
    if (activeGradient) {
      createRowDecorations();
      refreshVisibleEditors();
    }
  }
  context.subscriptions.push(
    vscode.commands.registerCommand("gradientStudio.chooseGradient", selectGradient),
    vscode.commands.registerCommand("gradientStudio.clearGradient", clearGradient),
    vscode.window.onDidChangeTextEditorVisibleRanges(refreshVisibleEditors),
    vscode.window.onDidChangeActiveTextEditor(editor => { if (editor && activeGradient) applyGradient(editor); })
  );
}

export function deactivate(): void {
  rowDecorations.forEach(decoration => decoration.dispose());
}
