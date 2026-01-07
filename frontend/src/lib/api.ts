/**
 * API client for HashScope backend
 */

export interface CapturedMessage {
  id: string;
  ts_recv: string;
  ts_fwd: string | null;
  direction: 'miner_to_pool' | 'pool_to_miner';
  session_id: string;
  peer: string;
  raw: string;
  decoded: Record<string, any> | null;
  parse_error: string | null;
  size_bytes: number;
  jsonrpc_id?: number | string | null;
  is_request?: boolean;
  is_response?: boolean;
  paired_message_id?: string | null;
  response?: Record<string, any> | null;
  response_ts_recv?: string | null;
  response_raw?: string | null;
}

export interface Session {
  session_id: string;
  peer: string;
  first_seen: string;
  last_seen: string;
  message_count: number;
  user_agent?: string | null;
  mining_session_id?: string | null;
  difficulty?: number | null;
  stats?: {
    total_messages: number;
    miner_to_pool: number;
    pool_to_miner: number;
    parse_errors: number;
  };
}

const API_BASE = '/api';

export class HashScopeAPI {
  async getSessions(): Promise<Session[]> {
    const response = await fetch(`${API_BASE}/sessions`);
    if (!response.ok) {
      throw new Error('Failed to fetch sessions');
    }
    return response.json();
  }

  async getSession(sessionId: string): Promise<Session> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}`);
    if (!response.ok) {
      throw new Error('Failed to fetch session');
    }
    return response.json();
  }

  async getMessages(params?: {
    session_id?: string;
    direction?: 'miner_to_pool' | 'pool_to_miner';
    limit?: number;
    offset?: number;
  }): Promise<CapturedMessage[]> {
    const query = new URLSearchParams();
    if (params?.session_id) query.append('session_id', params.session_id);
    if (params?.direction) query.append('direction', params.direction);
    if (params?.limit) query.append('limit', params.limit.toString());
    if (params?.offset) query.append('offset', params.offset.toString());

    const response = await fetch(`${API_BASE}/messages?${query}`);
    if (!response.ok) {
      throw new Error('Failed to fetch messages');
    }
    return response.json();
  }

  async getMessage(messageId: string): Promise<CapturedMessage> {
    const response = await fetch(`${API_BASE}/messages/${messageId}`);
    if (!response.ok) {
      throw new Error('Failed to fetch message');
    }
    return response.json();
  }

  connectWebSocket(onMessage: (message: CapturedMessage) => void): WebSocket {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const ws = new WebSocket(`${protocol}//${host}${API_BASE}/ws`);

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      onMessage(message);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return ws;
  }
}

export const api = new HashScopeAPI();

