import { Session } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface SessionListProps {
  sessions: Session[];
  selectedSessionId: string | null;
  onSelectSession: (sessionId: string | null) => void;
}

export function SessionList({ sessions, selectedSessionId, onSelectSession }: SessionListProps) {
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleTimeString();
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

            {/* Peer IP:Port and Message Count */}
            <div className="flex items-center justify-between mb-1">
              <span className="font-mono text-xs opacity-90">
                {session.peer}
              </span>
              <Badge variant="secondary">{session.message_count}</Badge>
            </div>

            {/* Difficulty (if available) */}
            {session.difficulty !== null && session.difficulty !== undefined && (
              <div className="text-xs opacity-90 mb-1 font-medium">
                Difficulty: {session.difficulty.toLocaleString()}
              </div>
            )}

            {/* Mining Session ID (if available) */}
            {session.mining_session_id && (
              <div className="text-xs opacity-75 truncate mb-1" title={`Session: ${session.mining_session_id}`}>
                Session: {session.mining_session_id.substring(0, 16)}...
              </div>
            )}

            <div className="text-xs opacity-75">
              Connected: {formatDate(session.first_seen)}
            </div>
            <div className="text-xs opacity-75">
              Last seen: {formatDate(session.last_seen)}
            </div>
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

