import { BotConfig } from '../config/bot-config.js';
import { PolymarketClientService } from '../core/polymarket-client.js';
import { ArbitragePureDetector, ArbitragePureExecutor, TradeLog } from '../strategies/arbitrage-pure/index.js';

export interface Logger {
    logError(message: string): void;
    logInfo(message: string): void;
}

export class ArbitrageBotService {
    private detector: ArbitragePureDetector;
    private executor: ArbitragePureExecutor;
    private _running: boolean = false;
    private _balance: number = 0.0;
    private _tradeLogs: TradeLog[] = [];
    private _stopPromise: ((value: void) => void) | null = null;

    constructor(
        private polyClient: PolymarketClientService,
        private config: BotConfig,
        private logger: Logger
    ) {
        this.detector = new ArbitragePureDetector(
            this.polyClient,
            this.config.min_profit_threshold,
            this.config.min_market_volume
        );
        this.executor = new ArbitragePureExecutor(this.polyClient, this.logger);
        this._balance = this.config.starting_capital;
    }

    async start(): Promise<void> {
        this._running = true;

        this.logger.logInfo(
            `Starting pure arbitrage bot | balance=$${this._balance.toFixed(2)} paper=${this.config.paper_trading} mock=${this.config.mock_mode}`
        );

        while (this._running) {
            const started = Date.now();
            try {
                await this.scanLoop();
            } catch (e: any) {
                this.logger.logError(`scanLoop error: ${e.message}`);
            }
            const elapsed = Date.now() - started;
            const sleepFor = Math.max(0, this.config.scan_interval_ms - elapsed);

            if (sleepFor > 0 && this._running) {
                await new Promise<void>((resolve) => {
                    const timeout = setTimeout(resolve, sleepFor);
                    this._stopPromise = () => {
                        clearTimeout(timeout);
                        resolve();
                    };
                });
            }
        }
    }

    async scanLoop(): Promise<void> {
        if (!this._running) return;

        const minAmount = this.positionAmount();
        if (this._balance < minAmount || minAmount <= 0) {
            this.logger.logInfo(
                `Balance too low to trade | balance=$${this._balance.toFixed(2)} position_size=$${this.config.position_size.toFixed(2)}`
            );
            return;
        }

        const scanLimit = this.config.market_scan_limit;
        this.logger.logInfo(`🔍 Scanning ${scanLimit} markets...`);

        const opportunities = await this.detector.scanMarkets(scanLimit);
        this.logger.logInfo(`🎯 Found ${opportunities.length} opportunities`);

        for (const arb of opportunities) {
            if (!this._running) break;

            const amount = this.positionAmount();
            if (amount <= 0) break;

            this.logger.logInfo(
                `⚡ Executing: ${arb.question || arb.market} (${(arb.profit * 100).toFixed(2)}% expected profit)`
            );

            const opStarted = Date.now();
            const result = await this.executor.execute(arb, amount);
            const opTime = (Date.now() - opStarted) / 1000;

            if (result.success) {
                this.updateBalance(result.profit);
                this._tradeLogs.push({
                    timestamp: new Date(),
                    market: result.market,
                    type: result.type,
                    profit: result.profit,
                    balance: this._balance,
                    operation_time: opTime,
                });
                this.logger.logInfo(
                    `✅ COMPLETED: +$${result.profit.toFixed(2)} profit | Balance: $${this._balance.toFixed(2)}`
                );
            } else {
                this.logger.logError(`❌ FAILED: ${result.error}`);
            }

            if (this.config.execution_delay_ms > 0) {
                await new Promise((resolve) => setTimeout(resolve, this.config.execution_delay_ms));
            }
        }
    }

    stop(): void {
        this._running = false;
        if (this._stopPromise) {
            this._stopPromise();
        }
        this.logger.logInfo("Stopping bot...");
    }

    getBalance(): number {
        return this._balance;
    }

    getTradeLogs(): TradeLog[] {
        return [...this._tradeLogs];
    }

    private positionAmount(): number {
        if (this._balance <= 0) return 0;
        let size = this.config.position_size;
        if (size > 0 && size <= 1) {
            size = this._balance * size;
        }
        return Math.min(size, this._balance);
    }

    private updateBalance(profit: number): void {
        this._balance += profit;
    }
}
