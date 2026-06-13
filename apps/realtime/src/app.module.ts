import { Module } from '@nestjs/common';
import { AppConfigModule } from './config/config.module';
import { RedisModule } from './redis/redis.module';
import { EmitterModule } from './gateway/emitter.module';
import { AuthModule } from './auth/auth.module';
import { EventsModule } from './events/events.module';
import { InternalClientModule } from './internal-client/internal-client.module';
import { MatchmakingEloModule } from './matchmaking/matchmaking-elo.module';
import { DuelModule } from './duel/duel.module';
import { MatchmakingModule } from './matchmaking/matchmaking.module';
import { GatewayModule } from './gateway/gateway.module';
import { HealthModule } from './health/health.module';

@Module({
  imports: [
    AppConfigModule,
    RedisModule,
    EmitterModule,
    AuthModule,
    EventsModule,
    InternalClientModule,
    MatchmakingEloModule,
    DuelModule,
    MatchmakingModule,
    GatewayModule,
    HealthModule,
  ],
})
export class AppModule {}
