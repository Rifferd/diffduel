import { Global, Module } from '@nestjs/common';
import { ConfigModule as NestConfigModule } from '@nestjs/config';
import { AppConfigService } from './app-config.service';
import { validateEnv } from './env.schema';

@Global()
@Module({
  imports: [
    NestConfigModule.forRoot({
      isGlobal: true,
      // Fail fast on a bad/missing env. We read process.env directly; .env
      // loading is the operator's job (compose/host), matching conventions.md.
      validate: validateEnv,
    }),
  ],
  providers: [AppConfigService],
  exports: [AppConfigService],
})
export class AppConfigModule {}
