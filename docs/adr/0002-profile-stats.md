# ADR-0002: Витрина статистики публичного профиля

- **Статус:** принято
- **Дата:** 2026-06-13
- **Контекст:** спека `docs/specs/leaderboards-admin.md` раздел B (публичный профиль, SEO)

## Контекст

`GET /users/{username}` — публичная SEO-витрина: агрегаты по дуэлям игрока (всего
дуэлей, побед, винрейт, текущий streak) плюс Эло по темам и метаданные. Игрок
участвует в дуэли как `player_a` ЛИБО `player_b`, поэтому фильтр —
`status='finished' AND (player_a = :uid OR player_b = :uid)`.

Эндпоинт публичный и кэшируемый CDN, но обязан оставаться дешёвым на горячей
таблице `duels`: на старте таблица растёт быстрее всех, кроме `answers`. Цель —
не уезжать в seq scan по `duels` при росте до десятков тысяч строк.

## Запрос

Один запрос (raw SQL — допустимая витрина статистики по conventions §SQL,
параметры через `bindparam`, без конкатенации). CTE `my_duels` отбирает
завершённые дуэли игрока; `total_duels`/`wins` — count-агрегаты; `streak` —
число подряд идущих побед с конца через оконную сумму поражений как «сброс
серии» (`losses_so_far = 0 AND is_win`). Эло по темам берётся отдельным дешёвым
JOIN `ratings`+`topics` по `(user_id)`.

```sql
WITH my_duels AS (
    SELECT d.finished_at, (d.winner_id = :uid) AS is_win
    FROM duels d
    WHERE d.status = 'finished' AND (d.player_a = :uid OR d.player_b = :uid)
),
ordered AS (
    SELECT is_win,
        SUM(CASE WHEN NOT is_win THEN 1 ELSE 0 END)
            OVER (ORDER BY finished_at DESC
                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS losses_so_far
    FROM my_duels
)
SELECT (SELECT count(*) FROM my_duels) AS total_duels,
       (SELECT count(*) FROM my_duels WHERE is_win) AS wins,
       (SELECT count(*) FROM ordered WHERE losses_so_far = 0 AND is_win) AS streak;
```

## План (EXPLAIN ANALYZE)

Снят на 20 000 дуэлях (500 пользователей, целевой игрок в ~80 дуэлях) после
`ANALYZE duels`, с индексами `ix_duels_player_a` / `ix_duels_player_b`:

```
CTE my_duels
  ->  Bitmap Heap Scan on duels d
        Recheck Cond: ((player_a = :uid) OR (player_b = :uid))
        Filter: (status = 'finished')
        ->  BitmapOr
              ->  Bitmap Index Scan on ix_duels_player_a  (rows=80)  Index Cond: (player_a = :uid)
              ->  Bitmap Index Scan on ix_duels_player_b  (rows=0)   Index Cond: (player_b = :uid)
...
Planning Time: 0.545 ms
Execution Time: 0.233 ms
```

Ключевое: предикат `OR` разрешается через **BitmapOr** двух Bitmap Index Scan —
seq scan по `duels` не возникает. Оконный расчёт streak идёт по уже
отфильтрованным ~80 строкам (Sort + WindowAgg, quicksort в памяти).

Без индексов (та же выборка) планировщик выбирал `Seq Scan on duels` с
`Rows Removed by Filter`, что на больших объёмах деградирует линейно.

## Решение

Добавлены btree-индексы `ix_duels_player_a` и `ix_duels_player_b`
(миграция `0002_profile_indexes`). Этого достаточно: PG комбинирует их через
BitmapOr для `OR`-предиката; составной/частичный индекс на старте избыточен.

## Последствия

- (+) Профиль читается index-scan'ом, без seq scan по растущей `duels`.
- (+) Два простых индекса полезны и другим запросам по участникам дуэли.
- (−) +2 индекса на запись в `duels` (вставка раз в дуэль — приемлемо).
- На очень малых объёмах планировщик может предпочесть seq scan (он дешевле) —
  это нормально; индексы вступают в игру по мере роста селективности/таблицы.
