/**
 * API client for HashScope backend
 */

export interface CapturedMessage {
  id: string;
  ts_recv: string;
  ts_fwd: string | null;
  direction: 'miner_to_pool' | 'pool_to_miner' | 'hashscope_to_pool';
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
  latency_ms?: number | null;
}

export interface ReplayResponse {
  success: boolean;
  pool_response?: Record<string, any> | null;
  error?: string | null;
  latency_ms?: number | null;
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
  broadcast_enabled?: boolean;
  repeat_count?: number;
  auto_replay_enabled?: boolean;
  auto_replay_count?: number;
  pool_host?: string | null;
  pool_port?: number | null;
  pool_connected?: boolean;
  pool_peer?: string | null;
  /** Hashsplit: which upstream leg this TCP session was assigned */
  hashsplit_leg?: 'customer' | 'fee' | string | null;
  hashsplit_enabled?: boolean | null;
  /** Worker name the miner authorized as (pass-through) */
  customer_worker?: string | null;
  /** Worker name sent upstream after hashsplit rewrite */
  upstream_worker?: string | null;
  stats?: {
    total_messages: number;
    miner_to_pool: number;
    pool_to_miner: number;
    parse_errors: number;
  };
}

export interface Agent {
  agent_id: string;
  last_seen: string;
  conn_state: 'connected' | 'reconnecting' | 'error';
  stats: {
    share_events_received_total: number;
    submits_attempted_total: number;
    submits_accepted_total: number;
    submits_rejected_total: number;
    last_submit_latency_ms: number | null;
    submits_per_second_1min: number | null;
    submits_per_second_10sec: number | null;
  };
  pool_target: {
    host: string;
    port: number;
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
    direction?: 'miner_to_pool' | 'pool_to_miner' | 'hashscope_to_pool';
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

  async replayMessage(messageId: string, modifiedMessage?: string): Promise<ReplayResponse> {
    const body = modifiedMessage ? { modified_message: modifiedMessage } : {};
    const response = await fetch(`${API_BASE}/messages/${messageId}/replay`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to replay message');
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

  // Session broadcast control
  async enableSessionBroadcast(sessionId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/broadcast/enable`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('Failed to enable broadcast');
    }
  }

  async disableSessionBroadcast(sessionId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/broadcast/disable`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('Failed to disable broadcast');
    }
  }

  async getSessionBroadcastStatus(sessionId: string): Promise<{ broadcast_enabled: boolean }> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/broadcast/status`);
    if (!response.ok) {
      throw new Error('Failed to get broadcast status');
    }
    return response.json();
  }

  async setSessionRepeatCount(sessionId: string, repeatCount: number): Promise<void> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/repeat-count`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ repeat_count: repeatCount }),
    });
    if (!response.ok) {
      throw new Error('Failed to set repeat count');
    }
  }

  async getSessionRepeatCount(sessionId: string): Promise<{ repeat_count: number }> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/repeat-count`);
    if (!response.ok) {
      throw new Error('Failed to get repeat count');
    }
    return response.json();
  }

  // Auto-replay control (load testing)
  async enableSessionAutoReplay(sessionId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/auto-replay/enable`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('Failed to enable auto-replay');
    }
  }

  async disableSessionAutoReplay(sessionId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/auto-replay/disable`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('Failed to disable auto-replay');
    }
  }

  async setSessionAutoReplayCount(sessionId: string, count: number): Promise<void> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/auto-replay-count`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ auto_replay_count: count }),
    });
    if (!response.ok) {
      throw new Error('Failed to set auto-replay count');
    }
  }

  async getSessionAutoReplayCount(sessionId: string): Promise<{ auto_replay_count: number }> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/auto-replay-count`);
    if (!response.ok) {
      throw new Error('Failed to get auto-replay count');
    }
    return response.json();
  }

  // Session control
  async disconnectSession(sessionId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/disconnect`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('Failed to disconnect session');
    }
  }

  // Agent telemetry
  async getAgents(): Promise<Agent[]> {
    const response = await fetch(`${API_BASE}/agents`);
    if (!response.ok) {
      throw new Error('Failed to fetch agents');
    }
    return response.json();
  }

  async getAgent(agentId: string): Promise<any> {
    const response = await fetch(`${API_BASE}/agents/${agentId}`);
    if (!response.ok) {
      throw new Error('Failed to fetch agent');
    }
    return response.json();
  }

  connectAgentsWebSocket(onMessage: (data: any) => void): WebSocket {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const ws = new WebSocket(`${protocol}//${host}${API_BASE}/ws/agents`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onMessage(data);
    };

    ws.onerror = (error) => {
      console.error('Agents WebSocket error:', error);
    };

    return ws;
  }
}

export const api = new HashScopeAPI();

