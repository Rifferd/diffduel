import {
  ConnectedSocket,
  MessageBody,
  OnGatewayConnection,
  OnGatewayDisconnect,
  OnGatewayInit,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Logger } from '@nestjs/common';
import type { Server, Socket } from 'socket.io';
import { TokenService } from '../auth/token.service';
import { MatchmakingService } from '../matchmaking/matchmaking.service';
import { DuelService } from '../duel/duel.service';
import { DuelEngineService } from '../duel/duel-engine.service';
import { SocketEmitterService } from './socket-emitter.service';
import { Rooms } from '../common/keys';
import { queueJoinSchema } from '../matchmaking/matchmaking.dto';
import { z } from 'zod';

interface SocketData {
  userId: string;
  username: string;
}

const answerSchema = z.object({
  idx: z.number().int().nonnegative(),
  selected: z.number().int(),
});

/**
 * Socket.IO gateway, namespace /duel. Handles handshake auth, queue and answer
 * messages, reconnect on connect and queue cleanup on disconnect.
 *
 * Multi-tab policy: a user may have multiple sockets. All sockets join the
 * per-user room `user:{id}`; events are addressed to the room so every tab
 * stays in sync. We do NOT evict older sockets — extra tabs are harmless
 * observers of the same duel. (Documented in README.)
 */
@WebSocketGateway({
  namespace: '/duel',
  // CORS is also enforced at the adapter/app level; mirror the allow-list here.
})
export class DuelGateway
  implements OnGatewayInit, OnGatewayConnection, OnGatewayDisconnect
{
  private readonly logger = new Logger(DuelGateway.name);
  @WebSocketServer() server!: Server;

  constructor(
    private readonly tokens: TokenService,
    private readonly matchmaking: MatchmakingService,
    private readonly duel: DuelService,
    private readonly engine: DuelEngineService,
    private readonly emitter: SocketEmitterService,
  ) {}

  afterInit(server: Server): void {
    this.emitter.bindServer(server);
  }

  async handleConnection(client: Socket): Promise<void> {
    const token = this.extractToken(client);
    const verified = this.tokens.verifyAccessToken(token);
    if (!verified) {
      client.emit('system.error', { code: 'unauthorized', message: 'Invalid or missing token' });
      client.disconnect(true);
      return;
    }
    const data = client.data as SocketData;
    data.userId = verified.userId;
    // username is best-effort from token; fall back to a short id.
    data.username = this.extractUsername(client) ?? verified.userId.slice(0, 8);

    await client.join(Rooms.user(verified.userId));
    this.logger.log(`connected user=${verified.userId} socket=${client.id}`);

    // Reconnect into a running duel if any.
    await this.duel.tryReconnect(verified.userId);
  }

  async handleDisconnect(client: Socket): Promise<void> {
    const data = client.data as SocketData;
    if (!data?.userId) {
      return;
    }
    // Only drop the user from queues when they have no other live sockets.
    const remaining = await this.server.in(Rooms.user(data.userId)).fetchSockets();
    const others = remaining.filter((s) => s.id !== client.id);
    if (others.length === 0) {
      await this.matchmaking.leaveAll(data.userId);
    }
    this.logger.log(`disconnected user=${data.userId} socket=${client.id}`);
  }

  @SubscribeMessage('queue.join')
  async onQueueJoin(
    @ConnectedSocket() client: Socket,
    @MessageBody() body: unknown,
  ): Promise<void> {
    const data = client.data as SocketData;
    const parsed = queueJoinSchema.safeParse(body);
    if (!parsed.success) {
      client.emit('system.error', { code: 'bad_request', message: 'Invalid queue.join payload' });
      return;
    }
    const result = await this.matchmaking.join(data.userId, data.username, parsed.data.topic);
    if (!result.ok && result.error) {
      client.emit('system.error', result.error);
    }
  }

  @SubscribeMessage('queue.leave')
  async onQueueLeave(@ConnectedSocket() client: Socket): Promise<void> {
    const data = client.data as SocketData;
    await this.matchmaking.leaveAll(data.userId);
  }

  @SubscribeMessage('duel.answer')
  async onAnswer(
    @ConnectedSocket() client: Socket,
    @MessageBody() body: unknown,
  ): Promise<void> {
    const data = client.data as SocketData;
    const parsed = answerSchema.safeParse(body);
    if (!parsed.success) {
      client.emit('system.error', { code: 'bad_request', message: 'Invalid duel.answer payload' });
      return;
    }
    const duelId = await this.duel.getActiveDuelId(data.userId);
    if (!duelId) {
      client.emit('system.error', { code: 'no_active_duel', message: 'No active duel' });
      return;
    }
    const result = await this.engine.submitAnswer(
      duelId,
      data.userId,
      parsed.data.idx,
      parsed.data.selected,
    );
    if (!result.ok && result.error) {
      client.emit('system.error', result.error);
    }
  }

  private extractToken(client: Socket): string | undefined {
    const auth = client.handshake.auth as { token?: unknown } | undefined;
    if (auth && typeof auth.token === 'string') {
      return auth.token;
    }
    // Fallback: Authorization header (Bearer) for non-browser clients.
    const header = client.handshake.headers['authorization'];
    if (typeof header === 'string' && header.startsWith('Bearer ')) {
      return header.slice('Bearer '.length);
    }
    return undefined;
  }

  private extractUsername(client: Socket): string | undefined {
    const auth = client.handshake.auth as { username?: unknown } | undefined;
    return auth && typeof auth.username === 'string' ? auth.username : undefined;
  }
}
