import { AsyncRateLimiter } from './rate-limiter.js';
import { BinaryMarket } from '../strategies/arbitrage-pure/types.js';
import { ConsoleLogger } from './console-logger.js';
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
    private logger: ConsoleLogger;

    constructor(
        private apiKey: string = '',
        private apiSecret: string = '',
        private host: string = 'https://clob.polymarket.com',
        private gammaHost: string = 'https://gamma-api.polymarket.com',
        private paperTrading: boolean = true,
        private mockMode: boolean = true
    ) {
        this.gammaRateLimiter = new AsyncRateLimiter(5, 1.0);
        this.logger = new ConsoleLogger();
    }

    async getTopMarkets(limit: number = 1000): Promise<BinaryMarket[]> {
        if (this.mockMode) {
            this.logger.logInfo(`Mock mode: Returning ${limit} mock markets`);
            return this.mockMarkets(limit);
        }

        this.logger.logInfo(`Fetching ${limit} markets from Gamma API`);
        
        try {
            return await this.fetchMarketsWithRetry(limit);
        } catch (error) {
            this.logger.logError(`Failed to fetch markets after retries: ${error instanceof Error ? error.message : 'Unknown error'}`);
            return [];
        }
    }

    private async fetchMarketsWithRetry(limit: number, maxRetries: number = 3): Promise<BinaryMarket[]> {
        const markets: BinaryMarket[] = [];
        let offset = 0;
        const pageSize = Math.min(500, Math.max(1, limit));
        let attempt = 0;

        while (markets.length < limit && attempt < maxRetries) {
            try {
                const batch = await this.fetchMarketBatch(offset, pageSize, attempt + 1);
                if (batch.length === 0) {
                    this.logger.logInfo(`No more markets found at offset ${offset}`);
                    break;
                }

                markets.push(...batch);
                offset += batch.length;
                
                this.logger.logInfo(`Fetched ${batch.length} markets (total: ${markets.length}/${limit})`);
                
                if (batch.length < pageSize) {
                    this.logger.logInfo(`Received partial batch, pagination complete`);
                    break;
                }

                attempt = 0; // Reset attempt counter on successful batch
            } catch (error) {
                attempt++;
                if (attempt >= maxRetries) {
                    this.logger.logError(`Max retries reached (${maxRetries}) for offset ${offset}: ${error instanceof Error ? error.message : 'Unknown error'}`);
                    break;
                }
                
                const backoffDelay = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
                this.logger.logError(`Fetch attempt ${attempt} failed, retrying in ${backoffDelay}ms: ${error instanceof Error ? error.message : 'Unknown error'}`);
                await this.sleep(backoffDelay);
            }
        }

        return markets.slice(0, limit);
    }

    private async fetchMarketBatch(offset: number, pageSize: number, attempt: number): Promise<BinaryMarket[]> {
        const params = new URLSearchParams({
            limit: pageSize.toString(),
            offset: offset.toString(),
            active: 'true'
        });
        const url = `${this.gammaHost}/markets?${params.toString()}`;
        
        this.logger.logInfo(`Fetching markets batch (attempt ${attempt}): ${url}`);
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000); // 15 second timeout
        
        const startTime = Date.now();
        let response: Response;
        let responseText: string;
        
        try {
            // Add headers including User-Agent and authentication if available
            const headers: Record<string, string> = {
                'User-Agent': 'PolymarketClient/1.0',
                'Accept': 'application/json',
            };
            
            if (this.apiKey) {
                headers['Authorization'] = `Bearer ${this.apiKey}`;
            }
            
            this.logger.logInfo(`Request headers: ${JSON.stringify(headers, null, 2)}`);

            response = await fetch(url, {
                method: 'GET',
                headers,
                signal: controller.signal
            });

            const duration = Date.now() - startTime;
            clearTimeout(timeoutId);
            
            this.logger.logInfo(`Response status: ${response.status} ${response.statusText}, took ${duration}ms`);
            
            if (!response.ok) {
                responseText = await response.text();
                this.logger.logError(`HTTP error ${response.status}: ${responseText.substring(0, 500)}`);
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            responseText = await response.text();
            this.logger.logInfo(`Response body (${responseText.length} chars): ${responseText.substring(0, 500)}${responseText.length > 500 ? '...' : ''}`);
            
            let payload: any;
            try {
                payload = JSON.parse(responseText);
            } catch (parseError) {
                this.logger.logError(`Failed to parse JSON response: ${parseError}`);
                throw new Error(`Invalid JSON response: ${parseError}`);
            }

            const items = Array.isArray(payload) ? payload : (payload.markets || []);
            this.logger.logInfo(`Parsed ${items.length} items from response`);
            
            const markets: BinaryMarket[] = [];
            
            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                try {
                    const bm = this.parseBinaryMarket(item);
                    if (bm) {
                        markets.push(bm);
                    } else {
                        this.logger.logInfo(`Skipped invalid market at index ${i}: ${JSON.stringify(item).substring(0, 100)}...`);
                    }
                } catch (parseError) {
                    this.logger.logError(`Error parsing market at index ${i}: ${parseError}`);
                }
            }
            
            this.logger.logInfo(`Successfully parsed ${markets.length} valid markets from ${items.length} items`);
            return markets;

        } catch (error) {
            clearTimeout(timeoutId);
            
            if (error instanceof Error && error.name === 'AbortError') {
                this.logger.logError(`Request timed out after 15 seconds for URL: ${url}`);
                throw new Error('Request timeout');
            }
            
            this.logger.logError(`Network error fetching markets: ${error instanceof Error ? error.message : 'Unknown error'}`);
            throw error;
        }
    }

    private sleep(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
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
