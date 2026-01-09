import { PolymarketClientService } from '../../core/polymarket-client.js';
import { Arbitrage, ExecutionResult } from './types.js';

export interface Logger {
    logError(message: string): void;
    logInfo(message: string): void;
}

export class ArbitragePureExecutor {
    constructor(
        private polyClient: PolymarketClientService,
        private logger: Logger
    ) {}

    async execute(arb: Arbitrage, amount: number = 10.0): Promise<ExecutionResult> {
        const started = performance.now();

        try {
            if (amount <= 0) {
                throw new Error("amount must be > 0");
            }

            const sumPrice = arb.yes_price + arb.no_price;
            if (sumPrice <= 0) {
                throw new Error("invalid prices");
            }

            let invested: number;
            let received: number;
            let profit: number;

            if (arb.type === 'long') {
                const shares = amount / sumPrice;

                const yesCfg = {
                    market: arb.market,
                    condition_id: arb.condition_id,
                    outcome: 'YES' as const,
                    side: 'BUY' as const,
                    shares: shares,
                    expected_price: arb.yes_price,
                };
                const noCfg = {
                    market: arb.market,
                    condition_id: arb.condition_id,
                    outcome: 'NO' as const,
                    side: 'BUY' as const,
                    shares: shares,
                    expected_price: arb.no_price,
                };

                const [yesOrder, noOrder] = await Promise.all([
                    this.polyClient.createMarketOrder(yesCfg),
                    this.polyClient.createMarketOrder(noCfg),
                ]);

                invested = amount;
                
                // Merge/redeem complete sets
                received = await this.polyClient.redeem(yesOrder.shares, noOrder.shares, arb.condition_id);
                profit = received - invested;

            } else {
                const shares = amount;

                const yesCfg = {
                    market: arb.market,
                    condition_id: arb.condition_id,
                    outcome: 'YES' as const,
                    side: 'SELL' as const,
                    shares: shares,
                    expected_price: arb.yes_price,
                };
                const noCfg = {
                    market: arb.market,
                    condition_id: arb.condition_id,
                    outcome: 'NO' as const,
                    side: 'SELL' as const,
                    shares: shares,
                    expected_price: arb.no_price,
                };

                const [yesOrder, noOrder] = await Promise.all([
                    this.polyClient.createMarketOrder(yesCfg),
                    this.polyClient.createMarketOrder(noCfg),
                ]);

                invested = amount;
                received = yesOrder.shares * yesOrder.filled_price + noOrder.shares * noOrder.filled_price;

                await this.polyClient.redeem(0, 0, arb.condition_id);
                profit = received - invested;
            }

            const elapsed = (performance.now() - started) / 1000;
            this.logger.logInfo(
                `EXECUTED arb type=${arb.type} market=${arb.market} profit=$${profit.toFixed(4)} time=${elapsed.toFixed(2)}s`
            );

            return {
                market: arb.market,
                type: arb.type,
                invested,
                received,
                profit,
                success: true,
            };

        } catch (e: any) {
            const elapsed = (performance.now() - started) / 1000;
            this.logger.logError(`Arbitrage execution failed: ${e.message} (${elapsed.toFixed(2)}s)`);
            return {
                market: arb.market,
                type: arb.type,
                invested: amount,
                received: 0,
                profit: 0,
                success: false,
                error: e.message,
            };
        }
    }
}
