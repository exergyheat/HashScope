import { CapturedMessage } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';

interface MessageTableProps {
  messages: CapturedMessage[];
  selectedMessageId: string | null;
  onSelectMessage: (messageId: string) => void;
  newMessageIds?: Set<string>;
  sessions?: any[];
  showSessionColumn?: boolean;
}

export function MessageTable({ messages, selectedMessageId, onSelectMessage, newMessageIds, sessions, showSessionColumn }: MessageTableProps) {
  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleTimeString() + '.' + date.getMilliseconds().toString().padStart(3, '0');
  };

  const getDirectionBadge = (direction: string) => {
    if (direction === 'miner_to_pool') {
      return <Badge variant="default">Miner → Pool</Badge>;
    }
    return <Badge variant="secondary">Pool → Miner</Badge>;
  };

  const truncate = (str: string | null | undefined, length: number) => {
    if (!str) return '-';
    if (str.length <= length) return str;
    return str.substring(0, length) + '...';
  };

  const getMethod = (message: CapturedMessage): string => {
    if (message.decoded?.method) {
      return message.decoded.method;
    }
    if (message.decoded?.result !== undefined) {
      return 'response';
    }
    if (message.decoded?.error !== undefined) {
      return 'error';
    }
    return '-';
  };

  const getMessageId = (message: CapturedMessage): string => {
    return message.decoded?.id?.toString() || '-';
  };

  const getSessionDisplay = (message: CapturedMessage): string => {
    // Find the session for this message
    const session = sessions?.find(s => s.session_id === message.session_id);
    if (session) {
      // Prefer user agent, fallback to peer
      return session.user_agent || session.peer;
    }
    // Fallback to message peer or truncated session ID
    return message.peer || message.session_id.substring(0, 8);
  };

  return (
    <Card>
      <CardContent className="p-0">
        <div className="overflow-auto max-h-[600px]">
          <table className="w-full text-sm">
            <thead className="bg-muted sticky top-0">
              <tr>
                {showSessionColumn && (
                  <th className="text-left p-3 font-medium">Session</th>
                )}
                <th className="text-left p-3 font-medium">Time</th>
                <th className="text-left p-3 font-medium">Direction</th>
                <th className="text-left p-3 font-medium">Method</th>
                <th className="text-left p-3 font-medium">ID</th>
                <th className="text-left p-3 font-medium">Params/Result</th>
                <th className="text-left p-3 font-medium">Size</th>
                <th className="text-left p-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {messages.map((message) => {
                const isSelected = selectedMessageId === message.id;
                const isNew = newMessageIds?.has(message.id);

                return (
                  <tr
                    key={message.id}
                    className={`border-t cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-primary/20 border-l-4 border-l-primary'
                        : 'hover:bg-accent'
                    } ${
                      isNew ? 'animate-flash' : ''
                    }`}
                    onClick={() => onSelectMessage(message.id)}
                  >
                  {showSessionColumn && (
                    <td className="p-3 text-xs max-w-[150px] truncate" title={getSessionDisplay(message)}>
                      {getSessionDisplay(message)}
                    </td>
                  )}
                  <td className="p-3 font-mono text-xs">{formatTime(message.ts_recv)}</td>
                  <td className="p-3">{getDirectionBadge(message.direction)}</td>
                  <td className="p-3 font-mono">{getMethod(message)}</td>
                  <td className="p-3 font-mono text-xs">{getMessageId(message)}</td>
                  <td className="p-3 font-mono text-xs max-w-xs overflow-hidden">
                    {truncate(
                      JSON.stringify(message.decoded?.params || message.decoded?.result),
                      50
                    )}
                  </td>
                  <td className="p-3 text-xs">{message.size_bytes}B</td>
                  <td className="p-3">
                    <div className="flex gap-1">
                      {message.parse_error ? (
                        <Badge variant="destructive">Error</Badge>
                      ) : (
                        <Badge variant="outline">OK</Badge>
                      )}
                      {message.response && (
                        <Badge variant="secondary" className="text-xs">
                          ↔
                        </Badge>
                      )}
                    </div>
                  </td>
                </tr>
              );
              })}
            </tbody>
          </table>

          {messages.length === 0 && (
            <div className="text-center text-muted-foreground py-12">
              No messages to display
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

