import "@testing-library/jest-dom/vitest";

// jsdom saknar ResizeObserver, som Recharts använder för responsiva diagram.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
