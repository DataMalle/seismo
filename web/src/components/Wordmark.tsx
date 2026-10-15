/** Pixelblock-logotyp, byggd av en 5x5-bitmap per bokstav. Samma idé som pixelloggor i ljuskonstgallerier. */
const GLYPHS: Record<string, string[]> = {
  S: ["01111", "10000", "01110", "00001", "11110"],
  E: ["11111", "10000", "11110", "10000", "11111"],
  I: ["11111", "00100", "00100", "00100", "11111"],
  M: ["10001", "11011", "10101", "10001", "10001"],
  O: ["01110", "10001", "10001", "10001", "01110"],
};

const WORD = "SEISMO";
const PIXEL = 2;
const GAP = 3; // mellanrum mellan bokstäver, i pixlar

export function Wordmark() {
  const rects: { x: number; y: number; key: string }[] = [];
  [...WORD].forEach((ch, i) => {
    GLYPHS[ch].forEach((row, y) =>
      [...row].forEach((bit, x) => {
        if (bit === "1") rects.push({ x: (i * (5 + GAP) + x) * PIXEL, y: y * PIXEL, key: `${i}-${x}-${y}` });
      }),
    );
  });
  const width = (WORD.length * (5 + GAP) - GAP) * PIXEL;
  return (
    <svg viewBox={`0 0 ${width} ${5 * PIXEL}`} height="14" width={Math.round((width / (5 * PIXEL)) * 14)} role="img" aria-label="Seismo" className="wordmark-svg" shapeRendering="crispEdges">
      {rects.map((r) => (
        <rect key={r.key} x={r.x} y={r.y} width={PIXEL - 0.25} height={PIXEL - 0.25} fill="currentColor" />
      ))}
    </svg>
  );
}
