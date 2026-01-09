import { PolymarketClientService } from '../../core/polymarket-client.js';
import { Arbitrage, BinaryMarket } from './types.js';

export class ArbitragePureDetector {
    constructor(
        private polyClient: PolymarketClientService,
        private minProfitThreshold: number = 0.005,
        private minMarketVolume: number = 10000.0,
        private longSumThreshold: number = 0.99,
        private shortSumThreshold: number = 1.01
    ) {}

    async scanMarkets(limit: number = 1000): Promise<Arbitrage[]> {
        const markets = await this.polyClient.getTopMarkets(limit);

        const opportunities: Arbitrage[] = [];
        for (const m of markets) {
            const arb = this.analyzeMarket(m);
            if (!arb) continue;
            if (arb.profit < this.minProfitThreshold) continue;
            opportunities.push(arb);
        }

        opportunities.sort((a, b) => b.profit - a.profit);
        return opportunities;
    }

    analyzeMarket(market: BinaryMarket): Arbitrage | null {
        if (!market.active) return null;
        if (market.volume < this.minMarketVolume) return null;

        if (Math.min(market.yes_bid, market.yes_ask, market.no_bid, market.no_ask) <= 0) {
            return null;
        }

        if (market.yes_ask < market.yes_bid || market.no_ask < market.no_bid) {
            return null;
        }

        const longSum = market.yes_ask + market.no_ask;
        const shortSum = market.yes_bid + market.no_bid;

        let best: Arbitrage | null = null;

        if (longSum < this.longSumThreshold) {
            const profit = Math.max(0.0, 1.0 - longSum);
            best = {
                type: 'long',
                market: market.market,
                condition_id: market.condition_id,
                profit: profit,
                yes_price: market.yes_ask,
                no_price: market.no_ask,
                timestamp: Date.now() / 1000,
                question: market.question,
            };
        }

        if (shortSum > this.shortSumThreshold) {
            const profit = Math.max(0.0, shortSum - 1.0);
            const cand: Arbitrage = {
                type: 'short',
                market: market.market,
                condition_id: market.condition_id,
                profit: profit,
                yes_price: market.yes_bid,
                no_price: market.no_bid,
                timestamp: Date.now() / 1000,
                question: market.question,
            };
            if (!best || cand.profit > best.profit) {
                best = cand;
            }
        }

        return best;
    }
}
