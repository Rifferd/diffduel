import { Module } from '@nestjs/common';
import { INTERNAL_CLIENT } from './internal-client.interface';
import { InternalClientService } from './internal-client.service';

@Module({
  providers: [
    InternalClientService,
    { provide: INTERNAL_CLIENT, useExisting: InternalClientService },
  ],
  exports: [INTERNAL_CLIENT],
})
export class InternalClientModule {}
