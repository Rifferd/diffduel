import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { Test } from '@nestjs/testing';
import type { INestApplication } from '@nestjs/common';
import { io, type Socket } from 'socket.io-client';
import jwt from 'jsonwebtoken';
import type { AddressInfo } from 'node:net';

import { AppModule } from '../src/app.module';
import { INTERNAL_CLIENT } from '../src/internal-client/internal-client.interface';
import { FakeInternalClient, makeTasks } from './helpers/fakes';
import { makeTestRedis, flushTestDb } from './helpers/redis';

// Env (incl. DUEL_TASKS_COUNT=2 to keep the test fast) is provided by
// vitest.config.ts `test.env`, set before @nestjs/config reads process.env.
const JWT_SECRET = 'test-secret-test-secret-test-secret-test-secret-test-secret';

const A = '11111111-1111-1111-1111-111111111111';
const B = '22222222-2222-2222-2222-222222222222';
const DUEL_ID = 'e2e-duel';

function token(sub: string): string {
  return jwt.sign({ sub, type: 'access' }, JWT_SECRET, { algorithm: 'HS256', expiresIn: '5m' });
}

function connect(url: string, sub: string, username: string): Socket {
  return io(`${url}/duel`, {
    auth: { token: token(sub), username },
    transports: ['websocket'],
    forceNew: true,
  });
}

function once<T = unknown>(socket: Socket, event: string): Promise<T> {
  return new Promise((resolve) => socket.once(event, (p: T) => resolve(p)));
}

describe('Duel e2e (in-process app, internal-client mocked)', () => {
  let app: INestApplication;
  let url: string;
  const redis = makeTestRedis();

  beforeAll(async () => {
    await flushTestDb(redis);
    const tasks = makeTasks(2);
    const fakeInternal = new FakeInternalClient(DUEL_ID, tasks, { [A]: 1200, [B]: 1200 });

    const moduleRef = await Test.createTestingModule({
      imports: [AppModule],
    })
      .overrideProvider(INTERNAL_CLIENT)
      .useValue(fakeInternal)
      .compile();

    app = moduleRef.createNestApplication();
    // Default IoAdapter (no Redis adapter) is fine for a single in-process node.
    await app.init();
    await app.listen(0);
    const server = app.getHttpServer();
    const address = server.address() as AddressInfo;
    url = `http://127.0.0.1:${address.port}`;
  }, 30000);

  afterAll(async () => {
    await app?.close();
    await flushTestDb(redis);
    await redis.quit();
  });

  it('runs two players through match -> countdown -> 2 tasks -> finished', async () => {
    const sa = connect(url, A, 'alice');
    const sb = connect(url, B, 'bob');

    await Promise.all([once(sa, 'connect'), once(sb, 'connect')]);

    const matchedA = once<{ duelId: string; tasksCount: number }>(sa, 'duel.matched');
    const matchedB = once(sb, 'duel.matched');

    sa.emit('queue.join', { topic: 'sql' });
    sb.emit('queue.join', { topic: 'sql' });

    const ma = await matchedA;
    await matchedB;
    expect(ma.duelId).toBe(DUEL_ID);
    expect(ma.tasksCount).toBe(2);

    // Drive both tasks via persistent listeners (avoid missing the next
    // duel.task while re-registering a one-shot handler). A answers correctly,
    // B answers wrong. Correct answer for task i is i % 4 (makeTasks).
    const seenA = new Set<number>();
    sa.on('duel.task', (t: { idx: number }) => {
      if (!seenA.has(t.idx)) {
        seenA.add(t.idx);
        sa.emit('duel.answer', { idx: t.idx, selected: t.idx % 4 });
      }
    });
    const seenB = new Set<number>();
    sb.on('duel.task', (t: { idx: number }) => {
      if (!seenB.has(t.idx)) {
        seenB.add(t.idx);
        sb.emit('duel.answer', { idx: t.idx, selected: t.idx % 4 === 0 ? 1 : 0 });
      }
    });

    const finishedA = once<{ score: { mine: number; opp: number }; winnerId: string }>(
      sa,
      'duel.finished',
    );
    const finishedB = once<{ score: { mine: number; opp: number } }>(sb, 'duel.finished');

    const [fa, fb] = await Promise.all([finishedA, finishedB]);
    expect(fa.score).toEqual({ mine: 2, opp: 0 });
    expect(fb.score).toEqual({ mine: 0, opp: 2 });
    expect(fa.winnerId).toBe(A);

    sa.disconnect();
    sb.disconnect();
  }, 25000);
});
