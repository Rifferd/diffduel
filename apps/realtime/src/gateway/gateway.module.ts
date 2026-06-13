import { Module } from '@nestjs/common';
import { DuelGateway } from './duel.gateway';
import { AuthModule } from '../auth/auth.module';
import { DuelModule } from '../duel/duel.module';
import { MatchmakingModule } from '../matchmaking/matchmaking.module';

@Module({
  imports: [AuthModule, DuelModule, MatchmakingModule],
  providers: [DuelGateway],
})
export class GatewayModule {}
