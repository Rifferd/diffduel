import { defineStore } from 'pinia';
import type { DuelResultData } from '@/composables/useDuel';

/**
 * Хранит результат последней дуэли для экрана /duel/result.
 *
 * Только в памяти (как access-токен) — при перезагрузке страницы пропадает,
 * и DuelResultPage редиректит на главную (см. ТЗ §3).
 */
interface DuelResultState {
  result: DuelResultData | null;
}

export const useDuelResultStore = defineStore('duelResult', {
  state: (): DuelResultState => ({ result: null }),
  actions: {
    set(result: DuelResultData): void {
      this.result = result;
    },
    clear(): void {
      this.result = null;
    },
  },
});
