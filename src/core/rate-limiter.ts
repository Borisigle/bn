export class AsyncRateLimiter {
    private tokens: number;
    private lastRefill: number;
    private queue: (() => void)[] = [];

    constructor(private maxCalls: number, private periodSeconds: number) {
        this.tokens = maxCalls;
        this.lastRefill = Date.now();
    }

    async acquire(): Promise<void> {
        this.refill();
        if (this.tokens >= 1) {
            this.tokens -= 1;
            return;
        }

        return new Promise((resolve) => {
            this.queue.push(resolve);
            this.scheduleProcessing();
        });
    }

    private refill() {
        const now = Date.now();
        const elapsed = (now - this.lastRefill) / 1000;
        const newTokens = elapsed * (this.maxCalls / this.periodSeconds);
        if (newTokens > 0) {
            this.tokens = Math.min(this.maxCalls, this.tokens + newTokens);
            this.lastRefill = now;
        }
    }

    private scheduleProcessing() {
        const interval = (this.periodSeconds / this.maxCalls) * 1000;
        const process = () => {
            this.refill();
            while (this.queue.length > 0 && this.tokens >= 1) {
                this.tokens -= 1;
                const resolve = this.queue.shift();
                if (resolve) resolve();
            }
            if (this.queue.length > 0) {
                setTimeout(process, interval);
            }
        };
        setTimeout(process, interval);
    }
}
