import { describe, it, expect } from 'vitest';
import { ArbitragePureDetector } from '../src/strategies/arbitrage-pure/detector.js';
import { ArbitragePureExecutor } from '../src/strategies/arbitrage-pure/executor.js';
import { Arbitrage, BinaryMarket } from '../src/strategies/arbitrage-pure/types.js';

class StubLogger {
    infos: string[] = [];
    errors: string[] = [];
    logInfo(msg: string) { this.infos.push(msg); }
    logError(msg: string) { this.errors.push(msg); }
}

class StubPolymarketClient {
    orders: any[] = [];
    constructor(private markets: BinaryMarket[]) {}
    async initialize() {}
    async getTopMarkets(limit: number) { return this.markets.slice(0, limit); }
    async createMarketOrder(cfg: any) {
        this.orders.push(cfg);
        return {
            order_id: 'paper',
            market: cfg.market,
            outcome: cfg.outcome,
            side: cfg.side,
            filled_price: cfg.expected_price,
            shares: cfg.shares,
        };
    }
    async redeem(yes: number, no: number, conditionId: string) {
        if (yes <= 0 || no <= 0) return 0;
        return Math.min(yes, no);
    }
}

describe('ArbitragePureDetector', () => {
    it('finds long and short and sorts by profit', async () => {
        const markets: BinaryMarket[] = [
            {
                market: "m1",
                condition_id: "c1",
                question: "Long Arb",
                volume: 50000,
                yes_bid: 0.47,
                yes_ask: 0.48,
                no_bid: 0.48,
                no_ask: 0.49,
                active: true,
            },
            {
                market: "m2",
                condition_id: "c2",
                question: "Short Arb",
                volume: 50000,
                yes_bid: 0.52,
                yes_ask: 0.53,
                no_bid: 0.50,
                no_ask: 0.51,
                active: true,
            },
            {
                market: "m3",
                condition_id: "c3",
                question: "No Arb",
                volume: 50000,
                yes_bid: 0.49,
                yes_ask: 0.50,
                no_bid: 0.50,
                no_ask: 0.51,
                active: true,
            },
        ];

        const client = new StubPolymarketClient(markets);
        const detector = new ArbitragePureDetector(client as any, 0.005, 10000);

        const opps = await detector.scanMarkets(1000);

        expect(opps.length).toBe(2);
        const types = new Set(opps.map(o => o.type));
        expect(types.has('long')).toBe(true);
        expect(types.has('short')).toBe(true);
        expect(opps[0].profit).toBeGreaterThanOrEqual(opps[1].profit);
        expect(opps[0].market).toBe('m1');
    });
});

describe('ArbitragePureExecutor', () => {
    it('executes long profit math and redeem', async () => {
        const client = new StubPolymarketClient([]);
        const logger = new StubLogger();
        const executor = new ArbitragePureExecutor(client as any, logger as any);

        const arb: Arbitrage = {
            type: 'long',
            market: 'm1',
            condition_id: 'c1',
            profit: 0.03,
            yes_price: 0.48,
            no_price: 0.49,
            timestamp: 0,
            question: 'Long Arb',
        };

        const result = await executor.execute(arb, 10.0);
        expect(result.success).toBe(true);
        expect(Math.abs(result.invested - 10.0)).toBeLessThan(1e-9);
        expect(result.received).toBeGreaterThan(10.0);
        expect(result.profit).toBeGreaterThan(0);
        expect(client.orders.length).toBe(2);
    });

    it('executes short profit math', async () => {
        const client = new StubPolymarketClient([]);
        const logger = new StubLogger();
        const executor = new ArbitragePureExecutor(client as any, logger as any);

        const arb: Arbitrage = {
            type: 'short',
            market: 'm2',
            condition_id: 'c2',
            profit: 0.02,
            yes_price: 0.52,
            no_price: 0.50,
            timestamp: 0,
            question: 'Short Arb',
        };

        const result = await executor.execute(arb, 10.0);
        expect(result.success).toBe(true);
        expect(Math.abs(result.invested - 10.0)).toBeLessThan(1e-9);
        expect(Math.abs(result.received - 10.2)).toBeLessThan(1e-9);
        expect(Math.abs(result.profit - 0.2)).toBeLessThan(1e-9);
        expect(client.orders.length).toBe(2);
    });
});
