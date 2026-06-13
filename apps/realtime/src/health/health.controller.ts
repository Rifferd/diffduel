import { Controller, Get, Inject, ServiceUnavailableException } from '@nestjs/common';
import { REDIS_CLIENT, type RedisClient } from '../redis/redis.constants';

@Controller()
export class HealthController {
  constructor(@Inject(REDIS_CLIENT) private readonly redis: RedisClient) {}

  /** Liveness + Redis readiness. 200 when Redis answers PING. */
  @Get('healthz')
  async healthz(): Promise<{ status: string; redis: string }> {
    try {
      const pong = await this.redis.ping();
      if (pong !== 'PONG') {
        throw new Error(`unexpected ping reply: ${pong}`);
      }
      return { status: 'ok', redis: 'up' };
    } catch (err) {
      throw new ServiceUnavailableException({
        status: 'error',
        redis: 'down',
        message: (err as Error).message,
      });
    }
  }
}
