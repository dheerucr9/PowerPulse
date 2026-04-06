import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

function createStorageMock() {
  let store = new Map<string, string>();

  return {
    getItem(key: string) {
      return store.has(key) ? store.get(key) ?? null : null;
    },
    setItem(key: string, value: string) {
      store.set(key, value);
    },
    removeItem(key: string) {
      store.delete(key);
    },
    clear() {
      store = new Map<string, string>();
    }
  };
}

const localStorageMock = createStorageMock();

Object.defineProperty(window, "localStorage", {
  value: localStorageMock,
  configurable: true
});

Object.defineProperty(globalThis, "localStorage", {
  value: localStorageMock,
  configurable: true
});

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.restoreAllMocks();
});

vi.mock("echarts", () => {
  const instance = {
    resize: vi.fn(),
    dispose: vi.fn(),
    setOption: vi.fn()
  };

  return {
    init: vi.fn(() => instance),
    getInstanceByDom: vi.fn(() => instance)
  };
});
