import { Module } from '@nestjs/common';
import { EloCacheService } from './elo-cache.service';

/** Standalone module for the Elo cache so both duel and matchmaking can use it
 * without a circular module dependency. */
@Module({
  providers: [EloCacheService],
  exports: [EloCacheService],
})
export class MatchmakingEloModule {}
