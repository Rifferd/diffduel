import { IoAdapter } from '@nestjs/platform-socket.io';
import { createAdapter } from '@socket.io/redis-adapter';
import type { INestApplicationContext } from '@nestjs/common';
import type { ServerOptions, Server } from 'socket.io';
import { createRedisClient, type RedisClient } from '../redis/redis.constants';

/**
 * Socket.IO adapter backed by Redis pub/sub so duel events reach players on any
 * realtime instance (horizontal scale). Uses dedicated pub/sub connections —
 * a Redis connection in subscriber mode cannot run normal commands.
 */
export class RedisIoAdapter extends IoAdapter {
  private pubClient!: RedisClient;
  private subClient!: RedisClient;

  constructor(
    app: INestApplicationContext,
    private readonly redisUrl: string,
    private readonly corsOrigins: string[],
  ) {
    super(app);
  }

  async connect(): Promise<void> {
    this.pubClient = createRedisClient(this.redisUrl);
    this.subClient = this.pubClient.duplicate();
    // ensure both are ready
    await Promise.all([this.pubClient.ping(), this.subClient.ping()]);
  }

  override async close(): Promise<void> {
    await Promise.allSettled([this.pubClient?.quit(), this.subClient?.quit()]);
  }

  override createIOServer(port: number, options?: ServerOptions): Server {
    const server = super.createIOServer(port, {
      ...options,
      cors: {
        origin: this.corsOrigins,
        credentials: true,
      },
    }) as Server;
    server.adapter(createAdapter(this.pubClient, this.subClient));
    return server;
  }
}
