import { afterEach, expect, it, vi } from "vitest";
import { ImageBitmapLoader, Texture, TextureLoader } from "three";
import { createAvatarGLTFLoader } from "./avatar-gltf-loader";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("retains embedded avatar textures when browser bitmap decoding fails", async () => {
  vi.stubGlobal("createImageBitmap", vi.fn());
  vi.stubGlobal("URL", class extends URL {
    static createObjectURL = vi.fn(() => "blob:http://localhost/avatar-texture");
    static revokeObjectURL = vi.fn();
  });
  const bitmapLoad = vi.spyOn(ImageBitmapLoader.prototype, "load").mockImplementation(
    (_url, _onLoad, _progress, onError) => { onError?.(new Error("Bitmap decode failed")); },
  );
  const texture = new Texture(document.createElement("img"));
  const imageLoad = vi.spyOn(TextureLoader.prototype, "load").mockImplementation(
    (_url, onLoad) => { onLoad?.(texture); return texture; },
  );
  vi.spyOn(console, "error").mockImplementation(() => {});
  // GLTFLoader reaches the same embedded-image/blob path used by bot.glb.
  const gltf = await createAvatarGLTFLoader().parseAsync(JSON.stringify({
    asset: { version: "2.0" }, scenes: [{ nodes: [] }], scene: 0,
    buffers: [{ uri: "data:application/octet-stream;base64,AA==", byteLength: 1 }],
    bufferViews: [{ buffer: 0, byteLength: 1 }],
    images: [{ bufferView: 0, mimeType: "image/png" }],
    textures: [{ source: 0 }],
  }), "");
  // Isolate decoding: the buffer contents are irrelevant to our decoder stubs.
  vi.spyOn(gltf.parser, "getDependency").mockImplementation(async (type: string) => {
    if (type === "bufferView") return new ArrayBuffer(1);
    throw new Error(`Unexpected dependency: ${type}`);
  });
  const loaded = await gltf.parser.loadTexture(0);
  expect(loaded).toBe(texture);
  expect(imageLoad).toHaveBeenCalledWith("blob:http://localhost/avatar-texture", expect.any(Function), undefined, expect.any(Function));
  expect(bitmapLoad).not.toHaveBeenCalled();
});
