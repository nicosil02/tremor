// Camión minero de concentrado y tren de carga, procedurales (sin texturas ni descargas).
// Convención: y arriba, el frente mira a +z, 1 = 1 m, apoyados en y = 0 y centrados en x.
// Cada pieza se funde con las de su mismo material: el vehículo queda en ~15 mallas (pocas llamadas de dibujo).
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";

function taller(THREE) {
  const lotes = new Map(), base = new Map(), cubo = new THREE.BoxGeometry(1, 1, 1);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), p = new THREE.Vector3(), s = new THREE.Vector3();
  const pon = (geo, mat, x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0, sx = 1, sy = 1, sz = 1) => {
    if (!base.has(geo)) {  // misma lista de atributos para poder fundir (Extrude no tiene índice, Box sí)
      const g = geo.index ? geo.toNonIndexed() : geo.clone();
      for (const k of Object.keys(g.attributes)) if (k !== "position" && k !== "normal") g.deleteAttribute(k);
      base.set(geo, g);
    }
    const g = base.get(geo).clone().applyMatrix4(m.compose(p.set(x, y, z), q.setFromEuler(e.set(rx, ry, rz)), s.set(sx, sy, sz)));
    if (!lotes.has(mat)) lotes.set(mat, []);
    lotes.get(mat).push(g);
  };
  const caja = (w, h, l, mat, x, y, z, rx = 0, ry = 0, rz = 0) => pon(cubo, mat, x, y, z, rx, ry, rz, w, h, l);
  const arma = () => {
    const grupo = new THREE.Group();
    for (const [mat, gs] of lotes) grupo.add(new THREE.Mesh(mergeGeometries(gs), mat));
    return grupo;
  };
  const std = (color, roughness = 0.6, metalness = 0.1, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness, metalness, ...extra });
  const luz = (color, i = 1) => new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: i, roughness: 0.3 });
  const vidrio = () => new THREE.MeshPhysicalMaterial({ color: 0x1c3140, roughness: 0.06, metalness: 0.35, clearcoat: 1, clearcoatRoughness: 0.05 });
  const pintura = color => new THREE.MeshPhysicalMaterial({ color, roughness: 0.38, metalness: 0.05, clearcoat: 0.7, clearcoatRoughness: 0.25 });
  const rb = (w, h, l, r = 0.12) => new RoundedBoxGeometry(w, h, l, 3, r);
  const eje = g => g.rotateZ(Math.PI / 2);  // cilindros con el eje en x
  return { pon, caja, arma, std, luz, vidrio, pintura, rb, eje, limpia: () => lotes.clear() };
}

// Perfil de techo en arco (lona), extruido a lo largo de z desde z = 0.
function arco(THREE, ancho, y0, alto, largo) {
  const sh = new THREE.Shape(), a = ancho / 2;
  sh.moveTo(-a, y0); sh.lineTo(a, y0); sh.quadraticCurveTo(0, y0 + 2 * alto, -a, y0);
  return new THREE.ExtrudeGeometry(sh, { depth: largo, bevelEnabled: false, curveSegments: 10 });
}

