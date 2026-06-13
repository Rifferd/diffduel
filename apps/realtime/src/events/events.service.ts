import { Injectable, Logger, type OnModuleDestroy, type OnModuleInit } from '@nestjs/common';
import { Kafka, type Producer } from 'kafkajs';
import { AppConfigService } from '../config/app-config.service';

export interface AnswerSubmittedPayload {
  duel_id: string;
  user_id: string;
  task_id: string;
  selected: number | null;
  correct: boolean;
  time_ms: number | null;
  idx: number;
}

const TOPIC = 'answers.submitted';

/**
 * kafkajs producer for `answers.submitted`. Best-effort per spec: broker
 * outage must NOT break a duel — failures are logged and swallowed, never
 * awaited on the hot answer path in a way that blocks the player.
 */
@Injectable()
export class EventsService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(EventsService.name);
  private readonly kafka: Kafka;
  private producer: Producer | null = null;
  private connected = false;

  constructor(private readonly config: AppConfigService) {
    this.kafka = new Kafka({
      clientId: 'realtime',
      brokers: this.config.kafkaBrokers,
      // Keep connection attempts short so a dead broker doesn't stall startup.
      retry: { retries: 3 },
      logCreator: () => () => {
        /* silence kafkajs internal logs; we log our own */
      },
    });
  }

  async onModuleInit(): Promise<void> {
    this.producer = this.kafka.producer();
    try {
      await this.producer.connect();
      this.connected = true;
    } catch (err) {
      this.connected = false;
      this.logger.warn(`Kafka producer connect failed (best-effort): ${(err as Error).message}`);
    }
  }

  async onModuleDestroy(): Promise<void> {
    if (this.producer && this.connected) {
      try {
        await this.producer.disconnect();
      } catch {
        /* ignore on shutdown */
      }
    }
  }

  /** Fire-and-forget produce. Never throws to the caller. */
  emitAnswerSubmitted(payload: AnswerSubmittedPayload): void {
    void this.produce(payload);
  }

  private async produce(payload: AnswerSubmittedPayload): Promise<void> {
    if (!this.producer) {
      return;
    }
    const envelope = {
      v: 1,
      type: TOPIC,
      occurred_at: new Date().toISOString(),
      payload,
    };
    try {
      if (!this.connected) {
        await this.producer.connect();
        this.connected = true;
      }
      await this.producer.send({
        topic: TOPIC,
        messages: [{ key: payload.user_id, value: JSON.stringify(envelope) }],
      });
    } catch (err) {
      this.connected = false;
      this.logger.warn(`produce ${TOPIC} failed (best-effort): ${(err as Error).message}`);
    }
  }
}
