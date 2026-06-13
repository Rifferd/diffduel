<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink } from 'vue-router';
import { useQuery } from '@tanstack/vue-query';
import { leaderboardApi, type LeaderboardEntry } from '@/shared/api/endpoints';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();

/** Для гостя CTA «в бой» ведёт на регистрацию, для авторизованного — в приложение. */
const playTo = computed(() => (auth.isAuthenticated ? '/app' : '/register'));

/**
 * Публичный лидерборд (без auth). Лендинг не должен падать без бэкенда:
 * при ошибке/пустом ответе показываем заглушку.
 */
const { data: board, isError } = useQuery({
  queryKey: ['public-leaderboard'],
  queryFn: () => leaderboardApi.public({ scope: 'global', limit: 10 }),
  retry: false,
  staleTime: 60_000,
});

const entries = computed<LeaderboardEntry[]>(() => board.value ?? []);
const hasEntries = computed(() => entries.value.length > 0);
const showFallback = computed(() => isError.value || !hasEntries.value);
</script>

<template>
  <div class="landing">
    <nav class="nav">
      <div class="wrap nav__in">
        <RouterLink class="nav__logo" to="/"><span class="vs">VS</span>DiffDuel</RouterLink>
        <RouterLink class="nav__link" :to="playTo">Дуэли</RouterLink>
        <RouterLink class="nav__link" :to="playTo">Тренировка</RouterLink>
        <RouterLink class="nav__link" :to="playTo">Лидерборд</RouterLink>
        <span class="nav__spacer"></span>
        <div class="nav__cta-row">
          <template v-if="auth.isAuthenticated">
            <RouterLink class="btn btn--ghost nav__cta-secondary" to="/app">В приложение</RouterLink>
            <RouterLink class="btn btn--duel" to="/app">В бой</RouterLink>
          </template>
          <template v-else>
            <RouterLink class="btn btn--ghost nav__cta-secondary" to="/login">Войти</RouterLink>
            <RouterLink class="btn btn--duel" to="/register">Регистрация</RouterLink>
          </template>
        </div>
      </div>
    </nav>

    <header class="hero">
      <div class="hero__split"></div>
      <div class="wrap hero__grid">
        <div>
          <span class="eyebrow">// арена для разработчиков</span>
          <h1>Докажи кодом.<br />Дуэль <span class="u">1×1</span> на скорость.</h1>
          <p class="hero__lead">
            Одинаковые задачи по SQL, JS и Python — двум игрокам, в реальном времени. Побеждает тот,
            кто думает быстрее. Рейтинг Эло, лидерборды, разбор ошибок от AI.
          </p>
          <div class="hero__cta">
            <RouterLink class="btn btn--duel" :to="playTo">Найти соперника · ~20 сек</RouterLink>
            <RouterLink class="btn btn--ghost" :to="playTo">Сначала потренироваться</RouterLink>
          </div>
          <div class="hero__meta">
            <span><b>12 480</b>дуэлей сегодня</span>
            <span><b>638</b>игроков онлайн</span>
            <span><b class="diff-plus">+24</b>Эло за победу</span>
          </div>
        </div>

        <!-- live duel mock -->
        <div class="duel-card" aria-label="Экран дуэли">
          <div class="duel-head">
            <div class="duel-head__player">
              <span class="ava ava--you ava--md">ВЫ</span>
              <div>
                <div class="duel-head__nm duel-head__nm--you">anton_dev</div>
                <div class="duel-head__elo">1 482 Elo</div>
              </div>
            </div>
            <span class="duel-head__vs">VS</span>
            <div class="duel-head__player duel-head__player--right">
              <div>
                <div class="duel-head__nm duel-head__nm--rival">sql_ninja</div>
                <div class="duel-head__elo">1 507 Elo</div>
              </div>
              <span class="ava ava--rival ava--md">SN</span>
            </div>
          </div>
          <div class="duel-timer">
            <span class="duel-timer__num">0:19</span>
            <div class="tbar tbar--run"><i></i></div>
            <span class="duel-timer__step">3 / 5</span>
          </div>
          <div class="duel-card__body">
            <div class="task-label">JS · найди баг</div>
            <pre class="code"><span class="c">// Почему счётчик печатает 3, 3, 3?</span>
