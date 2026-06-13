// Минимальный клиент Socket.IO поверх engine.io для k6/ws.
//
// ПОЧЕМУ ТАК. У k6 нет встроенного клиента Socket.IO. Сервер (NestJS @WebSocketGateway,
// namespace /duel) говорит по протоколу Socket.IO v4 поверх engine.io v4. Чтобы k6
// (raw WebSocket) понял сервер, мы реализуем минимальный фрейминг вручную.
//
// РЕШЕНИЕ ПО HANDSHAKE. Полный «честный» путь Socket.IO — это HTTP polling-handshake
// (GET ?EIO=4&transport=polling) → получить sid → upgrade на websocket. Это хрупко и
// шумно под нагрузкой. socket.io-client сервера разрешает СРАЗУ открыть transport=websocket
// (engine.io отдаёт open-пакет прямо в ws), поэтому мы пропускаем polling и подключаемся
// напрямую по ws — это поддерживаемый путь и он стабилен под 1000+ VU.
//
// ФРЕЙМИНГ.
//   engine.io packet types (первая цифра): 0=open 1=close 2=ping 3=pong 4=message 6=noop
//   socket.io packet types (вторая цифра внутри message «4»):
//     0=CONNECT 1=DISCONNECT 2=EVENT 3=ACK 4=CONNECT_ERROR
//   EVENT с namespace: `42/duel,["queue.join",{...}]`
//   После CONNECT сервер шлёт `40/duel,{"sid":"..."}`.
//   Heartbeat: сервер шлёт `2` (ping) → клиент отвечает `3` (pong). Иначе дисконнект.
//
// МАСШТАБИРОВАНИЕ К 5k VU. См. README.md: один k6-процесс держит тысячи ws-соединений
// (executor ramping-vus). Узкое место обычно ulimit -n и память — поднять fd-лимит и
// гонять distributed (несколько агентов / k6 cloud), целясь в 5k WS на ОДИН инстанс
// realtime (§8).

const NS = '/duel';

// Кодирует socket.io EVENT в namespace /duel: 42/duel,["name",payload]
export function encodeEvent(name, payload) {
  const arr = payload === undefined ? [name] : [name, payload];
  return `42${NS},${JSON.stringify(arr)}`;
}

// socket.io CONNECT в namespace: 40/duel,
export function encodeConnect() {
  return `40${NS},`;
}

// Разбирает входящий engine.io/socket.io фрейм.
// Возвращает { kind, event?, payload?, raw }.
//   kind: 'open' | 'ping' | 'pong' | 'connect' | 'event' | 'disconnect' | 'connect_error' | 'other'
export function decode(msg) {
  if (typeof msg !== 'string' || msg.length === 0) {
    return { kind: 'other', raw: msg };
  }
  const eio = msg[0];

  if (eio === '0') {
    // open: остальное — JSON с sid/pingInterval/pingTimeout
    try {
      return { kind: 'open', payload: JSON.parse(msg.slice(1)), raw: msg };
    } catch (_e) {
      return { kind: 'open', raw: msg };
    }
  }
  if (eio === '2') return { kind: 'ping', raw: msg };
  if (eio === '3') return { kind: 'pong', raw: msg };
  if (eio !== '4') return { kind: 'other', raw: msg };

  // engine.io message → внутри socket.io пакет
  const sio = msg[1];
  // отрезаем "4" + sio-тип, затем опциональный namespace "/duel," до запятой/скобки
  let rest = msg.slice(2);
  // namespace начинается с '/'
  if (rest.startsWith('/')) {
    const comma = rest.indexOf(',');
    if (comma !== -1) {
      rest = rest.slice(comma + 1);
    }
  }

  if (sio === '0') return { kind: 'connect', payload: safeJson(rest), raw: msg };
  if (sio === '1') return { kind: 'disconnect', raw: msg };
  if (sio === '4') return { kind: 'connect_error', payload: safeJson(rest), raw: msg };
  if (sio === '2') {
    // EVENT: rest = `["name", payload]` (может быть с ack-id перед скобкой)
    const bracket = rest.indexOf('[');
    const arr = bracket === -1 ? null : safeJson(rest.slice(bracket));
    if (Array.isArray(arr)) {
      return { kind: 'event', event: arr[0], payload: arr[1], raw: msg };
    }
    return { kind: 'event', raw: msg };
  }
  return { kind: 'other', raw: msg };
}

function safeJson(s) {
  try {
    return JSON.parse(s);
  } catch (_e) {
    return undefined;
  }
}

export const PONG = '3';
export const NAMESPACE = NS;
