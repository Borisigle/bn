export class ConsoleLogger {
    logInfo(message: string): void {
        console.log(`[INFO] ${new Date().toISOString()} - ${message}`);
    }

    logError(message: string): void {
        console.error(`[ERROR] ${new Date().toISOString()} - ${message}`);
    }

    logPriceUpdate(btcPrice: number, pctChange: number): void {
        this.logInfo(`BTC Price: $${btcPrice.toFixed(2)} (${pctChange > 0 ? '+' : ''}${pctChange.toFixed(2)}%)`);
    }

    logMarket(marketId: string, secondsToForcedClose: number, status: string): void {
        this.logInfo(`Market: ${marketId} | Time remaining: ${secondsToForcedClose}s | Status: ${status}`);
    }

    logCapital(capital: number, openPositions: number): void {
        this.logInfo(`Capital: $${capital.toFixed(2)} | Open positions: ${openPositions}`);
    }
}
