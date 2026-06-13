import { Injectable, Logger } from '@nestjs/common';
import jwt, { type JwtPayload } from 'jsonwebtoken';
import { AppConfigService } from '../config/app-config.service';

export interface VerifiedUser {
  userId: string;
}

/**
 * Verifies access JWTs (HS256, same JWT_SECRET as Core API). Stateless:
 * checks signature, expiry and `type === 'access'` only — no DB.
 */
@Injectable()
export class TokenService {
  private readonly logger = new Logger(TokenService.name);

  constructor(private readonly config: AppConfigService) {}

  /** Returns the verified user or null if the token is invalid for any reason. */
  verifyAccessToken(token: string | undefined): VerifiedUser | null {
    if (!token || typeof token !== 'string') {
      return null;
    }
    try {
      const payload = jwt.verify(token, this.config.jwtSecret, {
        algorithms: ['HS256'],
      });
      if (typeof payload === 'string') {
        return null;
      }
      return this.extract(payload);
    } catch (err) {
      this.logger.debug(`token verification failed: ${(err as Error).message}`);
      return null;
    }
  }

  private extract(payload: JwtPayload): VerifiedUser | null {
    const type = payload['type'];
    if (type !== 'access') {
      return null;
    }
    const sub = payload.sub;
    if (typeof sub !== 'string' || sub.length === 0) {
      return null;
    }
    return { userId: sub };
  }
}
