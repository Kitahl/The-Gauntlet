(() => {
  "use strict";

  const canvas = document.getElementById("system-field-canvas");
  if (!canvas) return;

  const ctx = canvas.getContext("2d", { alpha: true });
  if (!ctx) return;

  const caption = document.getElementById("system-caption");
  const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  let reducedMotion = motionQuery.matches;
  let width = 0;
  let height = 0;
  let dpr = 1;
  let frame = 0;
  let time = 0;
  let activeScene = document.body.dataset.scene || "hero";

  const palette = {
    paper: "#F2EBDD",
    ink: "#171714",
    slate: "#3D4546",
    bronze: "#77634C",
    oxide: "#8B3F2F",
    verdigris: "#476B63",
    white: "#FCFAF4"
  };

  const sceneCaption = {
    hero: ["PLATE / ACTIVE SYSTEM", "FRAME → ROUTE → OBSERVE → VERIFY → RELEASE"],
    overview: ["METHOD / CONTROL MODEL", "SIX STAGES · ONE EVIDENCE STATE"],
    workflow: ["ROUTE / OBLIGATION", "THE METHOD CHANGES WITH THE CLAIM"],
    gems: ["INDEX / INSTRUMENTS", "RUNTIME + TEN CORE CONTRACTS"],
    mind: ["INSTRUMENT 01 / CANON", "FORMALIZE → NEGATE → VERIFY"],
    space: ["INSTRUMENT 02 / ATLAS", "SEARCH → IDENTIFY → BOUND"],
    reality: ["INSTRUMENT 03 / CRUCIBLE", "GAP → MECHANISM → FALSIFIER"],
    power: ["INSTRUMENT 04 / FORGE", "SOURCE → ENTRYPOINT → EXECUTION"],
    time: ["INSTRUMENT 05 / CHRONOMETER", "BASELINE → MEASURE → DECIDE"],
    system: ["AUTHORITY / RELEASE PATH", "OBSERVATION ≠ RECEIPT ≠ RELEASE"],
    quiet: ["ARCHIVE / SOURCE", "INSPECT THE MACHINERY, NOT THE MOOD"]
  };

  const gemGeometry = {
    mind: [[-0.7, 0.55], [0, -0.75], [0.75, 0.48]],
    space: [[0, -0.86], [-0.38, -0.22], [0.4, -0.1], [-0.55, 0.48], [0.52, 0.58]],
    reality: [[-0.72, -0.28], [-0.2, 0.08], [0.28, -0.06], [0.73, 0.34]],
    power: [[-0.7, 0], [-0.24, 0], [0.24, 0], [0.7, 0]],
    time: [[0, -0.78], [0.62, -0.2], [0.38, 0.64], [-0.38, 0.64], [-0.62, -0.2]]
  };

  function resize() {
    width = Math.max(1, window.innerWidth);
    height = Math.max(1, window.innerHeight);
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw();
  }

  function rgba(hex, alpha) {
    const value = hex.replace("#", "");
    const n = Number.parseInt(value, 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
  }

  function setStroke(color = palette.bronze, alpha = 0.42, lineWidth = 1) {
    ctx.strokeStyle = rgba(color, alpha);
    ctx.lineWidth = lineWidth;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
  }

  function line(x1, y1, x2, y2, color = palette.bronze, alpha = 0.42, lineWidth = 1) {
    setStroke(color, alpha, lineWidth);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  function circle(x, y, radius, color = palette.bronze, alpha = 0.42, lineWidth = 1, fill = null) {
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    if (fill) {
      ctx.fillStyle = fill;
      ctx.fill();
    }
    setStroke(color, alpha, lineWidth);
    ctx.stroke();
  }

  function ellipse(x, y, rx, ry, rotation = 0, color = palette.bronze, alpha = 0.42, lineWidth = 1) {
    setStroke(color, alpha, lineWidth);
    ctx.beginPath();
    ctx.ellipse(x, y, rx, ry, rotation, 0, Math.PI * 2);
    ctx.stroke();
  }

  function label(value, x, y, align = "left", color = palette.slate, alpha = 0.52, size = 10) {
    ctx.save();
    ctx.font = `600 ${size}px ui-monospace, SFMono-Regular, Menlo, monospace`;
    ctx.textAlign = align;
    ctx.textBaseline = "middle";
    ctx.fillStyle = rgba(color, alpha);
    ctx.fillText(value, x, y);
    ctx.restore();
  }

  function dot(x, y, radius = 3, color = palette.oxide, alpha = 0.62) {
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fillStyle = rgba(color, alpha);
    ctx.fill();
  }

  function ticks(x, y, radius, count = 36, length = 6, color = palette.bronze, alpha = 0.33) {
    for (let i = 0; i < count; i += 1) {
      const angle = (i / count) * Math.PI * 2;
      const major = i % 6 === 0;
      const inner = radius - (major ? length * 1.65 : length);
      line(
        x + Math.cos(angle) * inner,
        y + Math.sin(angle) * inner,
        x + Math.cos(angle) * radius,
        y + Math.sin(angle) * radius,
        major ? palette.oxide : color,
        major ? alpha + 0.14 : alpha,
        major ? 1.2 : 0.7
      );
    }
  }

  function crosshair(x, y, radius) {
    line(x - radius, y, x + radius, y, palette.oxide, 0.4, 0.8);
    line(x, y - radius, x, y + radius, palette.oxide, 0.4, 0.8);
    circle(x, y, 4, palette.oxide, 0.62, 1.1);
  }

  function paperGrid(step = 42, alpha = 0.065) {
    for (let x = step / 2; x < width; x += step) line(x, 0, x, height, palette.bronze, alpha, 0.6);
    for (let y = step / 2; y < height; y += step) line(0, y, width, y, palette.bronze, alpha, 0.6);
  }

  function rightCenter(scale = 1) {
    const compact = width < 850;
    return {
      x: compact ? width * 0.73 : width * 0.79,
      y: height * 0.49,
      r: Math.min(width, height) * (compact ? 0.24 : 0.28) * scale
    };
  }

  function armillary(x, y, radius, phase = 0) {
    circle(x, y, radius, palette.ink, 0.34, 1.15);
    circle(x, y, radius * 0.72, palette.bronze, 0.32, 0.8);
    ellipse(x, y, radius, radius * 0.38, -0.22 + phase, palette.ink, 0.31, 0.9);
    ellipse(x, y, radius, radius * 0.38, 0.54 - phase * 0.7, palette.bronze, 0.34, 0.9);
    ellipse(x, y, radius * 0.39, radius, 0.16 + phase * 0.4, palette.ink, 0.29, 0.9);
    ellipse(x, y, radius * 0.62, radius, 1.06 - phase * 0.3, palette.bronze, 0.27, 0.8);
    ticks(x, y, radius + 9, 48, 7);
    crosshair(x, y, 11);
    line(x, y + radius, x, y + radius + 36, palette.ink, 0.36, 1.2);
    line(x - radius * 0.24, y + radius + 36, x + radius * 0.24, y + radius + 36, palette.ink, 0.36, 1.2);
  }

  function profile(x, y, scale) {
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(scale, scale);
    setStroke(palette.ink, 0.31, 1.2 / scale);
    ctx.beginPath();
    ctx.moveTo(-30, 78);
    ctx.bezierCurveTo(-27, 44, -18, 23, 6, 10);
    ctx.bezierCurveTo(-7, -6, -12, -26, -8, -45);
    ctx.bezierCurveTo(-3, -70, 17, -86, 42, -82);
    ctx.bezierCurveTo(57, -80, 69, -72, 76, -61);
    ctx.bezierCurveTo(67, -56, 63, -48, 66, -40);
    ctx.bezierCurveTo(78, -37, 85, -29, 87, -19);
    ctx.bezierCurveTo(84, -12, 79, -8, 71, -6);
    ctx.bezierCurveTo(75, 1, 74, 8, 69, 13);
    ctx.bezierCurveTo(64, 19, 56, 21, 47, 22);
    ctx.bezierCurveTo(44, 38, 35, 51, 20, 60);
    ctx.bezierCurveTo(37, 67, 51, 82, 57, 101);
    ctx.stroke();
    line(-18, -47, 57, -47, palette.oxide, 0.24, 0.7 / scale);
    line(-18, -7, 73, -7, palette.oxide, 0.24, 0.7 / scale);
    line(20, -78, 20, 90, palette.oxide, 0.22, 0.7 / scale);
    ctx.restore();
  }

  function leaf(ctxX, ctxY, angle, length, side) {
    const dx = Math.cos(angle);
    const dy = Math.sin(angle);
    const px = -dy;
    const py = dx;
    const widthLeaf = length * 0.33 * side;
    ctx.beginPath();
    ctx.moveTo(ctxX, ctxY);
    ctx.bezierCurveTo(
      ctxX + dx * length * 0.35 + px * widthLeaf,
      ctxY + dy * length * 0.35 + py * widthLeaf,
      ctxX + dx * length * 0.77 + px * widthLeaf * 0.5,
      ctxY + dy * length * 0.77 + py * widthLeaf * 0.5,
      ctxX + dx * length,
      ctxY + dy * length
    );
    ctx.bezierCurveTo(
      ctxX + dx * length * 0.75 - px * widthLeaf * 0.42,
      ctxY + dy * length * 0.75 - py * widthLeaf * 0.42,
      ctxX + dx * length * 0.3 - px * widthLeaf * 0.55,
      ctxY + dy * length * 0.3 - py * widthLeaf * 0.55,
      ctxX,
      ctxY
    );
    setStroke(palette.verdigris, 0.33, 0.9);
    ctx.stroke();
    line(ctxX, ctxY, ctxX + dx * length, ctxY + dy * length, palette.verdigris, 0.25, 0.65);
  }

  function botanical(x, y, heightStem) {
    const sway = reducedMotion ? 0 : Math.sin(time * 0.00035) * 0.035;
    setStroke(palette.verdigris, 0.34, 1.2);
    ctx.beginPath();
    ctx.moveTo(x, y + heightStem * 0.48);
    ctx.bezierCurveTo(x + 18, y + heightStem * 0.12, x - 12, y - heightStem * 0.16, x + 24, y - heightStem * 0.5);
    ctx.stroke();
    const points = [0.31, 0.15, -0.02, -0.19, -0.34];
    points.forEach((offset, index) => {
      const py = y + heightStem * offset;
      const px = x + (0.28 - offset) * 22;
      const direction = index % 2 === 0 ? Math.PI + 0.25 + sway : -0.25 + sway;
      leaf(px, py, direction, heightStem * (0.19 - index * 0.008), index % 2 === 0 ? 1 : -1);
    });
    dot(x + 24, y - heightStem * 0.5, 2.4, palette.verdigris, 0.46);
  }

  function polygon(points, color = palette.ink, alpha = 0.34, lineWidth = 1, close = true) {
    if (!points.length) return;
    setStroke(color, alpha, lineWidth);
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    for (let i = 1; i < points.length; i += 1) ctx.lineTo(points[i][0], points[i][1]);
    if (close) ctx.closePath();
    ctx.stroke();
  }

  function gear(x, y, radius, teeth, rotation = 0) {
    const points = [];
    const total = teeth * 4;
    for (let i = 0; i < total; i += 1) {
      const angle = rotation + (i / total) * Math.PI * 2;
      const phase = i % 4;
      const rr = phase === 1 || phase === 2 ? radius * 1.13 : radius;
      points.push([x + Math.cos(angle) * rr, y + Math.sin(angle) * rr]);
    }
    polygon(points, palette.ink, 0.34, 0.9, true);
    circle(x, y, radius * 0.42, palette.bronze, 0.34, 0.8);
    circle(x, y, radius * 0.12, palette.oxide, 0.48, 0.9);
  }

  function drawHero() {
    paperGrid(48, 0.05);
    const { x, y, r } = rightCenter(0.98);
    const drift = reducedMotion ? 0 : Math.sin(time * 0.00015) * 0.03;
    armillary(x, y, r, drift);
    profile(x - r * 0.05, y + r * 0.08, r / 145);
    botanical(x - r * 1.22, y + r * 0.1, r * 1.32);
    label("SPECIMEN / CLAIM", x - r * 1.48, y - r * 0.8, "left", palette.verdigris, 0.43, 9);
    label("CALIBRATION / AUTHORITY", x + r * 0.25, y + r * 0.78, "left", palette.oxide, 0.44, 9);
  }

  function drawOverview() {
    paperGrid(54, 0.045);
    const { x, y, r } = rightCenter(0.94);
    const cols = 3;
    const rows = 2;
    const gapX = r * 0.78;
    const gapY = r * 0.66;
    const startX = x - gapX;
    const startY = y - gapY * 0.5;
    let index = 0;
    for (let row = 0; row < rows; row += 1) {
      for (let col = 0; col < cols; col += 1) {
        const px = startX + col * gapX;
        const py = startY + row * gapY;
        circle(px, py, r * 0.2, index === 4 ? palette.oxide : palette.bronze, 0.35, 1);
        crosshair(px, py, r * 0.045);
        label(String(index + 1).padStart(2, "0"), px, py + r * 0.29, "center", palette.slate, 0.46, 9);
        if (index > 0) {
          const prevCol = (index - 1) % cols;
          const prevRow = Math.floor((index - 1) / cols);
          line(startX + prevCol * gapX, startY + prevRow * gapY, px, py, palette.bronze, 0.19, 0.7);
        }
        index += 1;
      }
    }
    label("FRAME / ROUTE / OBSERVE / VERIFY / CHALLENGE / RELEASE", x, y + r * 0.82, "center", palette.oxide, 0.4, 9);
  }

  function drawWorkflow() {
    paperGrid(50, 0.04);
    const { x, y, r } = rightCenter(1.03);
    const paths = [
      [-0.84, -0.58, 0.76, -0.58],
      [-0.74, -0.29, 0.48, -0.29],
      [-0.67, 0, 0.86, 0],
      [-0.77, 0.29, 0.59, 0.29],
      [-0.83, 0.58, 0.72, 0.58]
    ];
    paths.forEach((p, index) => {
      const yLine = y + p[1] * r;
      const x1 = x + p[0] * r;
      const x2 = x + p[2] * r;
      line(x1, yLine, x2, yLine, index === 2 ? palette.oxide : palette.bronze, 0.36, index === 2 ? 1.4 : 0.9);
      for (let j = 0; j < 4; j += 1) {
        const px = x1 + ((j + 0.5) / 4) * (x2 - x1);
        dot(px, yLine, j === 3 ? 3.2 : 2.1, j === 3 ? palette.oxide : palette.bronze, 0.5);
      }
      label(`ROUTE ${String(index + 1).padStart(2, "0")}`, x1, yLine - 15, "left", palette.slate, 0.42, 8);
    });
    line(x - r * 0.06, y - r * 0.75, x - r * 0.06, y + r * 0.76, palette.oxide, 0.24, 0.8);
  }

  function drawGems() {
    paperGrid(56, 0.045);
    const { x, y, r } = rightCenter(0.96);
    const names = ["CANON", "ATLAS", "CRUCIBLE", "FORGE", "CHRONOMETER"];
    names.forEach((name, index) => {
      const angle = -Math.PI / 2 + index * (Math.PI * 2 / 5);
      const px = x + Math.cos(angle) * r * 0.7;
      const py = y + Math.sin(angle) * r * 0.7;
      circle(px, py, r * 0.19, index === 2 ? palette.oxide : palette.bronze, 0.36, 1);
      line(x, y, px, py, palette.bronze, 0.19, 0.75);
      dot(px, py, 3, index === 2 ? palette.oxide : palette.verdigris, 0.55);
      label(name, px, py + r * 0.27, "center", palette.slate, 0.42, 8);
    });
    circle(x, y, r * 0.23, palette.ink, 0.28, 1);
    crosshair(x, y, 12);
    label("AXIS", x, y + 29, "center", palette.oxide, 0.45, 9);
  }

  function drawMind() {
    paperGrid(44, 0.045);
    const { x, y, r } = rightCenter(1.0);
    const points = gemGeometry.mind.map(([gx, gy]) => [x + gx * r, y + gy * r]);
    polygon(points, palette.ink, 0.39, 1.2, true);
    const [a, b, c] = points;
    circle(a[0], a[1], Math.hypot(b[0] - a[0], b[1] - a[1]), palette.bronze, 0.25, 0.8);
    circle(c[0], c[1], Math.hypot(b[0] - c[0], b[1] - c[1]), palette.bronze, 0.25, 0.8);
    line(b[0], b[1], x, y, palette.oxide, 0.34, 1);
    line(x, y, a[0], a[1], palette.bronze, 0.27, 0.8);
    line(x, y, c[0], c[1], palette.bronze, 0.27, 0.8);
    [a, b, c, [x, y]].forEach((p, index) => {
      dot(p[0], p[1], 3, index === 3 ? palette.oxide : palette.ink, 0.55);
      label(["A", "B", "C", "Q.E.D."][index], p[0] + 10, p[1] - 12, "left", index === 3 ? palette.oxide : palette.slate, 0.5, 9);
    });
    ticks(x, y, r * 0.31, 24, 5, palette.bronze, 0.23);
  }

  function drawSpace() {
    paperGrid(52, 0.04);
    const { x, y, r } = rightCenter(0.98);
    botanical(x, y + r * 0.02, r * 1.65);
    const points = gemGeometry.space.map(([gx, gy]) => [x + gx * r, y + gy * r]);
    points.forEach((point, index) => {
      circle(point[0], point[1], r * 0.08, palette.verdigris, 0.3, 0.8);
      dot(point[0], point[1], 2.3, palette.verdigris, 0.46);
      label(`TAXON ${String(index + 1).padStart(2, "0")}`, point[0] + (point[0] < x ? -12 : 12), point[1] - 12, point[0] < x ? "right" : "left", palette.slate, 0.42, 8);
    });
    line(x - r * 0.95, y + r * 0.78, x + r * 0.98, y + r * 0.78, palette.bronze, 0.29, 0.8);
    for (let i = 0; i <= 20; i += 1) {
      const tx = x - r * 0.95 + (i / 20) * r * 1.93;
      line(tx, y + r * 0.78, tx, y + r * (i % 5 === 0 ? 0.72 : 0.75), palette.oxide, 0.28, 0.7);
    }
  }

  function drawReality() {
    paperGrid(48, 0.04);
    const { x, y, r } = rightCenter(0.98);
    const points = gemGeometry.reality.map(([gx, gy]) => [x + gx * r, y + gy * r]);
    points.forEach((point, index) => {
      const radius = r * (0.17 + index * 0.025);
      const sides = 3 + index;
      const shape = [];
      for (let j = 0; j < sides; j += 1) {
        const angle = -Math.PI / 2 + (j / sides) * Math.PI * 2;
        shape.push([point[0] + Math.cos(angle) * radius, point[1] + Math.sin(angle) * radius]);
      }
      polygon(shape, index === 2 ? palette.oxide : palette.ink, 0.34, index === 2 ? 1.3 : 0.9, true);
      dot(point[0], point[1], 2.7, index === 2 ? palette.oxide : palette.bronze, 0.52);
      if (index < points.length - 1) {
        line(point[0] + radius, point[1], points[index + 1][0] - r * (0.17 + (index + 1) * 0.025), points[index + 1][1], palette.oxide, 0.29, 1);
      }
      label(["KNOWN", "GAP", "CANDIDATE", "FALSIFIER"][index], point[0], point[1] + radius + 18, "center", index === 1 ? palette.oxide : palette.slate, 0.46, 8);
    });
  }

  function drawPower() {
    paperGrid(46, 0.045);
    const { x, y, r } = rightCenter(0.98);
    const points = gemGeometry.power.map(([gx, gy]) => [x + gx * r, y + gy * r]);
    const rotation = reducedMotion ? 0 : time * 0.00005;
    points.forEach((point, index) => {
      gear(point[0], point[1], r * (0.16 + index * 0.012), 8 + index, rotation * (index % 2 ? -1 : 1));
      label(["SOURCE", "BUILD", "ENTRY", "VERIFY"][index], point[0], y + r * 0.44, "center", palette.slate, 0.45, 8);
      if (index < points.length - 1) line(point[0] + r * 0.18, point[1], points[index + 1][0] - r * 0.18, points[index + 1][1], palette.oxide, 0.26, 0.8);
    });
    line(x - r * 0.95, y - r * 0.48, x + r * 0.95, y - r * 0.48, palette.bronze, 0.25, 0.8);
    label("EXPLODED VERIFICATION PLATE", x, y - r * 0.55, "center", palette.oxide, 0.42, 8);
  }

  function drawTime() {
    paperGrid(54, 0.04);
    const { x, y, r } = rightCenter(0.98);
    circle(x, y, r * 0.83, palette.ink, 0.37, 1.2);
    circle(x, y, r * 0.68, palette.bronze, 0.31, 0.8);
    ticks(x, y, r * 0.83, 60, 8, palette.bronze, 0.34);
    ticks(x, y, r * 0.68, 24, 5, palette.bronze, 0.22);
    const points = gemGeometry.time.map(([gx, gy]) => [x + gx * r * 0.55, y + gy * r * 0.55]);
    polygon(points, palette.verdigris, 0.32, 0.9, true);
    points.forEach((point, index) => {
      dot(point[0], point[1], 3, index === 0 ? palette.oxide : palette.verdigris, 0.56);
      label(String(index + 1), point[0], point[1] - 13, "center", palette.slate, 0.44, 8);
    });
    const handAngle = -Math.PI / 2 + (reducedMotion ? 0.68 : (time * 0.00008) % (Math.PI * 2));
    line(x, y, x + Math.cos(handAngle) * r * 0.58, y + Math.sin(handAngle) * r * 0.58, palette.oxide, 0.47, 1.4);
    circle(x, y, 7, palette.oxide, 0.52, 1.1, rgba(palette.paper, 0.7));
    label("BASELINE", x - r * 0.62, y + r * 0.92, "left", palette.slate, 0.42, 8);
    label("DECISION", x + r * 0.62, y + r * 0.92, "right", palette.oxide, 0.44, 8);
  }

  function drawSystem() {
    paperGrid(48, 0.045);
    const { x, y, r } = rightCenter(1.02);
    const layers = [
      { radius: r * 0.2, label: "AXIS", color: palette.oxide },
      { radius: r * 0.43, label: "RECEIPTS", color: palette.verdigris },
      { radius: r * 0.68, label: "INSTRUMENTS", color: palette.bronze },
      { radius: r * 0.91, label: "RUNTIME", color: palette.ink }
    ];
    layers.forEach((layer, index) => {
      circle(x, y, layer.radius, layer.color, 0.3 + index * 0.02, index === 0 ? 1.3 : 0.8);
      label(layer.label, x, y - layer.radius - 12, "center", layer.color, 0.45, 8);
    });
    for (let i = 0; i < 10; i += 1) {
      const angle = -Math.PI / 2 + i * Math.PI * 2 / 10;
      const px = x + Math.cos(angle) * r * 0.68;
      const py = y + Math.sin(angle) * r * 0.68;
      line(x, y, px, py, palette.bronze, 0.18, 0.7);
      dot(px, py, 2.7, i % 3 === 0 ? palette.oxide : palette.bronze, 0.5);
    }
    crosshair(x, y, 13);
    label("OBSERVATION ≠ RECEIPT ≠ RELEASE", x, y + r * 1.02, "center", palette.oxide, 0.45, 9);
  }

  function drawQuiet() {
    paperGrid(58, 0.035);
    const { x, y, r } = rightCenter(0.9);
    circle(x, y, r * 0.7, palette.bronze, 0.16, 0.8);
    ticks(x, y, r * 0.7, 32, 5, palette.bronze, 0.16);
    line(x - r, y, x + r, y, palette.bronze, 0.13, 0.7);
    line(x, y - r, x, y + r, palette.bronze, 0.13, 0.7);
    label("ARCHIVE / SOURCE / PROVENANCE", x, y + r * 0.88, "center", palette.slate, 0.28, 8);
  }

  const drawers = {
    hero: drawHero,
    overview: drawOverview,
    workflow: drawWorkflow,
    gems: drawGems,
    mind: drawMind,
    space: drawSpace,
    reality: drawReality,
    power: drawPower,
    time: drawTime,
    system: drawSystem,
    quiet: drawQuiet
  };

  function clear() {
    ctx.clearRect(0, 0, width, height);
  }

  function draw() {
    clear();
    ctx.save();
    const drawer = drawers[activeScene] || drawQuiet;
    drawer();
    ctx.restore();
  }

  function animate(timestamp) {
    time = timestamp;
    draw();
    if (!reducedMotion) frame = window.requestAnimationFrame(animate);
  }

  function setScene(scene) {
    if (!drawers[scene] || scene === activeScene) return;
    activeScene = scene;
    document.body.dataset.scene = scene;
    const copy = sceneCaption[scene] || sceneCaption.quiet;
    if (caption) caption.innerHTML = `<strong>${copy[0]}</strong><span>${copy[1]}</span>`;
    if (reducedMotion) draw();
  }

  const sections = Array.from(document.querySelectorAll(".scene-section[data-scene]"));
  const observer = new IntersectionObserver((entries) => {
    const candidates = entries
      .filter((entry) => entry.isIntersecting)
      .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
    if (candidates.length) setScene(candidates[0].target.dataset.scene || "quiet");
  }, {
    root: null,
    rootMargin: "-34% 0px -42% 0px",
    threshold: [0, 0.08, 0.2, 0.45, 0.7]
  });

  sections.forEach((section) => observer.observe(section));

  function handleMotion(event) {
    reducedMotion = event.matches;
    if (frame) window.cancelAnimationFrame(frame);
    frame = 0;
    if (reducedMotion) draw();
    else frame = window.requestAnimationFrame(animate);
  }

  if (typeof motionQuery.addEventListener === "function") motionQuery.addEventListener("change", handleMotion);
  else if (typeof motionQuery.addListener === "function") motionQuery.addListener(handleMotion);

  window.addEventListener("resize", resize, { passive: true });
  resize();
  if (reducedMotion) draw();
  else frame = window.requestAnimationFrame(animate);
})();
