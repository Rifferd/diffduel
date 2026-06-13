import { Module } from '@nestjs/common';
import { DuelStateRepository } from './duel-state.repository';
import { DuelEngineService } from './duel-engine.service';
import { DuelService } from './duel.service';
import { EventsModule } from '../events/events.module';
import { InternalClientModule } from '../internal-client/internal-client.module';
import { MatchmakingEloModule } from '../matchmaking/matchmaking-elo.module';

@Module({
  imports: [EventsModule, InternalClientModule, MatchmakingEloModule],
  providers: [DuelStateRepository, DuelEngineService, DuelService],
  exports: [DuelStateRepository, DuelEngineService, DuelService],
})
export class DuelModule {}
