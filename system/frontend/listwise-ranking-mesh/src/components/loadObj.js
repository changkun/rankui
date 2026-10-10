import {
  Mesh,
  MeshPhongMaterial,
  Vector3,
  LineSegments,
  WireframeGeometry,
  LineBasicMaterial,
  DoubleSide,
  Object3D,
  BufferAttribute,
  Color,
} from "three";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader";

/**
 * loadOBJ loads the object file from the given path, then adds all
 * parsed geometries into the scene graph.
 *
 * @param path is a URI that locates the obj file. If it is not an obj
 * file, nothing happens.
 * @param config is the rendering configuration that determines the
 * initial rendering effects.
 */
export const loadOBJ = async (path: string, config: RenderConfig) => {
  const g = await new Promise((resolve) => new OBJLoader().load(path, resolve));
  const meshes: Object3D[] = [];

  for (const obj of g.children) {
    // We are certain that a child is a Mesh object unless three.js breaks
    // its compatibility.
    obj.geometry.computeBoundingBox();
    // bondingBox is always avaliable if we just computed.
    const aabb = obj.geometry.boundingBox

    // Normalize the object to fit an unit code.
    const scalingFactor = Math.sqrt(3) / new Vector3().subVectors(aabb.max, aabb.min).length();
    const g = obj.geometry.center().scale(scalingFactor, scalingFactor, scalingFactor);
    const nverts = g.getAttribute("position").count;
    const colors = new Float32Array(3 * nverts);
    const blue = new Color(0x0080ff);
    for (let i = 0; i < nverts; i++) {
      colors[3 * i + 0] = blue.r;
      colors[3 * i + 1] = blue.g;
      colors[3 * i + 2] = blue.b;
    }
    g.setAttribute("color", new BufferAttribute(colors, 3));
    const mat = new MeshPhongMaterial({
      flatShading: false,
      side: DoubleSide,
      vertexColors: true,
    });
    config.materials.push(mat);

    const m = new Mesh(g, mat);
    m.name = "model";
    m.castShadow = true;
    m.receiveShadow = true;
    const w = new LineSegments(
      new WireframeGeometry(g),
      new LineBasicMaterial({ color: 0x000000, linewidth: 2 })
    );
    w.name = "wireframe";
    w.visible = false;

    meshes.push(m, w);
  }
  return meshes;
};
