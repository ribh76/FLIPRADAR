export type Condition = "new" | "used" | "sealed" | "unknown";
export type UserGoal = "buy_vs_pass" | "hold_vs_sell" | "buy" | "sell" | "hold";
export type Verdict = "BUY" | "PASS" | "SELL" | "HOLD" | "WATCH";

export type PaginationMeta = {
  limit: number;
  offset: number;
  count: number;
  has_more: boolean;
};

export type CollectionResponse<T> = {
  data: T[];
  pagination: PaginationMeta;
};

export type AuthSession = {
  access_token: string;
  refresh_token: string;
  token_type?: string;
  user?: CurrentUser;
};

export type ApiMessage = {
  message: string;
};

export type AnalyzeRequest = {
  set_number: string;
  user_goal: UserGoal;
  condition: Condition;
  asking_price: number | null;
  manual_valuation_override?: ManualValuationOverride | null;
};

export type ManualValuationOverride = {
  expected_value: number;
  low_value?: number | null;
  high_value?: number | null;
  reason: string;
};

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
  valuation_source: "market" | "manual_override" | string;
};

export type PortfolioItem = {
  id: string;
  user_id?: string;
  set_number: string;
  quantity: number;
  purchase_price: string | number;
  condition: string;
  purchase_date: string | null;
  currency: string;
  notes: string | null;
  created_at?: string;
  updated_at?: string;
  set_name: string | null;
  theme: string | null;
  current_unit_value: string | number | null;
  current_total_value: string | number | null;
  cost_basis: string | number;
  unrealized_gain_loss: string | number | null;
  unrealized_gain_loss_percent: string | number | null;
  valuation_status: string;
  valuation_confidence: string | null;
};

export type PortfolioItemCreate = {
  set_number: string;
  quantity: number;
  purchase_price: number;
  condition: Condition;
  purchase_date: string | null;
  currency: string;
  notes: string | null;
};

export type PortfolioItemUpdate = Partial<PortfolioItemCreate>;

export type PortfolioFilters = {
  condition?: Condition | "";
  theme?: string;
  year?: number | "";
  performance?: "gain" | "loss" | "unvalued" | "";
  order?: string;
  limit?: number;
  offset?: number;
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

export type PortfolioHistoryPoint = {
  timestamp: string;
  cost_basis: string | number;
  market_value: string | number;
  gain_loss: string | number;
  currency: string;
};

export type PortfolioHistory = {
  range: "1d" | "1w" | "1m" | "3m" | "180d" | "1y" | "all";
  points: PortfolioHistoryPoint[];
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
  valuation_error?: string | null;
  latest_snapshot: {
    condition: string;
    currency: string;
    metric_type: string;
    value: string | number;
    sample_size: number;
    source_payload: Record<string, unknown> | null;
    retrieval_time: string;
  } | null;
};

export type LegoSet = {
  id: string;
  set_number: string;
  name: string;
  theme: string | null;
  subtheme: string | null;
  release_year: number | null;
  retirement_year: number | null;
  piece_count: number | null;
  minifig_count: number | null;
  msrp: string | number | null;
  original_currency: string | null;
  region: string | null;
  image_urls: string[] | null;
  source_name: string | null;
  source_url: string | null;
  data_quality_flag: boolean;
  completeness_flag: boolean;
  created_at: string;
  updated_at: string;
};

export type CatalogSearchResponse = {
  query: string;
  provider: string | null;
  source: "local" | "provider";
  exact_match: boolean;
  results: LegoSet[];
};

export type CurrentUser = {
  id: string;
  username: string;
  display_name: string | null;
  email: string;
  pending_email: string | null;
  is_email_verified: boolean;
  deletion_requested_at: string | null;
  deletion_scheduled_at: string | null;
  created_at: string;
  updated_at: string;
};

export type RefreshSession = {
  id: string;
  created_at: string;
  last_seen_at: string | null;
  expires_at: string;
};
