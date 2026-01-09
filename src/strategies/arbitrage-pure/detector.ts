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
        const startTime = Date.now();
        
        console.log(`\n🔍 [SCAN START] ${new Date().toISOString()}`);
        console.log(`⏱️ Starting to fetch markets...`);
        
        try {
            // ===== FETCH MARKETS =====
            const fetchStartTime = Date.now();
            
            console.log(`📡 Calling polyClient.getTopMarkets(limit: ${limit})...`);
            
            const markets = await this.polyClient.getTopMarkets(limit);
            
            const fetchTime = Date.now() - fetchStartTime;
            console.log(`✅ FETCH COMPLETE: ${markets.length} markets in ${(fetchTime / 1000).toFixed(2)}s`);
            console.log(`📈 Speed: ${(markets.length / (fetchTime / 1000)).toFixed(1)} markets/sec`);
            
            if (markets.length === 0) {
                console.log(`⚠️ WARNING: No markets returned from API`);
                return [];
            }
            
            // ===== ANALYZE MARKETS =====
            console.log(`\n📊 Starting to analyze ${markets.length} markets...`);
            const analyzeStartTime = Date.now();
            
            let analyzed = 0;
            let arbs = 0;
            let errors = 0;
            
            const opportunities: Arbitrage[] = [];
            
            for (let i = 0; i < markets.length; i++) {
                const market = markets[i];
                
                // Log every 100 markets
                if (i % 100 === 0 && i > 0) {
                    const elapsed = Date.now() - analyzeStartTime;
                    const speed = (i / (elapsed / 1000)).toFixed(1);
                    const remaining = markets.length - i;
                    const eta = ((remaining / (i / (elapsed / 1000))) / 1000).toFixed(0);
                    console.log(
                        `📍 Progress: ${i}/${markets.length} (${(i / markets.length * 100).toFixed(1)}%) - ` +
                        `${speed} markets/sec - ETA: ${eta}s`
                    );
                }
                
                try {
                    const arb = this.analyzeMarket(market);
                    if (arb) {
                        if (arb.profit >= this.minProfitThreshold) {
                            opportunities.push(arb);
                            arbs++;
                        }
                    }
                    analyzed++;
                } catch (error) {
                    errors++;
                    if (errors <= 3) {
                        console.log(`⚠️ Error analyzing market ${i}: ${error}`);
                    }
                }
            }
            
            const analyzeTime = Date.now() - analyzeStartTime;
            console.log(`\n✅ ANALYZE COMPLETE: Analyzed ${analyzed}/${markets.length} in ${(analyzeTime / 1000).toFixed(2)}s`);
            console.log(`📊 Found ${arbs} arbitrage opportunities`);
            console.log(`📈 Speed: ${(markets.length / (analyzeTime / 1000)).toFixed(1)} markets/sec`);
            
            // Sort by profit
            opportunities.sort((a, b) => b.profit - a.profit);
            
            // ===== SUMMARY =====
            const totalTime = Date.now() - startTime;
            console.log(`\n🎯 [SCAN COMPLETE]`);
            console.log(`├─ Total time: ${(totalTime / 1000).toFixed(2)}s`);
            console.log(`├─ Fetch time: ${(fetchTime / 1000).toFixed(2)}s`);
            console.log(`├─ Analyze time: ${(analyzeTime / 1000).toFixed(2)}s`);
            console.log(`├─ Opportunities: ${opportunities.length}`);
            console.log(`├─ Errors: ${errors}`);
            
            if (totalTime > 35000) {
                console.log(`└─ ⚠️ SLOW: ${(totalTime / 1000).toFixed(2)}s (target: 30s)`);
            } else {
                console.log(`└─ ✅ FAST: ${(totalTime / 1000).toFixed(2)}s (target: 30s)`);
            }
            
            return opportunities;
            
        } catch (error) {
            console.log(`\n❌ [SCAN ERROR]`, error);
            return [];
        }
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
