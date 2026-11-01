import { TextureLoader } from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

export function createAvatarGLTFLoader() {
  const loader = new GLTFLoader();
  loader.register((parser) => ({
    name: "HermesBrowserImageTextures",
    beforeRoot: () => {
      // The avatar's embedded PNGs can fail through ImageBitmapLoader's
      // fetch/createImageBitmap path. Use browser image decoding for this
      // decorative avatar, without changing the product review loaders.
      parser.textureLoader = new TextureLoader(loader.manager)
        .setCrossOrigin(loader.crossOrigin);
      return null;
    },
  }));
  return loader;
}
