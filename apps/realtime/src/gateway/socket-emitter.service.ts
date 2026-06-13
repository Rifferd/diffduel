import { Injectable, Logger } from '@nestjs/common';
import type { Server } from 'socket.io';
import { Rooms } from '../common/keys';
import type { IDuelEmitter } from '../duel/duel-emitter.interface';

/**
 * Implements {@link IDuelEmitter} over the Socket.IO server. Engine and
 * matchmaking depend on this (as DUEL_EMITTER); the gateway injects the live
 * `Server` instance once it's available. Emits go to the per-user room so all
 * of a user's tabs receive events and Redis-adapter fans out across instances.
 */
@Injectable()
export class SocketEmitterService implements IDuelEmitter {
  private readonly logger = new Logger(SocketEmitterService.name);
  private server: Server | null = null;

  bindServer(server: Server): void {
    this.server = server;
  }

  async joinDuelRoom(userId: string, duelId: string): Promise<void> {
    if (!this.server) {
      return;
    }
    const sockets = await this.server.in(Rooms.user(userId)).fetchSockets();
    for (const s of sockets) {
      await s.join(Rooms.duel(duelId));
    }
  }

  // Single implementation backing every overload declared on IDuelEmitter.
  toUser(userId: string, event: string, payload: unknown): void {
    if (!this.server) {
      this.logger.warn(`emit ${event} dropped: server not bound`);
      return;
    }
    this.server.to(Rooms.user(userId)).emit(event, payload);
  }
}
