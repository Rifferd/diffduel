<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import AppNav from '@/components/AppNav.vue';

const auth = useAuthStore();
const isPro = computed(() => auth.user?.is_pro === true);
</script>

<template>
  <div class="app">
    <AppNav active="pro" />

    <main class="app__main">
      <div class="wrap">
        <div class="page-head" style="text-align: center">
          <span class="eyebrow">// дуэли бесплатны навсегда · Pro усиливает рост</span>
          <h1>DiffDuel Pro</h1>
          <p style="margin: 6px auto 0">
            AI-разбор каждой ошибки и статистика слабых тем — чтобы Эло росло быстрее.
          </p>
          <p v-if="isPro" class="pro-active" data-test="pro-active">
            ✓ Pro уже активен — все функции открыты.
          </p>
        </div>

        <div class="section">
          <div class="grid-3">
            <div class="plan">
              <h3>Free</h3>
              <div class="plan__price">0 ₽</div>
              <div class="plan__per">навсегда</div>
              <ul>
                <li>Безлимитные дуэли</li>
                <li>Рейтинг и лидерборды</li>
                <li>Карточки результатов</li>
              </ul>
              <RouterLink class="btn btn--ghost btn--block" to="/app">Текущий план</RouterLink>
            </div>
            <div class="plan plan--pro">
              <h3>Pro</h3>
              <div class="plan__price">299 ₽</div>
              <div class="plan__per">в месяц</div>
              <ul>
                <li>AI-разбор каждой ошибки</li>
                <li>Статистика 90 дней</li>
                <li>Темы карточек + бейдж</li>
              </ul>
              <RouterLink class="btn btn--duel btn--block" to="/checkout">Оформить Pro</RouterLink>
            </div>
            <div class="plan">
              <h3>Pro · год</h3>
              <div class="plan__price">2 490 ₽</div>
              <div class="plan__per">в год · −30%</div>
              <ul>
                <li>Всё из Pro</li>
                <li>Два месяца в подарок</li>
                <li>Ранний доступ к фичам</li>
              </ul>
              <RouterLink class="btn btn--ghost btn--block" to="/checkout">Оформить год</RouterLink>
            </div>
          </div>
        </div>

        <div class="section">
          <div class="section__head"><h2>Сравнение</h2></div>
          <div class="surface" style="overflow: hidden">
            <table class="cmp">
              <thead>
                <tr>
                  <th scope="col">Возможность</th>
                  <th scope="col">Free</th>
                  <th scope="col">Pro</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Дуэли и рейтинг</td>
                  <td><span class="mark-y">+</span></td>
                  <td><span class="mark-y">+</span></td>
                </tr>
                <tr>
                  <td>Лидерборды и турниры</td>
                  <td><span class="mark-y">+</span></td>
                  <td><span class="mark-y">+</span></td>
                </tr>
                <tr>
                  <td>AI-разбор ошибок</td>
                  <td><span class="mark-n">−</span></td>
                  <td><span class="mark-y">+</span></td>
                </tr>
                <tr>
                  <td>Статистика 90 дней</td>
                  <td><span class="mark-n">−</span></td>
                  <td><span class="mark-y">+</span></td>
                </tr>
                <tr>
                  <td>Темы карточек результата</td>
                  <td><span class="mark-n">−</span></td>
                  <td><span class="mark-y">+</span></td>
                </tr>
                <tr>
                  <td>Бейдж Pro в профиле</td>
                  <td><span class="mark-n">−</span></td>
                  <td><span class="mark-y">+</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="section">
          <div class="section__head"><h2>Вопросы</h2></div>
          <div class="acc">
            <details class="acc__item" open>
              <summary>Дуэли правда останутся бесплатными?</summary>
              <div class="acc__body">
                Да. Pro не ограничивает игру — он ускоряет обучение через AI-разбор и аналитику.
              </div>
            </details>
            <details class="acc__item">
              <summary>Можно отменить в любой момент?</summary>
              <div class="acc__body">
                Да, из настроек. Доступ сохранится до конца оплаченного периода, автопродление
                отключится.
              </div>
            </details>
            <details class="acc__item">
              <summary>Какие способы оплаты?</summary>
              <div class="acc__body">
                ЮKassa (карта, СБП) и Telegram Stars. Для годовой подписки доступен возврат за
                неиспользованный период.
              </div>
            </details>
          </div>
        </div>
        <div style="height: 24px"></div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.cmp {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.cmp th,
.cmp td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--line);
  text-align: left;
}
.cmp th:not(:first-child),
.cmp td:not(:first-child) {
  text-align: center;
}
.cmp thead th {
  font: 700 13px var(--font-display);
  font-stretch: 110%;
}
.cmp .mark-y {
  color: var(--plus);
  font: 700 15px var(--font-mono);
}
.cmp .mark-n {
  color: var(--minus);
  font: 700 15px var(--font-mono);
}
.pro-active {
  margin: 10px auto 0;
  color: var(--plus);
  font: 700 14px var(--font-mono);
}
</style>
