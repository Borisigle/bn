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
    private cycleCount: number = 0;

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
        
        const cycleStartTime = Date.now();
        this.cycleCount++;
        
        console.log(`\n${'='.repeat(70)}`);
        console.log(`📍 CYCLE #${this.cycleCount} | ${new Date().toISOString()}`);
        console.log(`${'='.repeat(70)}`);

        try {
            // SCAN
            const scanStartTime = Date.now();
            console.log(`⏳ Starting scan...`);

            const scanLimit = this.config.market_scan_limit;
            const opportunities = await this.detector.scanMarkets(scanLimit);
            
            const scanTime = Date.now() - scanStartTime;
            console.log(`\n✅ Scan finished in ${(scanTime / 1000).toFixed(2)}s`);
            console.log(`🎯 Found ${opportunities.length} opportunities`);

            if (opportunities.length === 0) {
                console.log(`⏸️ No opportunities. Waiting for next cycle...\n`);
                return;
            }

            // EXECUTE
            console.log(`\n⚡ Executing ${opportunities.length} opportunities...`);
            
            let executedCount = 0;
            let totalProfit = 0;
            
            for (const arb of opportunities.slice(0, 5)) {
                if (!this._running) break;

                const amount = this.positionAmount();
                if (amount <= 0) {
                    console.log(`⚠️ Balance too low to continue executing.`);
                    break;
                }

                console.log(`\n  ⚡ [${executedCount + 1}/${Math.min(5, opportunities.length)}] ${arb.question || arb.market}`);
                
                const execStartTime = Date.now();
                const result = await this.executor.execute(arb, amount);
                const execTime = Date.now() - execStartTime;

                if (result.success) {
                    executedCount++;
                    totalProfit += result.profit;
                    this.updateBalance(result.profit);
                    
                    this._tradeLogs.push({
                        timestamp: new Date(),
                        market: result.market,
                        type: result.type,
                        profit: result.profit,
                        balance: this._balance,
                        operation_time: execTime / 1000,
                    });
                    
                    console.log(`  ✅ +$${result.profit.toFixed(2)} (${(execTime / 1000).toFixed(2)}s) | Balance: $${this._balance.toFixed(2)}`);
                } else {
                    console.log(`  ❌ Failed: ${result.error}`);
                }

                if (this.config.execution_delay_ms > 0) {
                    await new Promise((resolve) => setTimeout(resolve, this.config.execution_delay_ms));
                }
            }
            
            // SUMMARY
            const cycleTime = Date.now() - cycleStartTime;
            console.log(`\n${'='.repeat(70)}`);
            console.log(`📊 CYCLE #${this.cycleCount} SUMMARY`);
            console.log(`├─ Total time: ${(cycleTime / 1000).toFixed(2)}s`);
            console.log(`├─ Opportunities: ${opportunities.length}`);
            console.log(`├─ Executed: ${executedCount}`);
            console.log(`├─ Profit: +$${totalProfit.toFixed(2)}`);
            console.log(`├─ Balance: $${this._balance.toFixed(2)}`);
            console.log(`└─ Next cycle in 30 seconds...`);
            console.log(`${'='.repeat(70)}\n`);

        } catch (error) {
            console.log(`\n❌ Cycle error:`, error);
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
