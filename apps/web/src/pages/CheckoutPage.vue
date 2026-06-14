<script setup lang="ts">
import { ref } from 'vue';
import { RouterLink } from 'vue-router';

/** Платёжки нет: «Оплатить» показывает заглушку (см. docs/specs/release2.md). */
const stubShown = ref(false);

function pay(): void {
  stubShown.value = true;
}
</script>

<template>
  <div class="app">
    <nav class="appnav">
      <div class="wrap appnav__in">
        <RouterLink class="nav__logo" to="/pro"><span class="vs">VS</span>DiffDuel</RouterLink>
        <span class="appnav__sp"></span>
        <RouterLink class="appnav__link" to="/pro">← Назад к тарифам</RouterLink>
      </div>
    </nav>

    <main class="app__main">
      <div class="wrap co">
        <div class="page-head" style="padding-bottom: 0"><h1>Оформление Pro</h1></div>

        <div class="surface co-card">
          <h2>Заказ</h2>
          <div class="sum-row"><span>DiffDuel Pro · месяц</span><span class="mono">299 ₽</span></div>
          <div class="sum-row">
            <span>Промокод <b class="mono t-plus">FIRST10</b></span
            ><span class="mono diff-minus">−30 ₽</span>
          </div>
          <div class="sum-row total">
            <span>К оплате сегодня</span><span class="mono">269 ₽</span>
          </div>
          <p class="mono t-soft" style="font-size: 11px">Далее 299 ₽/мес. Отмена в любой момент.</p>
        </div>

        <div class="surface co-card">
          <h2>Способ оплаты</h2>
          <label class="radio-card is-on"
            ><input type="radio" name="pay" checked />
            <div style="flex: 1">
              <div class="radio-card__label">ЮKassa</div>
              <div class="radio-card__sub">карта · СБП · ЮMoney</div>
            </div>
            <span class="mono t-soft" style="font-size: 11px">мгновенно</span></label
          >
          <label class="radio-card"
            ><input type="radio" name="pay" />
            <div style="flex: 1">
              <div class="radio-card__label">Telegram Stars</div>
              <div class="radio-card__sub">⭐ 150 звёзд</div>
            </div>
            <span class="mono t-soft" style="font-size: 11px">из бота</span></label
          >
        </div>

        <div v-if="stubShown" class="surface co-card co-stub" role="alert" data-test="pay-stub">
          <h2>Оплата скоро</h2>
          <p class="t-soft" style="font-size: 14px; line-height: 1.6">
            Онлайн-оплата ещё не подключена. Чтобы получить Pro прямо сейчас — обратитесь к
            администратору, он выдаст подписку вручную.
          </p>
        </div>

        <button class="btn btn--duel btn--block" style="padding: 14px" type="button" @click="pay">
          Оплатить 269 ₽
        </button>
        <p class="t-soft" style="text-align: center; font-size: 12px">
          Нажимая «Оплатить», вы принимаете <a href="#" class="link-plus" @click.prevent>оферту</a>.
        </p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.co {
  max-width: 560px;
  margin: 0 auto;
  padding: 8px 0 40px;
  display: grid;
  gap: 16px;
}
.co-card {
  padding: 22px;
  display: grid;
  gap: 14px;
}
.co-card h2 {
  font: 700 16px var(--font-display);
  font-stretch: 110%;
}
.sum-row {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  padding: 6px 0;
}
.sum-row.total {
  border-top: 1px solid var(--line);
  padding-top: 12px;
  margin-top: 4px;
  font: 700 16px var(--font-body);
}
.sum-row .mono {
  font-variant-numeric: tabular-nums;
}
.co-stub {
  border-color: var(--plus);
}
.co-stub h2 {
  color: var(--plus);
}
</style>
