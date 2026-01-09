export type ArbitrageType = 'long' | 'short';

export interface BinaryMarket {
    market: string;
    condition_id: string;
    question: string;
    volume: number;
    yes_bid: number;
    yes_ask: number;
    no_bid: number;
    no_ask: number;
    active: boolean;
}

export interface Arbitrage {
    type: ArbitrageType;
    market: string;
    condition_id: string;
    profit: number;
    yes_price: number;
    no_price: number;
    timestamp: number;
    question: string;
}

export interface ExecutionResult {
    market: string;
    type: ArbitrageType;
    invested: number;
    received: number;
    profit: number;
    success: boolean;
    error?: string;
}

export interface TradeLog {
    timestamp: Date;
    market: string;
    type: ArbitrageType;
    profit: number;
    balance: number;
    operation_time: number;
}
