import {
  Map as MapLibreMap,
  NavigationControl,
  Popup,
  setWorkerUrl,
  type ExpressionSpecification,
  type GeoJSONSource,
} from "maplibre-gl";
// Workern byggs som en egen fil av Vite och pekas ut uttryckligen. MapLibres egen sökväg (import.meta.url) pekar fel när
// biblioteket ligger i en buntad fil, och då startar aldrig kartan ("Worker failed to load").
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";
import type { FeatureCollection } from "geojson";
import { useEffect, useRef } from "react";
import { formatDateTime, formatMagnitude } from "../lib/format";
import { DEPTH_BANDS, UNKNOWN_DEPTH_COLOR } from "../lib/insights";
import type { EventMapRow } from "../lib/types";

setWorkerUrl(workerUrl);

// CARTO Dark Matter: mörk, gratis bakgrundskarta utan token. Passar den svarta designen.
const STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const SOURCE = "events";
const LAYER = "events-circles";

/** Cirkelradie i pixlar efter magnitud, skalad med `scale`. Samma form som tidigare, bara multiplicerad. */
function radiusByMagnitude(scale: number): ExpressionSpecification {
  return [
    "interpolate",
    ["linear"],
    ["coalesce", ["get", "magnitude"], 0],
    0,
    2 * scale,
    2,
    3 * scale,
    4,
    7 * scale,
    6,
    18 * scale,
    8,
    40 * scale,
  ];
}

function toGeoJson(events: EventMapRow[]): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: events.map((e) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [e.longitude, e.latitude] },
      properties: {
        magnitude: e.magnitude,
        depth_km: e.depth_km,
        place: e.place,
        event_time: e.event_time,
      },
    })),
  };
}

/** Popup byggs med DOM-noder och textContent, aldrig HTML-strängar: platsnamnen kommer från en extern källa. */
function popupContent(props: Record<string, unknown>): HTMLElement {
  const root = document.createElement("div");
  root.className = "map-popup";
  const title = document.createElement("strong");
  title.textContent = `M ${formatMagnitude(props.magnitude as number | null)}`;
  const place = document.createElement("div");
  place.textContent = String(props.place ?? "Unknown place");
  const meta = document.createElement("div");
  meta.className = "muted";
  const depth = props.depth_km === null || props.depth_km === undefined ? "–" : `${props.depth_km} km`;
  meta.textContent = `${formatDateTime(String(props.event_time))} · depth ${depth}`;
  root.append(title, place, meta);
  return root;
}

export function MapView({ events }: { events: EventMapRow[] }) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const eventsRef = useRef(events);
  // Synkas i en effekt, inte under rendering. Laddningshändelsen läser alltid det senaste värdet härifrån.
  useEffect(() => {
    eventsRef.current = events;
  });

  useEffect(() => {
    if (!container.current) return;
    const map = new MapLibreMap({
      container: container.current,
      style: STYLE,
      center: [10, 20],
      // Hela världen ska rymmas på bredden: en mobilskärm startar utzoomad, en bred skärm på zoom 1,2.
      zoom: Math.min(Math.max(Math.log2(container.current.clientWidth / 512), -1), 1.2),
      minZoom: -1,
      attributionControl: { compact: true },
    });
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");

    map.on("load", () => {
      map.addSource(SOURCE, { type: "geojson", data: toGeoJson(eventsRef.current) });
      map.addLayer({
        id: LAYER,
        type: "circle",
        source: SOURCE,
        paint: {
          // Samma band och färger som legenden (DEPTH_BANDS). step: <0 (okänt) -> grått, därefter ett steg per band.
          "circle-color": [
            "step",
            ["coalesce", ["get", "depth_km"], -1],
            UNKNOWN_DEPTH_COLOR,
            0,
            DEPTH_BANDS[0].color,
            70,
            DEPTH_BANDS[1].color,
            300,
            DEPTH_BANDS[2].color,
          ],
          // Radien följer både magnitud och zoom. Utzoomad (hela världen på en mobil) krymper alla cirklar så att de inte
          // täcker kartan, och inzoomat växer de så att enskilda skalv syns tydligt.
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            -1,
            radiusByMagnitude(0.2),
            1.2,
            radiusByMagnitude(0.8),
            4,
            radiusByMagnitude(1.2),
          ],
          "circle-opacity": 0.6,
          "circle-stroke-width": 0.5,
          "circle-stroke-color": "#000000",
        },
      });
      map.on("click", LAYER, (e) => {
        const feature = e.features?.[0];
        if (!feature || feature.geometry.type !== "Point") return;
        new Popup({ closeButton: false })
          .setLngLat(feature.geometry.coordinates as [number, number])
          .setDOMContent(popupContent(feature.properties ?? {}))
          .addTo(map);
      });
      map.on("mouseenter", LAYER, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", LAYER, () => (map.getCanvas().style.cursor = ""));
    });

    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const source = mapRef.current?.getSource(SOURCE) as GeoJSONSource | undefined;
    source?.setData(toGeoJson(events)); // uppdatera data utan att bygga om kartan
  }, [events]);

  return <div ref={container} className="map" role="img" aria-label="World map of earthquakes from the last seven days" />;
}

export function DepthLegend() {
  return (
    <ul className="legend" aria-label="Color key: depth">
      {DEPTH_BANDS.map((band) => (
        <li key={band.key}>
          <span className="dot" style={{ background: band.color }} aria-hidden="true" /> {band.label} ({band.span})
        </li>
      ))}
    </ul>
  );
}
