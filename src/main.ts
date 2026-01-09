import { BotConfig } from './config/bot-config.js';
import { PolymarketClientService } from './core/polymarket-client.js';
import { ArbitrageBotService } from './services/arbitrage-bot.js';
import { ConsoleLogger } from './core/console-logger.js';

async function main() {
    const config = BotConfig.load();
    try {
        config.validate();
    } catch (e: any) {
        console.error(`Config validation failed: ${e.message}`);
        process.exit(1);
    }

    const logger = new ConsoleLogger();
    const polyClient = new PolymarketClientService(
        config.polymarket_api_key,
        config.polymarket_api_secret,
        config.polymarket_host,
        config.gamma_host,
        config.paper_trading,
        config.mock_mode
    );

    const bot = new ArbitrageBotService(polyClient, config, logger);

    const shutdown = () => {
        bot.stop();
        setTimeout(() => process.exit(0), 1000);
    };

    process.on('SIGINT', shutdown);
    process.on('SIGTERM', shutdown);

    await bot.start();
}

main().catch((e) => {
    console.error(`Fatal error: ${e.message}`);
    process.exit(1);
});
