import asyncio
import time

class TokenBucket:
    def __init__(self, capacity: int = 10, refill_rate: float = 0.5):
        """
        capacity: Max burst size (tokens).
        refill_rate: Tokens added per second.
        """
        self.capacity = float(capacity)
        self._tokens = float(capacity)
        self.refill_rate = refill_rate
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1):
        """
        Waits until sufficient tokens are available.
        """
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.last_refill
                
                # Refill
                new_tokens = elapsed * self.refill_rate
                self._tokens = min(self.capacity, self._tokens + new_tokens)
                self.last_refill = now
                
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                
                # Wait for enough tokens
                missing = tokens - self._tokens
                wait_time = missing / self.refill_rate
                
                # Release lock while waiting? No, logic is simpler if we hold lock or carefully checking.
                # If we hold lock, nobody else can acquire. But nobody else can refill either.
                # Correct pattern: Calculate wait time, release lock (via generic wait?), then try again.
                # However, usually easiest to just wait effectively inside the critical section if short,
                # OR (better for concurrency) - calculate wait, await sleep WITHOUT lock?
                # Let's do a simple non-blocking-check sleep loop.
                
                # Actually, standard Token Bucket implementation with asyncio:
                # We can calculate exactly when we will have tokens.
                pass 
                
            # Re-implementation for correct asyncio waiting
            # We need to wait without holding the lock if the wait is long.
            
    # Simpler Implementation avoiding complex lock handoffs
    async def wait_for_token(self):
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                self._tokens = min(self.capacity, self._tokens + (elapsed * self.refill_rate))
                self.last_refill = now
                
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                
                # Calculate required wait
                missing = 1.0 - self._tokens
                wait_seconds = missing / self.refill_rate
            
            # Sleep outside lock
            await asyncio.sleep(wait_seconds)

# Global Limiter Instance (Conservative for Free Tier)
# 15 RPM = 0.25 requests/sec. 
# Let's set slightly higher: 60 RPM = 1.0/sec burstable to 10.
global_limiter = TokenBucket(capacity=5, refill_rate=0.5) 
