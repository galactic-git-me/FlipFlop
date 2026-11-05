# Gradient Studio

Pick a curated colour gradient and give your VS Code editor a calm, colourful background. Gradient Studio draws the blend as subtle, full-line editor decorations and tracks the visible editor area as you scroll.

## Use it

1. Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`).
2. Run **Gradient Studio: Choose Editor Gradient**.
3. Pick a gradient. Run **Gradient Studio: Clear Editor Gradient** to restore your theme's editor background.

You can also use `Ctrl+Alt+G` (`Cmd+Alt+G` on macOS) to open the picker.

The extension adjusts the editor background setting while a gradient is active. Clearing restores the previous value. The gradient is rendered with line decorations because VS Code's theme API accepts solid editor background colours, not CSS gradients.

## Develop

Run `npm install`, then `npm run compile`. Press `F5` in VS Code to launch an Extension Development Host.
