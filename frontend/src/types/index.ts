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

export type DealMarketplaceDetails = {
  name: string;
  display_name: string;
  base_url: string | null;
  seller_name: string | null;
  seller_rating: string | number | null;
};

export type Deal = {
  listing_id: string;
  set_number: string;
  set_name: string;
  marketplace: DealMarketplaceDetails;
  title: string;
  url: string;
  condition: string;
  is_sealed: boolean | null;
  asking_price: string | number;
  shipping_price: string | number;
  total_cost: string | number;
  currency: string;
  fair_value: string | number;
  value: string | number;
  valuation_sample_size: number;
  score: number;
  deal_band: string;
  confidence_score: number;
  confidence: number;
  discount_percent: string | number;
  discount: string | number;
  last_seen_at: string;
  explanation: string;
};

export type DealRefreshStatus = {
  requested: boolean;
  cached: boolean;
  throttled: boolean;
  retry_after_seconds: number | null;
  provider_errors: string[];
};

export type DealsResponse = CollectionResponse<Deal> & {
  refresh: DealRefreshStatus;
};

export type DealFilters = {
  min_budget?: number;
  max_budget?: number;
  theme?: string;
  subtheme?: string;
  min_release_year?: number;
  max_release_year?: number;
  min_age_years?: number;
  max_age_years?: number;
  condition?: string;
  retirement_status?: string;
  marketplace?: string;
  min_discount?: number;
  min_confidence?: number;
  max_shipping?: number;
  order?: string;
  limit?: number;
  offset?: number;
  refresh?: boolean;
};

export type SavedSearch = {
  id: string;
  name: string;
  filter_config: DealFilters;
  filter_version: number;
  last_run_at: string | null;
  result_count: number;
  created_at: string;
  updated_at: string;
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
  ai_narrative?: LlmRecommendationNarrative | null;
  ai_narrative_status?:
    | "available"
    | "disabled"
    | "rate_limited"
    | "timed_out"
    | "failed"
    | "invalid_response";
};

export type LlmFactCard = {
  source_metric: string;
  text: string;
};

export type LlmUncertaintyCard = {
  code: string;
  text: string;
};

export type LlmRecommendationNarrative = {
  summary: string;
  facts: LlmFactCard[];
  uncertainties: LlmUncertaintyCard[];
  prompt_version: string;
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

export type Listing = {
  id: string;
  lego_set_id: string;
  marketplace_id: string;
  external_listing_id: string;
  title: string;
  url: string;
  price: string | number;
  shipping_price: string | number;
  total_price: string | number;
  currency: string;
  condition: Condition;
  listing_status: string;
  seller_name: string | null;
  seller_rating: string | number | null;
  is_complete: boolean | null;
  is_sealed: boolean | null;
  is_verified: boolean;
};

export type WatchlistItem = {
  id: string;
  user_id: string;
  entry_type: "set" | "listing";
  set_number: string;
  listing_id: string | null;
  target_price: string | number | null;
  notes: string | null;
  saved_at: string;
  last_known_listing_price: string | number | null;
  last_known_listing_status: "active" | "sold" | "ended" | "removed" | null;
  current_price: string | number | null;
  valuation: string | number | null;
  discount_percent: string | number | null;
  deal_score: string | number | null;
  price_change: string | number | null;
  is_under_target: boolean;
  recommendation: "BUY" | "WATCH" | "PASS";
  last_checked_at: string | null;
};

export type WatchlistHistoryPoint = {
  observed_at: string;
  listing_price: string | number | null;
  fair_value: string | number | null;
  deal_score: string | number | null;
  listing_status: string | null;
};

export type WatchlistReplacement = {
  listing_id: string;
  title: string;
  url: string;
  total_price: string | number;
  currency: string;
  fair_value: string | number | null;
  deal_score: string | number | null;
  recommendation: "BUY" | "WATCH" | "PASS";
};

export type NotificationType =
  "price_drop" | "target_reached" | "ended_listing" | "deal_score";

export type AppNotification = {
  id: string;
  notification_type: NotificationType;
  watchlist_item_id: string | null;
  title: string;
  message: string;
  action_url: string;
  payload: Record<string, unknown>;
  is_read: boolean;
  created_at: string;
  read_at: string | null;
};

export type NotificationPreference = {
  notification_type: NotificationType;
  in_app_enabled: boolean;
  email_enabled: boolean;
};

export type NotificationSettings = {
  email_enabled: boolean;
  timezone: string;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
};

export type ListingAnalysis = {
  id: string;
  listing_id: string;
  fair_value: string | number | null;
  fair_value_low: string | number | null;
  fair_value_high: string | number | null;
  total_cost: string | number;
  discount_percent: string | number | null;
  premium_percent: string | number | null;
  product_match_confidence: string | number;
  decision: "buy" | "watch" | "pass" | "insufficient_data";
  decision_confidence: string | number;
  reasons: string[];
  risk_flags: string[];
  score_breakdown: Record<string, unknown>;
  valuation_sample_size: number;
  valuation_retrieved_at: string | null;
  created_at: string;
};

export type ManualListingEntry = {
  title: string;
  price: number;
  shipping_price: number;
  currency: string;
  condition: Condition;
  listing_status?: string;
};

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

export type PortfolioDashboard = {
  portfolio: CollectionResponse<PortfolioItem>;
  summary: PortfolioSummary;
  history: PortfolioHistory | null;
  history_unavailable: string | null;
};

export type HoldingMarketSnapshot = {
  timestamp: string;
  marketplace: string;
  condition: string;
  metric_type: string;
  value: string | number;
  sample_size: number;
  currency: string;
};

export type HoldingConditionPrice = {
  condition: string;
  estimated_unit_value: string | number | null;
  confidence: string | null;
  latest_snapshot_at: string | null;
};

export type PortfolioHoldingDetail = {
  holding: PortfolioItem;
  portfolio_total_value: string | number;
  portfolio_share_percent: string | number | null;
  concentration_risk: {
    level: "low" | "moderate" | "high" | string;
    message: string;
    portfolio_share_percent: string | number | null;
    value_rank: number | null;
  };
  market_freshness_at: string | null;
  market_snapshots: HoldingMarketSnapshot[];
  condition_pricing: HoldingConditionPrice[];
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
