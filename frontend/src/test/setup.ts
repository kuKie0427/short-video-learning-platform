// Vitest 测试环境初始化
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

/**
 * Node 22+ 实验性全局 localStorage 与当前 jsdom 提供的实现均为空壳
 * （无 Storage 方法，见 node 的 --localstorage-file 警告），
 * 这里无条件替换为完整的内存实现，保证 AuthContext（src/context/AuthContext.tsx）
 * 依赖的 getItem/setItem/removeItem/clear 可用。
 */
class MemoryStorage implements Storage {
  private store = new Map<string, string>();

  get length(): number {
    return this.store.size;
  }

  clear(): void {
    this.store.clear();
  }

  getItem(key: string): string | null {
    return this.store.has(key) ? this.store.get(key)! : null;
  }

  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null;
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }

  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }
}

const storage = new MemoryStorage();
Object.defineProperty(globalThis, 'localStorage', {
  value: storage,
  configurable: true,
  writable: true,
});

// 每个用例结束后清理 DOM 与 localStorage，保证用例隔离
afterEach(() => {
  cleanup();
  localStorage.clear();
});
