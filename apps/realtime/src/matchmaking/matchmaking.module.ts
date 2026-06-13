import { Module } from '@nestjs/common';
import { MatchmakingService } from './matchmaking.service';
import { MatchmakingEloModule } from './matchmaking-elo.module';
import { DuelModule } from '../duel/duel.module';
import { InternalClientModule } from '../internal-client/internal-client.module';

@Module({
  imports: [MatchmakingEloModule, DuelModule, InternalClientModule],
  providers: [MatchmakingService],
  exports: [MatchmakingService],
})
export class MatchmakingModule {}
