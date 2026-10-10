import {
  Scene,
  WebGLRenderer,
  Mesh,
  MeshPhongMaterial,
  Vector3,
  AmbientLight,
  PointLight,
  LineSegments,
  WireframeGeometry,
  LineBasicMaterial,
  DoubleSide,
  PerspectiveCamera,
  BufferAttribute,
  Color,
} from "three";
import { GUI } from "dat.gui";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader";
import { useEffect, useRef } from "react";

/**
 * createMenu creates a GUI menu controller.
 * @returns a GUI controller
 */
function createMenu(renderer, config, scene, control) {
  // Disable autoPlace so that we can place the GUI element on the top right
  // of every rendering panel.
  const gui = new GUI({ autoPlace: false });
  const assists = gui.addFolder("Visual Assists");
  config.wireframeControllers.push(
    assists
      .add(
        {
          wireframe: false,
        },
        "wireframe"
      )
      .name("wireframe")
      .listen()
      .onChange((show) => {
        // Synchornize with all other controllers.
        for (let i = 0; i < config.wireframeControllers.length; i++) {
          const c = config.wireframeControllers[i];
          if (c && c.getValue() !== show) {
            c.setValue(show);
          }
        }

        const o = scene.getObjectByName("wireframe");
        if (!o) {
          return;
        }
        o.visible = show;
      })
  );

  config.flatShadingControllers.push(
    assists
      .add({ flatShading: false }, "flatShading")
      .name("flat shading")
      .listen()
      .onChange((show) => {
        // Synchornize with all other controllers.
        for (let i = 0; i < config.flatShadingControllers.length; i++) {
          const c = config.flatShadingControllers[i];
          if (c && c.getValue() !== show) {
            c.setValue(show);
          }
        }

        const o = scene.getObjectByName("model");
        if (!o) {
          return;
        }
        o.material.flatShading = show;
        o.material.needsUpdate = true;
      })
  );
  assists.open();

  gui.domElement.style.position = "absolute";
  gui.domElement.style.top = "0";
  gui.domElement.style.right = "0";
  return gui;
};


/**
 * initRenderer creates a webgl renderer.
 * @returns a WebGL renderer
 */
function initRenderer() {
  const r = new WebGLRenderer({
    antialias: true,
    preserveDrawingBuffer: true,
    precision: "highp",
    alpha: true,
  });
  r.setPixelRatio(window.devicePixelRatio);
  return r;
};

function initCamera(w, h) {
  const camera = new PerspectiveCamera(40, w / h, 0.01, 1000);
  camera.position.copy(new Vector3(0, 1, 2));
  camera.lookAt(new Vector3(0, 0, 0));
  return camera;
};

/**
 * loadOBJ loads the object file from the given path, then adds all
 * parsed geometries into the scene graph.
 *
 * @param path is a URI that locates the obj file. If it is not an obj
 * file, nothing happens.
 * @param config is the rendering configuration that determines the
 * initial rendering effects.
 */
async function loadOBJ(path, config) {
  const g = await new Promise((resolve) => new OBJLoader().load(path, resolve));
  const meshes = [];

  for (const obj of g.children) {
    // We are certain that a child is a Mesh object unless three.js breaks
    // its compatibility.
    obj.geometry.computeBoundingBox();
    // bondingBox is always avaliable if we just computed.
    const aabb = obj.geometry.boundingBox;

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


export async function RenderEnvironment(label, dimension, container, mesh, config, showMenu, onLoad) {
  const camera = initCamera(dimension.width, dimension.height);
  config.cameras.push(camera);

  // Create renderer and scene graph.
  const renderer = initRenderer();
  renderer.setSize(dimension.width, dimension.height);
  config.renderers.push(renderer);
  const scene = new Scene();
  container.append(renderer.domElement);

  // Create basic light conditions: ambient and point light.
  // The ambient light provides basic lighting over the whole surface
  // whereas the position of the point light always follows the camera
  // so that it can always create the same light condition to the current
  // rendering canvas.
  scene.add(new AmbientLight(0xffffff, 0.35));
  const p = new PointLight(0xffffff, 0.8);
  p.position.copy(camera.position);
  p.castShadow = true;
  config.lights.push(p);
  scene.add(p);

  const control = new OrbitControls(camera, renderer.domElement);
  config.cameraControls.push(control);

  // Sync orbit controls between canvas.
  // See https://discourse.threejs.org/t/orbitcontrols-on-a-shared-camera-cannot-handle-panning/38547
  control.addEventListener("change", () => {
    for (const l of config.lights) {
      l.position.copy(camera.position);
    }
    for (const c of config.cameras) {
      c.position.copy(camera.position);
      c.rotation.copy(camera.rotation);
    }
    for (const c of config.cameraControls) {
      c.target.copy(control.target);
    }
  });

  // Create menu for control parameters
  const gui = createMenu(renderer, config, scene, control);
  if (showMenu) {
    container.append(gui.domElement);
  }
  const l = document.createElement("span");
  l.textContent = label;
  l.style.position = "absolute";
  l.style.top = "0px";
  l.style.left = "0px";
  l.style.margin = "5px 10px";
  l.style.fontWeight = "bold";
  l.style.fontSize = "large";
  container.append(l);

  // Load the target mesh from provided path.
  const objects = await loadOBJ(mesh, config);
  onLoad();
  scene.add(...objects);

  // Render loop
  // FIXME: do we need terminate this loop if react recreates the component?
  const loop = () => {
    renderer.setSize(dimension.width, dimension.height);
    renderer.render(scene, camera);
    window.requestAnimationFrame(() => loop());
  };
  console.log('run rendering loop')
  loop();
};

export function RenderComponent({ label, dimension, mesh, config, showMenu, onLoad, reset }) {
  const ref = useRef(null);
  useEffect(() => {
    const container = ref.current;
    if (container.children.length > 0 && !reset) {
      return container
    }
    RenderEnvironment(label, dimension, container, mesh, config, showMenu, onLoad);
    if (reset) {
      return () => {
        container.replaceChildren();
      }
    }
    return container;
  }, [label, dimension, mesh, config, showMenu, onLoad, reset]);

  return <div className="RenderContainer" ref={ref} />;
};