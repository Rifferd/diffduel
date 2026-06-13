import { Global, Module } from '@nestjs/common';
import { SocketEmitterService } from './socket-emitter.service';
import { DUEL_EMITTER } from '../duel/duel-emitter.interface';

/**
 * Global provider for the duel emitter. Made global so engine/matchmaking can
 * inject DUEL_EMITTER without a module dependency on the gateway (which itself
 * depends on those modules — avoids a cycle).
 */
@Global()
@Module({
  providers: [
    SocketEmitterService,
    { provide: DUEL_EMITTER, useExisting: SocketEmitterService },
  ],
  exports: [SocketEmitterService, DUEL_EMITTER],
})
export class EmitterModule {}