export function camion(THREE) {
  const { pon, caja, arma, std, luz, vidrio, pintura, rb, eje } = taller(THREE);
  const blanco = pintura(0xf1f0ea), rojo = pintura(0xa8231d), negro = std(0x1c1e21, 0.7), gris = std(0x3b3f45, 0.5, 0.3);
  const llantaM = std(0x141414, 0.92, 0, { side: THREE.DoubleSide }), aroM = std(0xc8ccd1, 0.28, 0.6), cromo = std(0xdfe3e8, 0.18, 0.8);
  const cristal = vidrio(), faro = luz(0xfff3d6, 1.2), stop = luz(0xd8141a, 1.4), ambar = luz(0xffa21a, 1.2);
  const tolvaM = std(0x8b9298, 0.42, 0.45), costilla = std(0x6c7379, 0.5, 0.45), lona = std(0x59603a, 0.95);
  const cincha = std(0xd1a62a, 0.7), refB = luz(0xf4f4f4, 0.35), refR = luz(0xc81e1e, 0.5);

  // Ruedas: llanta torneada con hombro redondeado, aro metálico y maza.
  const V = (a, b) => new THREE.Vector2(a, b);
  const llanta = eje(new THREE.LatheGeometry([V(0.3, -0.15), V(0.46, -0.15), V(0.52, -0.11), V(0.535, 0), V(0.52, 0.11), V(0.46, 0.15), V(0.3, 0.15)], 22));
  const aro = eje(new THREE.CylinderGeometry(0.31, 0.31, 0.31, 18)), maza = eje(new THREE.CylinderGeometry(0.11, 0.13, 0.36, 10));
  const barra = eje(new THREE.CylinderGeometry(0.07, 0.07, 1, 8));
  const rueda = (x, z) => { pon(llanta, llantaM, x, 0.535, z); pon(aro, aroM, x, 0.535, z); pon(maza, gris, x, 0.535, z); };
  const ejeSimple = z => { for (const sg of [-1, 1]) rueda(sg * 1.04, z); pon(barra, negro, 0, 0.535, z, 0, 0, 0, 2, 1, 1); };
  const ejeDoble = z => { for (const sg of [-1, 1]) { rueda(sg * 0.72, z); rueda(sg * 1.05, z); } pon(barra, negro, 0, 0.535, z, 0, 0, 0, 2.1, 1, 1); };

  // ---- Tracto (Volvo FH / Scania R de cabina dormitorio)
  for (const sg of [-1, 1]) caja(0.22, 0.3, 6.6, negro, sg * 0.42, 0.95, 4.85);   // largueros
  ejeSimple(6.9); ejeDoble(3.25); ejeDoble(1.9);
  pon(rb(2.45, 2.55, 2.35, 0.2), blanco, 0, 2.575, 6.85);                         // cabina
  pon(rb(2.38, 0.6, 1.9, 0.22), blanco, 0, 4.05, 6.6);                             // techo alto
  pon(rb(2.3, 0.08, 0.28, 0.03), blanco, 0, 3.76, 8.05, 0.12);                       // visera
  caja(2.15, 0.95, 0.06, cristal, 0, 3.15, 8.03, -0.1);                             // parabrisas
  caja(2.5, 0.12, 2.0, rojo, 0, 1.75, 6.75);                                       // franja roja baja
  caja(1.3, 0.85, 0.06, negro, 0, 2.1, 8.04);                                       // parrilla
  for (let i = 0; i < 4; i++) caja(1.22, 0.06, 0.05, cromo, 0, 1.78 + i * 0.21, 8.08);
  pon(rb(2.5, 0.5, 0.4, 0.08), gris, 0, 1.05, 8.1);                                 // parachoques
  for (const sg of [-1, 1]) {
    caja(0.06, 0.75, 0.95, cristal, sg * 1.235, 3.18, 7.35);                        // ventana lateral
    caja(0.04, 0.85, 1.05, negro, sg * 1.228, 3.18, 7.35);                          // marco
    caja(0.42, 0.2, 0.05, faro, sg * 0.92, 1.55, 8.04);                             // faros
    caja(0.2, 0.12, 0.05, faro, sg * 0.95, 1.05, 8.31);                             // neblineros
    caja(0.12, 0.08, 0.05, ambar, sg * 0.6, 4.33, 7.55);                            // gálibo
    caja(0.32, 0.04, 0.04, negro, sg * 1.38, 3.25, 7.82);                           // brazo del espejo
    pon(rb(0.12, 0.5, 0.24, 0.04), negro, sg * 1.55, 3.05, 7.8);                    // espejo
    caja(0.12, 0.6, 1.0, negro, sg * 1.17, 1.1, 6.0);                               // peldaños / faldón
    caja(0.75, 0.06, 2.6, negro, sg * 0.9, 1.2, 2.58);                              // guardafango trasero
    caja(0.7, 0.55, 0.03, negro, sg * 0.9, 0.55, 1.2);                              // faldón
    caja(0.45, 0.08, 0.7, negro, sg * 1.0, 1.32, 6.9, 0, 0, sg * -0.3);             // guardafango delantero
  }
  pon(new THREE.CylinderGeometry(0.32, 0.32, 1.3, 16), aroM, -0.98, 0.78, 4.75, Math.PI / 2);     // tanque
  caja(0.5, 0.5, 0.8, negro, 0.98, 0.8, 4.8);                                       // baterías
  pon(new THREE.CylinderGeometry(0.09, 0.09, 3.0, 10), cromo, 1.0, 2.9, 5.55);      // escape vertical
  pon(new THREE.CylinderGeometry(0.55, 0.55, 0.12, 18), negro, 0, 1.17, 2.6);       // quinta rueda

  // ---- Semirremolque tolva encapsulado con lona (z de -8.6 a 4)
  for (const sg of [-1, 1]) caja(0.25, 0.45, 12.4, negro, sg * 0.5, 1.28, -2.3);
  const perfil = new THREE.Shape();
  [[-1.25, 3.55], [1.25, 3.55], [1.25, 2.3], [0.55, 1.5], [-0.55, 1.5], [-1.25, 2.3]].forEach(([x, y], i) => i ? perfil.lineTo(x, y) : perfil.moveTo(x, y));
  const tolva = new THREE.ExtrudeGeometry(perfil, { depth: 12.2, bevelEnabled: true, bevelSize: 0.04, bevelThickness: 0.04, bevelSegments: 1 });
  pon(tolva, tolvaM, 0, 0, -8.4);
  pon(arco(THREE, 2.66, 3.5, 0.38, 12.3), lona, 0, 0, -8.45);                       // lona en arco
  const tira = arco(THREE, 2.72, 3.49, 0.4, 0.09);
  for (let i = 0; i < 11; i++) {                                                    // cinchas sobre la lona
    const z = -8.0 + i * 1.15;
    pon(tira, cincha, 0, 0, z);
    for (const sg of [-1, 1]) caja(0.03, 0.55, 0.09, cincha, sg * 1.34, 3.2, z + 0.045);
  }
  for (const sg of [-1, 1]) {
    caja(0.04, 0.3, 12.3, lona, sg * 1.31, 3.4, -2.3);                              // faldón de la lona
    caja(0.1, 0.12, 12.25, costilla, sg * 1.27, 3.53, -2.3);                        // borde superior
    for (let z = -8.0; z <= 3.6; z += 1.15) caja(0.07, 1.2, 0.1, costilla, sg * 1.29, 2.92, z + 0.6);
    for (let i = 0; i < 24; i++) caja(0.02, 0.1, 0.5, i % 2 ? refR : refB, sg * 1.3, 2.42, -8.2 + i * 0.5);
    caja(0.75, 0.06, 4.0, negro, sg * 0.9, 1.15, -6.5);                             // guardafangos
    caja(0.7, 0.55, 0.03, negro, sg * 0.9, 0.55, -8.45);
    caja(0.12, 0.95, 0.12, gris, sg * 0.7, 0.78, 1.8);                              // patas de apoyo
    caja(0.3, 0.05, 0.3, gris, sg * 0.7, 0.3, 1.8);
    caja(0.26, 0.16, 0.05, stop, sg * 1.0, 1.3, -8.63);                             // luces traseras
    caja(0.14, 0.16, 0.05, ambar, sg * 0.68, 1.3, -8.63);
  }
  for (const z of [-5.2, -6.5, -7.8]) ejeDoble(z);
  caja(2.4, 0.3, 0.1, negro, 0, 1.3, -8.56);                                        // porta luces
  caja(2.3, 0.18, 0.12, gris, 0, 0.82, -8.5);                                       // parachoques trasero
  for (let i = 0; i < 6; i++) caja(0.38, 0.1, 0.02, i % 2 ? refR : refB, -0.95 + i * 0.38, 0.84, -8.57);
  return arma();
}

