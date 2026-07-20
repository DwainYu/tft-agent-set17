// Backend Direction type
export type Direction = '推荐阵容' | '推荐装备' | '查专属' | '检索装备';

// SSE stages from backend
export type SSEStage =
  | 'understanding'
  | 'tool_selection'
  | 'tool_execution'
  | 'tool_done'
  | 'composing'
  | 'result';

// SSE event from backend: {stage, content?, data?}
export interface SSEEvent {
  stage: SSEStage;
  content?: string;
  data?: ResultData;
}

// The "result" stage data field
export interface ResultData {
  card: CompCard | Record<string, unknown> | null;
  summary: string;
  results: Record<string, unknown>[];
}

// Ask request body
export interface AskRequest {
  question: string;
  direction?: Direction;
  conversation_id?: string;
}

// CompCard from backend comp_query
export interface CompCard {
  comp_name: string;
  avg_placement: number | null;
  sample_size: number | null;
  champions: ChampionInfo[];
  synergies: string[];
  emblems: ItemDelta[];
  artifacts: ItemDelta[];
  flex_slot: FlexSlotData | null;
}

export interface ChampionInfo {
  id: string;
  name_zh: string;
  name_en: string | null;
  cost: number;
  icon: string | null;
  icon_path: string | null;
  role: string | null;
}

export interface ItemDelta {
  item_id?: string;
  name_zh: string;
  name_en?: string;
  target?: string;
  delta: number;
}

export interface FlexSlotData {
  population: number;
  champion: string;
}

// Auth types
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserInfo {
  id: number;
  phone: string;
  created_at: string | null;
}

// Conversation types
export interface Conversation {
  id: number;
  title: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface Message {
  id: number;
  conversation_id: number;
  role: string;
  content: string;
  created_at: string | null;
}

// Chat message for UI
export interface ChatMsg {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  card?: CompCard | Record<string, unknown> | null;
  results?: Record<string, unknown>[];
  reasoning?: Partial<Record<SSEStage, string>>;
  timestamp: number;
}
