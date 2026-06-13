import { z } from 'zod';

/** queue.join payload. Topic is a short slug. */
export const queueJoinSchema = z.object({
  topic: z
    .string()
    .trim()
    .min(1)
    .max(64)
    .regex(/^[a-z0-9_-]+$/, 'topic must be a lowercase slug'),
});

export type QueueJoinDto = z.infer<typeof queueJoinSchema>;