<span class="k">for</span> (<span class="err"><span class="k">var</span></span> i = 0; i &lt; 3; i++) {
  setTimeout(() =&gt; console.log(i), 100);
}</pre>
            <div class="opts">
              <button class="opt is-selected" type="button">var не блочная — заменить на let</button>
              <button class="opt" type="button">setTimeout всегда async</button>
              <button class="opt" type="button">нужен await перед log</button>
              <button class="opt" type="button">замыкание тут невозможно</button>
            </div>
          </div>
          <div class="feed">
            › sql_ninja ответил за <b class="m">7.4s</b> · вы лидируете <b class="p">2:1</b>
          </div>
        </div>
      </div>
    </header>

    <main>
      <section>
        <div class="wrap">
          <div class="sec-head">
            <h2>Как проходит дуэль</h2>
            <span class="eyebrow">// 90 секунд от клика до результата</span>
          </div>
          <div class="difflog">
            <div class="difflog__row">
              <div class="difflog__gut diff-plus">+ 0:00</div>
              <div class="difflog__body">
                <h3>Матчмейкинг</h3>
                <p>
                  Подбираем соперника вашего уровня (±150 Эло). Очередь пуста — выйдет «призрак»:
                  записанная игра реального игрока вашего рейтинга.
                </p>
              </div>
            </div>
            <div class="difflog__row">
              <div class="difflog__gut diff-plus">+ 0:20</div>
              <div class="difflog__body">
                <h3>5 задач × 30 секунд</h3>
                <p>
                  SQL-запрос, баг в коде, вопрос на конкурентность. Вы видите темп соперника, но не
                  его ответы.
                </p>
              </div>
            </div>
            <div class="difflog__row">
              <div class="difflog__gut diff-minus">− 2:50</div>
              <div class="difflog__body">
                <h3>Результат и Эло</h3>
                <p>
                  Победа — <b class="mono diff-plus">+24</b>, поражение —
                  <b class="mono diff-minus">−18</b>. Карточка результата готова для отправки в
                  рабочий чат.
                </p>
              </div>
            </div>
            <div class="difflog__row">
              <div class="difflog__gut diff-plus">+ 3:00</div>
              <div class="difflog__body">
                <h3>AI-разбор ошибок · Pro</h3>
                <p>Объясняем каждую ошибку и подбираем тренировку по слабым темам.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section style="padding-top: 0">
        <div class="wrap row2">
          <div>
            <div class="sec-head">
              <h2>Лидерборд недели</h2>
              <RouterLink class="btn btn--ghost" :to="playTo">Весь рейтинг</RouterLink>
            </div>
            <div class="board">
              <table>
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">Игрок</th>
                    <th scope="col">Эло</th>
                  </tr>
                </thead>
                <tbody v-if="!showFallback" data-test="board-rows">
                  <tr v-for="entry in entries" :key="entry.user_id" :class="{ 'is-top': entry.rank === 1 }">
                    <td class="num">{{ entry.rank }}</td>
                    <td>{{ entry.username }}</td>
                    <td class="num">{{ entry.elo.toLocaleString('ru-RU') }}</td>
                  </tr>
                </tbody>
                <tbody v-else data-test="board-fallback">
                  <tr class="is-top"><td class="num">1</td><td>masha_pg</td><td class="num">2 104</td></tr>
                  <tr><td class="num">2</td><td>sql_ninja</td><td class="num">1 998</td></tr>
                  <tr><td class="num">3</td><td>kotlin_kid</td><td class="num">1 951</td></tr>
                </tbody>
              </table>
            </div>
            <p v-if="showFallback" class="share-note">
              Рейтинг наполнится после первых дуэлей.
            </p>
          </div>
          <div>
            <div class="sec-head"><h2>Карточка победы</h2></div>
            <div class="share">
              <div class="share__top"><span>DIFFDUEL · ДУЭЛЬ #84 213</span><span>SQL</span></div>
              <div class="share__score">
                <div>
                  <div class="share__s">4</div>
                  <div class="share__n">anton_dev</div>
                  <div class="share__d share__d--plus">+24 Elo</div>
                </div>
                <div class="share__colon">:</div>
                <div>
                  <div class="share__s">2</div>
                  <div class="share__n">sql_ninja</div>
                  <div class="share__d share__d--minus">−18 Elo</div>
                </div>
              </div>
              <div class="share__bottom"><span>лучшее время 6.2s</span><span>diffduel.com</span></div>
            </div>
            <p class="share-note">
              Генерируется автоматически после каждой дуэли. Одна кнопка — и она в Telegram-чате
              команды с вызовом по ссылке.
            </p>
          </div>
        </div>
      </section>

      <section style="padding-top: 0">
        <div class="wrap">
          <div class="founder">
            <div>
              <span class="eyebrow eyebrow--arena">// каждую пятницу · 19:00</span>
              <h2>
                Вызови основателя:<br /><span class="riff">Riff</span>erd против твоего
                <span class="diff">diff</span>'а
              </h2>
              <p>
                Раз в неделю Rifferd принимает дуэли от всех желающих. Победил основателя — навсегда
                попадаешь в зал славы и получаешь месяц Pro.
              </p>
              <div class="hero__cta" style="position: relative; z-index: 1">
                <RouterLink class="btn btn--duel" :to="playTo">Встать в очередь на пятницу</RouterLink>
                <RouterLink class="btn btn--dark-ghost" :to="playTo">Профиль Rifferd</RouterLink>
              </div>
              <div class="founder__stats">
                <span><b>1 718</b>Эло основателя</span>
                <span><b>134 : 41</b>счёт против сообщества</span>
                <span><b>41</b>имя в зале славы</span>
              </div>
            </div>
            <div class="f-card">
              <div class="task-label">Зал славы · победили Rifferd</div>
              <div class="f-card__row">
                <span class="f-card__pos">1</span><span class="ava ava--3 ava--sm">MP</span><b>masha_pg</b
                ><span class="f-card__res f-card__res--win">4:1 · SQL</span>
              </div>
              <div class="f-card__row">
                <span class="f-card__pos">2</span><span class="ava ava--4 ava--sm">KK</span
                ><b>kotlin_kid</b
                ><span class="f-card__res f-card__res--win">3:2 · JS</span>
              </div>
              <div class="f-card__row">
                <span class="f-card__pos">3</span><span class="ava ava--5 ava--sm">DB</span
                ><b>db_whisperer</b
                ><span class="f-card__res f-card__res--win">3:2 · Python</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section style="padding-top: 0">
        <div class="wrap">
          <div class="sec-head">
            <h2>Тарифы</h2>
            <span class="eyebrow">// дуэли бесплатны навсегда</span>
          </div>
          <div class="plans">
            <div class="plan">
              <h3>Free</h3>
              <div class="plan__price">0 ₽</div>
              <div class="plan__per">навсегда</div>
              <ul>
                <li>Безлимитные дуэли и тренировки</li>
                <li>Рейтинг и лидерборды</li>
                <li>Карточки результатов</li>
              </ul>
              <RouterLink class="btn btn--ghost btn--block" :to="playTo">Начать</RouterLink>
            </div>
            <div class="plan plan--pro">
              <h3>Pro</h3>
              <div class="plan__price">299 ₽</div>
              <div class="plan__per">в месяц</div>
              <ul>
                <li>AI-разбор каждой ошибки</li>
                <li>Статистика слабых тем за 90 дней</li>
                <li>Темы карточек и бейдж в профиле</li>
              </ul>
              <RouterLink class="btn btn--duel btn--block" :to="playTo">Оформить Pro</RouterLink>
            </div>
            <div class="plan">
              <h3>Команда</h3>
              <div class="plan__price">9 900 ₽</div>
              <div class="plan__per">за приватный турнир</div>
              <ul>
                <li>Свой набор задач</li>
                <li>Закрытый лидерборд команды</li>
                <li>Отчёт для тимлида</li>
              </ul>
              <RouterLink class="btn btn--ghost btn--block" :to="playTo">Собрать турнир</RouterLink>
            </div>
          </div>
        </div>
      </section>
    </main>

    <footer>
      <div class="wrap">
        <span>DiffDuel by Rifferd · собран AI-only — техблог о разработке в Telegram</span>
        <span class="mono">v0.8.2 · status: <span class="diff-plus">operational</span></span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* ---- page-local layout, перенесено дословно из design/pages/landing.html ---- */
