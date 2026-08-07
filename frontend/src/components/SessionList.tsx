import { Session, api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useState } from 'react';

interface SessionListProps {
  sessions: Session[];
  selectedSessionId: string | null;
  onSelectSession: (sessionId: string | null) => void;
  onSessionUpdate?: () => void;
}

export function SessionList({ sessions, selectedSessionId, onSelectSession, onSessionUpdate }: SessionListProps) {
  const [togglingBroadcast, setTogglingBroadcast] = useState<string | null>(null);
  const [editingRepeatCount, setEditingRepeatCount] = useState<string | null>(null);
  const [repeatCountInput, setRepeatCountInput] = useState<Record<string, string>>({});
  const [togglingAutoReplay, setTogglingAutoReplay] = useState<string | null>(null);
  const [editingAutoReplayCount, setEditingAutoReplayCount] = useState<string | null>(null);
  const [autoReplayCountInput, setAutoReplayCountInput] = useState<Record<string, string>>({});
  const [disconnecting, setDisconnecting] = useState<string | null>(null);

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleTimeString();
  };

  const handleBroadcastToggle = async (sessionId: string, currentlyEnabled: boolean, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent selecting the session

    setTogglingBroadcast(sessionId);
    try {
      if (currentlyEnabled) {
        await api.disableSessionBroadcast(sessionId);
      } else {
        await api.enableSessionBroadcast(sessionId);
      }
      // Refresh sessions
      if (onSessionUpdate) {
        onSessionUpdate();
      }
    } catch (error) {
      console.error('Failed to toggle broadcast:', error);
      alert('Failed to toggle broadcast. Please try again.');
    } finally {
      setTogglingBroadcast(null);
    }
  };

  const handleRepeatCountChange = async (sessionId: string, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent selecting the session

    const newCount = parseInt(repeatCountInput[sessionId] || '1', 10);
    if (isNaN(newCount) || newCount < 1 || newCount > 1000) {
      alert('Repeat count must be between 1 and 1000');
      return;
    }

    try {
      await api.setSessionRepeatCount(sessionId, newCount);
      setEditingRepeatCount(null);
      // Refresh sessions
      if (onSessionUpdate) {
        onSessionUpdate();
      }
    } catch (error) {
      console.error('Failed to set repeat count:', error);
      alert('Failed to set repeat count. Please try again.');
    }
  };

  const handleAutoReplayToggle = async (sessionId: string, currentlyEnabled: boolean, event: React.MouseEvent) => {
    event.stopPropagation();

    setTogglingAutoReplay(sessionId);
    try {
      if (currentlyEnabled) {
        await api.disableSessionAutoReplay(sessionId);
      } else {
        await api.enableSessionAutoReplay(sessionId);
      }
      if (onSessionUpdate) {
        onSessionUpdate();
      }
    } catch (error) {
      console.error('Failed to toggle auto-replay:', error);
      alert('Failed to toggle auto-replay. Please try again.');
    } finally {
      setTogglingAutoReplay(null);
    }
  };

  const handleAutoReplayCountChange = async (sessionId: string, event: React.MouseEvent) => {
    event.stopPropagation();

    const newCount = parseInt(autoReplayCountInput[sessionId] || '1', 10);
    if (isNaN(newCount) || newCount < 1 || newCount > 900000) {
      alert('Auto-replay count must be between 1 and 900,000');
      return;
    }

    try {
      await api.setSessionAutoReplayCount(sessionId, newCount);
      setEditingAutoReplayCount(null);
      if (onSessionUpdate) {
        onSessionUpdate();
      }
    } catch (error) {
      console.error('Failed to set auto-replay count:', error);
      alert('Failed to set auto-replay count. Please try again.');
    }
  };

  const handleDisconnect = async (sessionId: string, event: React.MouseEvent) => {
    event.stopPropagation();

    if (!confirm('Disconnect this session? This will close both pool and miner connections, forcing the miner to completely reconnect.')) {
      return;
    }

    setDisconnecting(sessionId);
    try {
      await api.disconnectSession(sessionId);
      // Refresh sessions to show updated status
      if (onSessionUpdate) {
        onSessionUpdate();
      }
    } catch (error) {
      console.error('Failed to disconnect session:', error);
      alert('Failed to disconnect session. Please try again.');
    } finally {
      setDisconnecting(null);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Sessions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <button
          className={`w-full text-left p-3 rounded-md border transition-colors ${
            selectedSessionId === null
              ? 'bg-primary text-primary-foreground'
              : 'hover:bg-accent'
          }`}
          onClick={() => onSelectSession(null)}
        >
          <div className="font-medium">All Sessions</div>
          <div className="text-sm text-muted-foreground">
            {sessions.length} active
          </div>
        </button>

        {sessions.map((session) => (
          <button
            key={session.session_id}
            className={`w-full text-left p-3 rounded-md border transition-colors ${
              selectedSessionId === session.session_id
                ? 'bg-primary text-primary-foreground'
                : 'hover:bg-accent'
            }`}
            onClick={() => onSelectSession(session.session_id)}
          >
            {/* User Agent (if available) */}
            {session.user_agent && (
              <div className="font-semibold text-sm mb-1 truncate" title={session.user_agent}>
                {session.user_agent}
              </div>
            )}

            {/* Hashsplit leg + upstream worker (fee rewrite) */}
            {(session.hashsplit_leg || session.upstream_worker) && (
              <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                {session.hashsplit_leg && (
                  <Badge
                    variant={session.hashsplit_leg === 'fee' ? 'default' : 'secondary'}
                    className="text-[10px] px-1.5 py-0"
                  >
                    {session.hashsplit_leg === 'fee' ? 'FEE' : 'CUSTOMER'}
                  </Badge>
                )}
                {session.upstream_worker && (
                  <span
                    className="font-mono text-[10px] opacity-90 truncate max-w-[140px]"
                    title={
                      session.customer_worker &&
                      session.customer_worker !== session.upstream_worker
                        ? `${session.customer_worker} → ${session.upstream_worker}`
                        : session.upstream_worker
                    }
                  >
                    {session.upstream_worker.includes('.')
                      ? session.upstream_worker.split('.').slice(-1)[0]
                      : session.upstream_worker}
                  </span>
                )}
              </div>
            )}

            {/* Peer IP:Port and Message Count */}
            <div className="flex items-center justify-between mb-1">
              <span className="font-mono text-xs opacity-90">
                {session.peer}
              </span>
              <Badge variant="secondary">{session.message_count}</Badge>
            </div>

            {/* Pool Connection Status */}
            {session.pool_host && (
              <div className="mt-2 pt-2 border-t">
                <div className="text-xs font-medium mb-1">Target Pool:</div>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs opacity-90">
                    {session.pool_host}:{session.pool_port}
                  </span>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={session.pool_connected ? "default" : "destructive"}
                      className={session.pool_connected ? "bg-green-600" : "bg-red-600"}
                    >
                      {session.pool_connected ? "Connected" : "Failed"}
                    </Badge>
                    {session.pool_connected && (
                      <Button
                        onClick={(e) => handleDisconnect(session.session_id, e)}
                        disabled={disconnecting === session.session_id}
                        size="sm"
                        variant="destructive"
                        className="h-5 px-2 text-xs"
                        title="Disconnect session (closes both pool and miner connections)"
                      >
                        {disconnecting === session.session_id ? '...' : '✕'}
                      </Button>
                    )}
                  </div>
                </div>
                {session.pool_peer && session.pool_connected && (
                  <div className="text-xs opacity-75 mt-1">
                    → {session.pool_peer}
                  </div>
                )}
              </div>
            )}

            {/* Difficulty (if available) */}
            {session.difficulty !== null && session.difficulty !== undefined && (
              <div className="text-xs opacity-90 mt-2 pt-2 border-t font-medium">
                Difficulty: {session.difficulty.toLocaleString()}
              </div>
            )}

            {/* Last Seen */}
            <div className="text-xs opacity-75 mt-2">
              Last seen: {formatDate(session.last_seen)}
            </div>

            {/* Auto-Replay Toggle (Load Testing) */}
            <div className="flex items-center justify-between mb-1 mt-2 border-t pt-2">
              <span className="text-xs font-medium">
                Auto-Replay:
              </span>
              <button
                onClick={(e) => handleAutoReplayToggle(session.session_id, session.auto_replay_enabled || false, e)}
                disabled={togglingAutoReplay === session.session_id}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary ${
                  session.auto_replay_enabled ? 'bg-purple-600' : 'bg-gray-300'
                } ${togglingAutoReplay === session.session_id ? 'opacity-50 cursor-not-allowed' : ''}`}
                title={session.auto_replay_enabled ? 'Disable auto-replay' : 'Enable auto-replay'}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    session.auto_replay_enabled ? 'translate-x-5' : 'translate-x-0.5'
                  }`}
                />
              </button>
            </div>
            {session.auto_replay_enabled && (
              <Badge variant="default" className="text-xs bg-purple-600">
                Auto-Replaying
              </Badge>
            )}

            {/* Auto-Replay Count Control */}
            {session.auto_replay_enabled && (
              <div className="flex items-center justify-between mt-2 pt-2 border-t">
                <span className="text-xs font-medium">
                  Replay Count:
                </span>
                {editingAutoReplayCount === session.session_id ? (
                  <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="number"
                      min="1"
                      max="900000"
                      value={autoReplayCountInput[session.session_id] || session.auto_replay_count || 1}
                      onChange={(e) => {
                        e.stopPropagation();
                        setAutoReplayCountInput({ ...autoReplayCountInput, [session.session_id]: e.target.value });
                      }}
                      className="w-20 px-2 py-1 text-xs border rounded"
                      autoFocus
                    />
                    <button
                      onClick={(e) => handleAutoReplayCountChange(session.session_id, e)}
                      className="px-2 py-1 text-xs bg-purple-600 text-white rounded hover:bg-purple-700"
                    >
                      ✓
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingAutoReplayCount(null);
                      }}
                      className="px-2 py-1 text-xs bg-gray-300 rounded hover:bg-gray-400"
                    >
                      ✕
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-1">
                    <span className="font-mono text-xs font-semibold">{session.auto_replay_count || 1}x</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingAutoReplayCount(session.session_id);
                        setAutoReplayCountInput({ ...autoReplayCountInput, [session.session_id]: String(session.auto_replay_count || 1) });
                      }}
                      className="px-1 py-0.5 text-xs bg-gray-200 rounded hover:bg-gray-300"
                      title="Edit auto-replay count (1-900,000)"
                    >
                      Edit
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Broadcast Toggle */}
            <div className="flex items-center justify-between mb-1 mt-2 border-t pt-2">
              <span className="text-xs font-medium">
                Broadcast to Agents:
              </span>
              <button
                onClick={(e) => handleBroadcastToggle(session.session_id, session.broadcast_enabled || false, e)}
                disabled={togglingBroadcast === session.session_id}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary ${
                  session.broadcast_enabled ? 'bg-green-600' : 'bg-gray-300'
                } ${togglingBroadcast === session.session_id ? 'opacity-50 cursor-not-allowed' : ''}`}
                title={session.broadcast_enabled ? 'Disable broadcasting to agent fleet' : 'Enable broadcasting to agent fleet'}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    session.broadcast_enabled ? 'translate-x-5' : 'translate-x-0.5'
                  }`}
                />
              </button>
            </div>
            {session.broadcast_enabled && (
              <Badge variant="default" className="text-xs bg-green-600">
                Broadcasting
              </Badge>
            )}

            {/* Repeat Count Control (Load Testing) */}
            {session.broadcast_enabled && (
              <div className="flex items-center justify-between mt-2 pt-2 border-t">
                <span className="text-xs font-medium">
                  Repeat Count:
                </span>
                {editingRepeatCount === session.session_id ? (
                  <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="number"
                      min="1"
                      max="1000"
                      value={repeatCountInput[session.session_id] || session.repeat_count || 1}
                      onChange={(e) => {
                        e.stopPropagation();
                        setRepeatCountInput({ ...repeatCountInput, [session.session_id]: e.target.value });
                      }}
                      className="w-16 px-2 py-1 text-xs border rounded"
                      autoFocus
                    />
                    <button
                      onClick={(e) => handleRepeatCountChange(session.session_id, e)}
                      className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
                    >
                      ✓
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingRepeatCount(null);
                      }}
                      className="px-2 py-1 text-xs bg-gray-300 rounded hover:bg-gray-400"
                    >
                      ✕
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-1">
                    <span className="font-mono text-xs font-semibold">{session.repeat_count || 1}x</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingRepeatCount(session.session_id);
                        setRepeatCountInput({ ...repeatCountInput, [session.session_id]: String(session.repeat_count || 1) });
                      }}
                      className="px-1 py-0.5 text-xs bg-gray-200 rounded hover:bg-gray-300"
                      title="Edit repeat count (load testing)"
                    >
                      Edit
                    </button>
                  </div>
                )}
              </div>
            )}
          </button>
        ))}

        {sessions.length === 0 && (
          <div className="text-center text-muted-foreground py-8">
            No active sessions
          </div>
        )}
      </CardContent>
    </Card>
  );
}

