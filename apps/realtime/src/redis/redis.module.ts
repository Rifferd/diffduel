import { Global, Module } from '@nestjs/common';
import { AppConfigService } from '../config/app-config.service';
import { REDIS_CLIENT, createRedisClient, type RedisClient } from './redis.constants';

@Global()
@Module({
  providers: [
    {
      provide: REDIS_CLIENT,
      inject: [AppConfigService],
      useFactory: (config: AppConfigService): RedisClient => createRedisClient(config.redisUrl),
    },
  ],
  exports: [REDIS_CLIENT],
})
export class RedisModule {}
