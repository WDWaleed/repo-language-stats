import { Redis } from "@upstash/redis";

/**
 * Upstash Redis client initialized from environment variables:
 * - UPSTASH_REDIS_REST_URL
 * - UPSTASH_REDIS_REST_TOKEN
 */
export const redis = Redis.fromEnv();