.nav__cta-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.hero {
  position: relative;
  overflow: hidden;
  padding: 72px 0 84px;
}
.hero__split {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.hero__split::before,
.hero__split::after {
  content: '';
  position: absolute;
  top: -20%;
  bottom: -20%;
  width: 60%;
}
.hero__split::before {
  left: -14%;
  background: linear-gradient(rgb(31 157 85 / 0.08), rgb(31 157 85 / 0.02));
  transform: skewX(var(--split-skew));
}
.hero__split::after {
  right: -14%;
  background: linear-gradient(rgb(229 72 77 / 0.07), rgb(229 72 77 / 0.02));
  transform: skewX(var(--split-skew));
}
.hero__grid {
  position: relative;
  display: grid;
  grid-template-columns: 1.05fr 0.95fr;
  gap: 56px;
  align-items: center;
}
.hero h1 {
  font: 800 clamp(40px, 5vw, 62px) / 1.02 var(--font-display);
  font-stretch: 110%;
  letter-spacing: -0.02em;
  margin: 14px 0 18px;
}
.hero__lead {
  color: var(--ink-soft);
  font-size: 17px;
  max-width: 46ch;
  margin-bottom: 28px;
}
.hero__cta {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.hero__meta {
  margin-top: 26px;
  display: flex;
  gap: 26px;
  color: var(--ink-soft);
  font-size: 13px;
  flex-wrap: wrap;
}
.hero__meta b {
  font: 700 15px var(--font-mono);
  color: var(--ink);
  display: block;
  font-variant-numeric: tabular-nums;
}

/* live duel card */
.duel-card {
  background: var(--arena);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
  color: var(--arena-ink);
  overflow: hidden;
  border: 1px solid var(--frame);
}
.duel-card .duel-timer,
.duel-card .feed {
  padding-left: 18px;
  padding-right: 18px;
}
.duel-card .duel-timer {
  border-bottom: 1px solid var(--arena-line);
}
.duel-card__body {
  padding: 18px;
}
.task-label {
  font: 700 10px var(--font-mono);
  letter-spacing: 0.12em;
  color: var(--arena-soft);
  text-transform: uppercase;
  margin-bottom: 10px;
}
.duel-card .opts {
  margin-top: 14px;
}

section {
  padding: 72px 0;
}
.sec-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 34px;
}
.sec-head h2 {
  font: 800 32px var(--font-display);
  font-stretch: 110%;
}
.row2 {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 28px;
  align-items: start;
}
.share-note {
  margin-top: 14px;
  color: var(--ink-soft);
  font-size: 13px;
}
.plans {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

/* founder band */
.founder {
  background: var(--arena);
  border-radius: var(--radius-lg);
  color: var(--arena-ink);
  box-shadow: var(--shadow);
  border: 1px solid var(--frame);
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 30px;
  align-items: center;
  padding: 38px 40px;
}
.founder::after {
  content: '';
  position: absolute;
  inset: -30% -8% -30% 58%;
  background: linear-gradient(rgb(229 72 77 / 0.2), transparent);
  transform: skewX(var(--split-skew));
  pointer-events: none;
}
.founder h2 {
  font: 800 30px var(--font-display);
  font-stretch: 110%;
  margin: 10px 0;
}
.founder h2 .riff {
  color: var(--minus-bright);
}
.founder h2 .diff {
  color: var(--plus-bright);
}
.founder p {
  color: var(--arena-soft);
  font-size: 15px;
  max-width: 52ch;
  margin-bottom: 22px;
}
.founder__stats {
  display: flex;
  gap: 26px;
  font-size: 12px;
  color: var(--arena-soft);
  flex-wrap: wrap;
  margin-top: 24px;
}
.founder__stats b {
  display: block;
  font: 700 17px var(--font-mono);
  color: var(--arena-ink);
  font-variant-numeric: tabular-nums;
}
.f-card {
  position: relative;
  z-index: 1;
  background: var(--arena-2);
  border: 1px solid var(--arena-line);
  border-radius: var(--radius-lg);
  padding: 20px;
}
.f-card__row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--arena-line);
  font-size: 13px;
}
.f-card__row:last-of-type {
  border-bottom: 0;
}
.f-card__pos {
  font: 700 12px var(--font-mono);
  color: var(--arena-soft);
  width: 20px;
}
.f-card__res {
  margin-left: auto;
  font: 700 12px var(--font-mono);
}

footer {
  border-top: 1px solid var(--line);
  padding: 34px 0;
  color: var(--ink-soft);
  font-size: 13px;
}
footer .wrap {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

@media (max-width: 880px) {
  .hero__grid,
  .row2,
  .plans,
  .founder {
    grid-template-columns: 1fr;
  }
  .hero {
    padding: 40px 0 56px;
  }
  section {
    padding: 48px 0;
  }
  .nav__cta-row {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .tbar--run i {
    animation: none;
  }
}
</style>
