import { ConsoleLogger, type LoggerService, type LogLevel } from '@nestjs/common';

/**
 * Minimal structured (JSON) logger for prod. One JSON object per line so log
 * shippers (Loki) can parse it. In dev we use Nest's pretty ConsoleLogger.
 */
export class JsonLogger extends ConsoleLogger implements LoggerService {
  private write(level: LogLevel, message: unknown, context?: unknown): void {
    const line = {
      ts: new Date().toISOString(),
      level,
      context: typeof context === 'string' ? context : undefined,
      message: typeof message === 'string' ? message : JSON.stringify(message),
    };
    process.stdout.write(`${JSON.stringify(line)}\n`);
  }

  override log(message: unknown, context?: unknown): void {
    this.write('log', message, context);
  }
  override error(message: unknown, stackOrContext?: unknown, context?: unknown): void {
    this.write('error', message, context ?? stackOrContext);
  }
  override warn(message: unknown, context?: unknown): void {
    this.write('warn', message, context);
  }
  override debug(message: unknown, context?: unknown): void {
    this.write('debug', message, context);
  }
  override verbose(message: unknown, context?: unknown): void {
    this.write('verbose', message, context);
  }
}
