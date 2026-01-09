import { AsyncRateLimiter } from './rate-limiter.js';
import { BinaryMarket } from '../strategies/arbitrage-pure/types.js';
import crypto from 'crypto';

export interface OrderConfig {
    market: string;
    condition_id: string;
    outcome: 'YES' | 'NO';
    side: 'BUY' | 'SELL';
    shares: number;
    expected_price: number;
}

export interface Order {
    order_id: string;
    market: string;
    outcome: 'YES' | 'NO';
    side: 'BUY' | 'SELL';
    filled_price: number;
    shares: number;
}

export class PolymarketClientService {
    public gammaRateLimiter: AsyncRateLimiter;

    constructor(
        private apiKey: string = '',
        private apiSecret: string = '',
        private host: string = 'https://clob.polymarket.com',
        private gammaHost: string = 'https://gamma-api.polymarket.com',
        private paperTrading: boolean = true,
        private mockMode: boolean = true
    ) {
        this.gammaRateLimiter = new AsyncRateLimiter(5, 1.0);
    }

    async getTopMarkets(limit: number = 1000): Promise<BinaryMarket[]> {
        if (this.mockMode) {
            return this.mockMarkets(limit);
        }

        const markets: BinaryMarket[] = [];
        let offset = 0;
        const pageSize = Math.min(500, Math.max(1, limit));

        while (markets.length < limit) {
            const params = new URLSearchParams({
                limit: pageSize.toString(),
                offset: offset.toString(),
                active: 'true'
            });
            const url = `${this.gammaHost}/markets?${params.toString()}`;
            
            await this.gammaRateLimiter.acquire();
            const resp = await fetch(url);
            if (!resp.ok) break;
            
            const payload = await resp.json() as any;
            const items = Array.isArray(payload) ? payload : (payload.markets || []);
            
            if (!items.length) break;

            for (const item of items) {
                const bm = this.parseBinaryMarket(item);
                if (bm) {
                    markets.push(bm);
                    if (markets.length >= limit) break;
                }
            }

            offset += items.length;
            if (items.length < pageSize) break;
        }

        return markets.slice(0, limit);
    }

    async createMarketOrder(cfg: OrderConfig): Promise<Order> {
        if (cfg.shares <= 0) throw new Error("shares must be > 0");
        if (cfg.expected_price <= 0 || cfg.expected_price >= 1) {
            throw new Error("expected_price must be in (0, 1)");
        }

        if (this.paperTrading || this.mockMode) {
            return {
                order_id: `paper-${crypto.randomUUID()}`,
                market: cfg.market,
                outcome: cfg.outcome,
                side: cfg.side,
                filled_price: cfg.expected_price,
                shares: cfg.shares,
            };
        }

        throw new Error("Real trading is not enabled in this repository by default.");
    }

    async redeem(yesShares: number, noShares: number, conditionId: string): Promise<number> {
        if (this.paperTrading || this.mockMode) {
            if (yesShares <= 0 || noShares <= 0) return 0;
            return Math.min(yesShares, noShares);
        }

        throw new Error("On-chain redeem/merge is not enabled in this repository by default.");
    }

    private parseBinaryMarket(m: any): BinaryMarket | null {
        if (!m || typeof m !== 'object') return null;

        const active = m.active !== undefined ? Boolean(m.active) : true;
        if (!active) return null;

        const question = String(m.question || m.title || "");
        const condition_id = String(m.conditionId || m.condition_id || m.id || "");
        const market_id = String(m.id || condition_id);
        
        if (!condition_id || !market_id) return null;

        const volume = m.volume ?? m.volumeUsd ?? m.volume_usd ?? m.volumeUSD ?? 0;
        const volume_f = parseFloat(volume);

        const prices = this.extractYesNoPrices(m);
        if (!prices) return null;

        const [yes_bid, yes_ask, no_bid, no_ask] = prices;
        if (Math.min(yes_bid, yes_ask, no_bid, no_ask) <= 0) return null;

        return {
            market: market_id,
            condition_id: condition_id,
            question: question,
            volume: volume_f,
            yes_bid,
            yes_ask,
            no_bid,
            no_ask,
            active: true,
        };
    }

    private extractYesNoPrices(market: any): [number, number, number, number] | null {
        const outcomes = market.outcomes || market.tokens || market.clobTokens;
        if (!Array.isArray(outcomes)) return null;

        let yes: any = null;
        let no: any = null;

        for (const o of outcomes) {
            const label = String(o.outcome || o.label || o.name || "").trim().toUpperCase();
            if (label === 'YES' || label === 'Y' || label === 'TRUE' || label.includes('YES')) {
                yes = o;
            } else if (label === 'NO' || label === 'N' || label === 'FALSE' || label.includes('NO')) {
                no = o;
            }
        }

        if (!yes || !no) return null;

        const getBidAsk = (x: any): [number, number] | null => {
            const bid = x.bestBid ?? x.best_bid ?? x.bid;
            const ask = x.bestAsk ?? x.best_ask ?? x.ask;
            if (bid === undefined || ask === undefined) return null;
            return [parseFloat(bid), parseFloat(ask)];
        };

        const y = getBidAsk(yes);
        const n = getBidAsk(no);
        if (!y || !n) return null;

        return [y[0], y[1], n[0], n[1]];
    }

    private mockMarkets(limit: number): BinaryMarket[] {
        const out: BinaryMarket[] = [];
        for (let i = 0; i < Math.max(limit, 1200); i++) {
            const question = `Mock Market #${i}`;
            const market_id = `mock-${i}`;
            const condition_id = `cond-${i}`;
            const volume = Math.floor(Math.random() * 99000) + 1000;

            const mid_yes = Math.random() * 0.9 + 0.05;
            let mid_no = 1.0 - mid_yes;
            const ineff = Math.random() * 0.06 - 0.03;
            mid_no = Math.min(0.999, Math.max(0.001, mid_no + ineff));

            const spread = Math.random() * 0.009 + 0.001;
            const yes_bid = Math.max(0.001, Math.min(0.999, mid_yes - spread));
            const yes_ask = Math.max(0.001, Math.min(0.999, mid_yes + spread));
            const no_bid = Math.max(0.001, Math.min(0.999, mid_no - spread));
            const no_ask = Math.max(0.001, Math.min(0.999, mid_no + spread));

            out.push({
                market: market_id,
                condition_id: condition_id,
                question: question,
                volume,
                yes_bid,
                yes_ask,
                no_bid,
                no_ask,
                active: true,
            });
        }
        return out.slice(0, limit);
    }
}