export function tren(THREE) {
  const { pon, caja, arma, std, luz, vidrio, pintura, rb, eje, limpia } = taller(THREE);
  const amarillo = pintura(0xf0b417), azul = pintura(0x1d3c8c), negro = std(0x1a1b1e, 0.7), gris = std(0x33363b, 0.55, 0.35);
  const acero = std(0x5d6168, 0.35, 0.7), baranda = std(0xe9e9e4, 0.4), cristal = vidrio(), faro = luz(0xfff3d6, 1.4);
  const vagonM = std(0x8e959d, 0.45, 0.45), costilla = std(0x6a7178, 0.5, 0.45), lona = std(0x55603a, 0.95), cincha = std(0xd1a62a, 0.7);

  const rueda = eje(new THREE.CylinderGeometry(0.46, 0.46, 0.13, 16)), pestana = eje(new THREE.CylinderGeometry(0.51, 0.51, 0.03, 16));
  const barra = eje(new THREE.CylinderGeometry(0.07, 0.07, 1.56, 8)), resorte = new THREE.CylinderGeometry(0.1, 0.1, 0.3, 8);
  const ejeTren = z => { for (const sg of [-1, 1]) { pon(rueda, acero, sg * 0.72, 0.46, z); pon(pestana, acero, sg * 0.64, 0.46, z); } pon(barra, gris, 0, 0.46, z); };
  const bogie = (z, ejes, paso) => {
    const largo = paso * (ejes - 1) + 1.4;
    for (let i = 0; i < ejes; i++) ejeTren(z + (i - (ejes - 1) / 2) * paso);
    for (const sg of [-1, 1]) {
      caja(0.14, 0.42, largo, gris, sg * 0.95, 0.66, z);                            // bastidor lateral
      for (let i = 0; i < ejes - 1; i++) pon(resorte, acero, sg * 0.95, 0.98, z + (i + 0.5 - (ejes - 1) / 2) * paso);
    }
    caja(1.9, 0.24, 0.45, gris, 0, 0.92, z);                                        // travesaño
  };
  const acople = (z, d) => { caja(0.32, 0.28, 0.6, acero, 0, 1.0, z); caja(0.5, 0.36, 0.2, acero, 0, 1.0, z + d * 0.3); };

  // ---- Locomotora diésel de capó (z de -8.8 a 8.9, cabina adelante)
  caja(3.0, 0.32, 16.4, negro, 0, 1.44, 0);                                          // bastidor y pasillo
  for (const sg of [-1, 1]) caja(0.03, 0.14, 16.4, amarillo, sg * 1.51, 1.44, 0);
  bogie(5.3, 3, 1.35); bogie(-5.3, 3, 1.35);
  for (const z of [5.3, -5.3]) caja(1.3, 0.45, 3.4, negro, 0, 0.85, z);            // motores de tracción
  pon(rb(2.5, 0.85, 4.2, 0.15), gris, 0, 0.98, 0);                                   // tanque de combustible
  pon(rb(2.2, 2.35, 10.6, 0.14), amarillo, 0, 2.78, -2.7);                          // capó largo
  pon(rb(2.95, 2.65, 2.6, 0.14), amarillo, 0, 2.93, 3.9);                           // cabina
  pon(rb(3.02, 0.2, 2.72, 0.08), negro, 0, 4.3, 3.9);                               // techo
  pon(rb(2.2, 1.55, 2.3, 0.14), amarillo, 0, 2.38, 6.35);                           // nariz
  pon(rb(2.0, 0.28, 2.2, 0.1), amarillo, 0, 4.05, 0);                               // freno dinámico
  caja(0.3, 0.3, 0.7, negro, 0, 4.05, -2.2);                                        // escape
  pon(new THREE.CylinderGeometry(0.5, 0.5, 0.1, 18), negro, 0, 3.98, -6.0);         // ventiladores
  pon(new THREE.CylinderGeometry(0.5, 0.5, 0.1, 18), negro, 0, 3.98, -7.15);
  for (const sg of [-1, 1]) {
    caja(0.03, 0.42, 10.62, azul, sg * 1.105, 2.55, -2.7);                          // franja azul
    caja(0.03, 0.42, 2.62, azul, sg * 1.48, 2.55, 3.9);
    caja(0.03, 0.42, 2.32, azul, sg * 1.105, 2.55, 6.35);
    for (let z = -7.4; z < 2.2; z += 1.35) caja(0.02, 1.9, 0.04, negro, sg * 1.105, 2.95, z); // puertas del capó
    caja(0.03, 0.9, 2.2, negro, sg * 1.105, 3.35, -6.5);                            // radiador
    caja(0.05, 0.65, 1.0, cristal, sg * 1.48, 3.6, 4.1);                            // ventana lateral
    caja(0.95, 0.7, 0.05, cristal, sg * 0.62, 3.6, 5.22);                           // parabrisas
    caja(0.22, 0.22, 0.05, faro, sg * 0.35, 2.9, 7.51);                             // faros
    caja(0.2, 0.2, 0.05, faro, sg * 1.15, 1.85, 8.55);                              // luces de zanja
    caja(0.6, 0.6, 0.1, amarillo, sg * 1.2, 1.0, 8.5);                              // peldaños
    caja(0.6, 0.6, 0.1, amarillo, sg * 1.2, 1.0, -8.5);
    // barandas del pasillo
    caja(0.05, 0.05, 10.6, baranda, sg * 1.45, 2.55, -2.7);
    caja(0.05, 0.05, 2.4, baranda, sg * 1.45, 2.55, 6.6);
    for (let z = -8.0; z <= 2.4; z += 1.6) caja(0.05, 0.95, 0.05, baranda, sg * 1.45, 2.08, z);
    for (const z of [5.4, 7.9]) caja(0.05, 0.95, 0.05, baranda, sg * 1.45, 2.08, z);
  }
  for (const z of [8.2, -8.2]) { caja(3.0, 0.08, 0.05, baranda, 0, 2.55, z); }
  caja(1.9, 0.3, 0.04, negro, 0, 1.9, 7.52);                                        // franja negra de la nariz
  pon(rb(3.0, 0.6, 0.4, 0.08), negro, 0, 1.0, 8.4);                                // quitapiedras
  pon(rb(3.0, 0.6, 0.4, 0.08), negro, 0, 1.0, -8.4);
  acople(8.75, 1); acople(-8.75, -1);
  const loco = arma(); limpia();

  // ---- vagón tolva de concentrado con lona (uno, centrado en z = 0; se clona 3 veces)
  const tira = arco(THREE, 2.98, 3.98, 0.32, 0.09), techo = arco(THREE, 2.92, 3.98, 0.3, 8.6);
  const tolvita = new THREE.CylinderGeometry(1.45, 0.35, 0.9, 4, 1).rotateY(Math.PI / 4);
  {
    const c = 0;
    caja(0.5, 0.4, 9.0, negro, 0, 1.25, c);                                        // viga central
    bogie(c + 3.1, 2, 1.8); bogie(c - 3.1, 2, 1.8);
    pon(rb(2.9, 2.4, 8.6, 0.08), vagonM, 0, 2.78, c);                              // caja
    for (const dz of [-1.1, 1.1]) pon(tolvita, vagonM, 0, 1.15, c + dz);            // tolvas de descarga
    caja(3.0, 0.12, 8.7, costilla, 0, 3.98, c);                                    // borde superior
    pon(techo, lona, 0, 0, c - 4.3);
    for (let i = 0; i < 7; i++) pon(tira, cincha, 0, 0, c - 3.5 + i * 1.15);
    for (const sg of [-1, 1]) {
      for (let z = -3.9; z <= 4.0; z += 0.97) caja(0.07, 2.3, 0.12, costilla, sg * 1.47, 2.78, c + z);
      caja(0.02, 0.12, 8.5, amarillo, sg * 1.5, 1.75, c);                          // franja reflectiva
      caja(2.9, 0.5, 0.06, amarillo, 0, 1.75, c + sg * 4.32);                       // testero
    }
    acople(c + 4.7, 1); acople(c - 4.7, -1);
  }
  // cada pieza es un grupo aparte con su distancia detrás de la locomotora (userData.atras, en m): en las curvas
  // la app pone cada una sobre la vía, en vez de mover el tren entero como un palo rígido
  const vagon = arma(), g = new THREE.Group();
  loco.userData.atras = 0; g.add(loco);
  for (let k = 0; k < 3; k++) { const v = vagon.clone(); v.userData.atras = 13.8 + k * 10; g.add(v); }
  return g;
}
