export type Condition = "new" | "used" | "sealed" | "unknown";
export type UserGoal = "buy_vs_pass" | "hold_vs_sell" | "buy" | "sell" | "hold";
export type Verdict = "BUY" | "PASS" | "SELL" | "HOLD" | "WATCH";

export type AnalyzeResponse = {
  set_number: string;
  user_goal: UserGoal;
  asking_price: number | null;
  fair_value: number;
  score: number;
  recommendation: Verdict;
  confidence: "low" | "medium" | "high";
  reasoning: string;
  market_low: number | null;
  market_high: number | null;
  listing_count: number | null;
};

export type PortfolioItem = {
  id: string;
  set_number: string;
  quantity: number;
  purchase_price: string | number;
  condition: string;
  acquired_at: string | null;
  notes: string | null;
  set_name: string | null;
  current_unit_value: string | number | null;
  current_total_value: string | number | null;
  cost_basis: string | number;
  unrealized_gain_loss: string | number | null;
  valuation_status: string;
};

export type PortfolioSummary = {
  total_items: number;
  total_sets: number;
  total_quantity: number;
  total_cost_basis: string | number;
  estimated_current_value: string | number;
  unrealized_gain_loss: string | number;
  unrealized_gain_loss_percent: string | number | null;
};

export type SetDetail = {
  set_number: string;
  name: string;
  theme: string | null;
  subtheme: string | null;
  release_year: number | null;
  retirement_year: number | null;
  piece_count: number | null;
  minifig_count: number | null;
  fair_value: string | number | null;
  market_low: string | number | null;
  market_high: string | number | null;
  listing_count: number;
  confidence: string | null;
  valuation_status: "available" | "missing_market_data" | string;
  latest_snapshot: {
    condition: string;
    currency: string;
    low_price: string | number | null;
    median_price: string | number | null;
    average_price: string | number | null;
    high_price: string | number | null;
    fair_market_value: string | number | null;
    listing_count: number;
    snapshot_at: string;
  } | null;
};

export type CurrentUser = {
  id: string;
  username: string;
  display_name: string | null;
  email: string;
  pending_email: string | null;
  is_email_verified: boolean;
  created_at: string;
  updated_at: string;
};
