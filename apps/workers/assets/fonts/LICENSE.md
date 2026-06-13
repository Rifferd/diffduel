# Шрифты share-карточек

В сборку положены шрифты семейства **DejaVu** (`DejaVuSans*`, `DejaVuSansMono*`).

## Почему DejaVu, а не JetBrains Mono / Archivo

Спека (раздел C / §13) допускает JetBrains Mono + Archivo «или дефолтные,
если лицензия неясна — но моноширинный для цифр обязателен». Чтобы гарантировать
чистоту лицензии при сборке без сетевого доступа, бандлим **DejaVu** —
шрифт с заведомо свободной, разрешающей перераспространение лицензией
(Bitstream Vera Fonts Copyright + изменения проекта DejaVu, public-domain-friendly).

Распределение ролей в карточке:

- `DejaVuSansMono.ttf` / `DejaVuSansMono-Bold.ttf` — **все цифры**
  (счёт, дельты Эло) моноширинным, как требует §13;
- `DejaVuSans-Bold.ttf` — ник победителя и заголовок (роль Archivo);
- `DejaVuSans.ttf` — водяной знак / вспомогательный текст.

При желании заменить на JetBrains Mono + Archivo достаточно положить их TTF
рядом и обновить имена файлов в `src/workers/render.py` (`_FONT_*`).

## Лицензия DejaVu

Bitstream Vera Fonts Copyright (c) 2003 Bitstream, Inc.
DejaVu changes are in public domain.
Полный текст: https://dejavu-fonts.github.io/License.html
