import * as dotenv from 'dotenv';
import * as os from 'os';

export interface BotConfigData {
    polymarket_api_key: string;
    polymarket_api_secret: string;
    polymarket_host: string;
    gamma_host: string;
    starting_capital: number;
    position_size: number;
    min_profit_threshold: number;
    min_market_volume: number;
    market_scan_limit: number;
    scan_interval_ms: number;
    execution_delay_ms: number;
    paper_trading: boolean;
    mock_mode: boolean;
    log_level: string;
    gamma_rps: number;
}

export class BotConfig implements BotConfigData {
    polymarket_api_key!: string;
    polymarket_api_secret!: string;
    polymarket_host!: string;
    gamma_host!: string;
    starting_capital!: number;
    position_size!: number;
    min_profit_threshold!: number;
    min_market_volume!: number;
    market_scan_limit!: number;
    scan_interval_ms!: number;
    execution_delay_ms!: number;
    paper_trading!: boolean;
    mock_mode!: boolean;
    log_level!: string;
    gamma_rps!: number;

    constructor(data: BotConfigData) {
        Object.assign(this, data);
    }

    static load(): BotConfig {
        dotenv.config();

        const getEnvBool = (name: string, defaultValue: boolean): boolean => {
            const val = process.env[name];
            if (val === undefined) return defaultValue;
            return ["1", "true", "yes", "y", "on"].includes(val.toLowerCase());
        };

        const getEnvFloat = (name: string, defaultValue: number): number => {
            const val = process.env[name];
            if (val === undefined || val === "") return defaultValue;
            return parseFloat(val);
        };

        const getEnvInt = (name: string, defaultValue: number): number => {
            const val = process.env[name];
            if (val === undefined || val === "") return defaultValue;
            return parseInt(val, 10);
        };

        return new BotConfig({
            polymarket_api_key: process.env.POLYMARKET_API_KEY || "",
            polymarket_api_secret: process.env.POLYMARKET_API_SECRET || "",
            polymarket_host: process.env.POLYMARKET_HOST || "https://clob.polymarket.com",
            gamma_host: process.env.GAMMA_HOST || "https://gamma-api.polymarket.com",
            starting_capital: getEnvFloat("STARTING_CAPITAL", getEnvFloat("CAPITAL", 100.0)),
            position_size: getEnvFloat("POSITION_SIZE", 10.0),
            min_profit_threshold: getEnvFloat("MIN_PROFIT_THRESHOLD", 0.005),
            min_market_volume: getEnvFloat("MIN_MARKET_VOLUME", 10000.0),
            market_scan_limit: getEnvInt("MARKET_SCAN_LIMIT", 1000),
            scan_interval_ms: getEnvInt("SCAN_INTERVAL", 30000),
            execution_delay_ms: getEnvInt("EXECUTION_DELAY", 1000),
            paper_trading: getEnvBool("PAPER_TRADING", true),
            mock_mode: getEnvBool("MOCK_MODE", true),
            log_level: process.env.LOG_LEVEL || "info",
            gamma_rps: getEnvInt("GAMMA_RPS", 5),
        });
    }

    validate(): void {
        if (this.starting_capital <= 0) throw new Error("STARTING_CAPITAL must be > 0");
        if (this.position_size <= 0) throw new Error("POSITION_SIZE must be > 0");
        if (this.min_profit_threshold <= 0) throw new Error("MIN_PROFIT_THRESHOLD must be > 0");
        if (this.scan_interval_ms <= 0) throw new Error("SCAN_INTERVAL must be > 0");
        if (this.execution_delay_ms < 0) throw new Error("EXECUTION_DELAY must be >= 0");
        if (this.market_scan_limit <= 0) throw new Error("MARKET_SCAN_LIMIT must be > 0");
    }
}
