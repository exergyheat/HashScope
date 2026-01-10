import { useEffect, useState } from 'react';
import { Book } from 'lucide-react';
import { api, CapturedMessage, Session } from './lib/api';
import { SessionList } from './components/SessionList';
import { MessageFilters } from './components/MessageFilters';
import { MessageTable } from './components/MessageTable';
import { MessageDetail } from './components/MessageDetail';
import { AgentStatus } from './components/AgentStatus';
import { Card, CardContent, CardHeader, CardTitle } from './components/ui/card';
import { Button } from './components/ui/button';

function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [messages, setMessages] = useState<CapturedMessage[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);
  const [selectedMessage, setSelectedMessage] = useState<CapturedMessage | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [directionFilter, setDirectionFilter] = useState<'all' | 'miner_to_pool' | 'pool_to_miner' | 'hashscope_to_pool'>('all');
  const [showErrorsOnly, setShowErrorsOnly] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // WebSocket connection status
  const [wsConnected, setWsConnected] = useState(false);

  // Track new messages for flash animation
  const [newMessageIds, setNewMessageIds] = useState<Set<string>>(new Set());

  // Load sessions
  const loadSessions = async () => {
    try {
      const data = await api.getSessions();
      setSessions(data);
    } catch (error) {
      console.error('Failed to load sessions:', error);
    }
  };

  useEffect(() => {
    loadSessions();
    const interval = setInterval(loadSessions, 5000); // Refresh every 5s

    return () => clearInterval(interval);
  }, []);

  // Load messages
  useEffect(() => {
    const loadMessages = async () => {
      try {
        const data = await api.getMessages({
          session_id: selectedSessionId || undefined,
          direction: directionFilter !== 'all' ? directionFilter : undefined,
          limit: 100,
        });
        // Simply replace messages with fresh API data
        // WebSocket handler will deduplicate if new messages arrive
        setMessages(data);
      } catch (error) {
        console.error('Failed to load messages:', error);
      }
    };

    loadMessages();
  }, [selectedSessionId, directionFilter, refreshTrigger]);

  // WebSocket for real-time updates - no filtering, just add all messages
  useEffect(() => {
    const ws = api.connectWebSocket((message) => {
      let isNewMessage = false;

      setMessages((prev) => {
        // Check if message already exists (happens when request gets paired with response)
        const existingIndex = prev.findIndex((m) => m.id === message.id);

        if (existingIndex !== -1) {
          // UPDATE existing message instead of adding duplicate
          const updated = [...prev];
          updated[existingIndex] = message;
          isNewMessage = false;
          return updated;
        } else {
          // NEW message - add to list
          isNewMessage = true;
          return [message, ...prev].slice(0, 1000);
        }
      });

      // Mark as new for flash animation
      setNewMessageIds((prev) => new Set(prev).add(message.id));

      // Remove from new messages after 2 seconds
      setTimeout(() => {
        setNewMessageIds((prev) => {
          const newSet = new Set(prev);
          newSet.delete(message.id);
          return newSet;
        });
      }, 2000);

      // Update session list - only increment count for NEW messages
      setSessions((prev) => {
        const existing = prev.find((s) => s.session_id === message.session_id);
        if (existing) {
          return prev.map((s) =>
            s.session_id === message.session_id
              ? {
                  ...s,
                  message_count: isNewMessage ? s.message_count + 1 : s.message_count,
                  last_seen: message.ts_recv
                }
              : s
          );
        } else {
          // New session
          return [
            ...prev,
            {
              session_id: message.session_id,
              peer: message.peer,
              first_seen: message.ts_recv,
              last_seen: message.ts_recv,
              message_count: 1,
            },
          ];
        }
      });
    });

    ws.onopen = () => setWsConnected(true);
    ws.onclose = () => setWsConnected(false);

    return () => {
      ws.close();
    };
  }, []); // No dependencies - never reconnect

  // Load selected message detail
  useEffect(() => {
    if (selectedMessageId) {
      const message = messages.find((m) => m.id === selectedMessageId);
      setSelectedMessage(message || null);
    } else {
      setSelectedMessage(null);
    }
  }, [selectedMessageId, messages]);

  // Apply ALL filters client-side (session, direction, search, errors)
  const filteredMessages = messages
    .filter((message) => {
      // Session filter
      if (selectedSessionId && message.session_id !== selectedSessionId) {
        return false;
      }

      // Direction filter
      if (directionFilter !== 'all' && message.direction !== directionFilter) {
        return false;
      }

      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const searchableText = JSON.stringify({
          ...message.decoded,
          raw: message.raw,
          peer: message.peer,
        }).toLowerCase();
        if (!searchableText.includes(query)) {
          return false;
        }
      }

      // Errors filter
      if (showErrorsOnly && !message.parse_error) {
        return false;
      }

      return true;
    })
    .sort((a, b) => {
      // Sort by most recent timestamp (newest first)
      // Use response timestamp if available, otherwise request timestamp
      const timeA = new Date(a.response_ts_recv || a.ts_recv).getTime();
      const timeB = new Date(b.response_ts_recv || b.ts_recv).getTime();
      return timeB - timeA; // Descending order (newest first)
    });

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <header className="border-b flex-shrink-0">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">HashScope</h1>
              <p className="text-sm text-muted-foreground">
                Bitcoin Mining MITM Proxy
              </p>
            </div>
            <div className="flex items-center gap-4">
              <a href="/docs/" target="_blank" rel="noopener noreferrer">
                <Button variant="outline" size="sm">
                  <Book className="h-4 w-4 mr-2" />
                  Documentation
                </Button>
              </a>
              <div className="flex items-center gap-2">
                <div
                  className={`h-2 w-2 rounded-full ${
                    wsConnected ? 'bg-green-500' : 'bg-red-500'
                  }`}
                />
                <span className="text-sm text-muted-foreground">
                  {wsConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="w-full px-4 py-6 h-full">
          <div className="flex gap-6 h-full">
          {/* Sessions sidebar - Fixed width */}
          <div className="w-[350px] flex-shrink-0 space-y-6 overflow-y-auto">
            <SessionList
              sessions={sessions}
              selectedSessionId={selectedSessionId}
              onSelectSession={setSelectedSessionId}
              onSessionUpdate={loadSessions}
            />
            <AgentStatus />
          </div>

          {/* Main content - Flexible width */}
          <div className="flex-1 flex flex-col gap-6 min-h-0">
            {/* Filters */}
            <Card className="flex-shrink-0">
              <CardHeader>
                <CardTitle className="text-lg">Filters</CardTitle>
              </CardHeader>
              <CardContent>
                <MessageFilters
                  searchQuery={searchQuery}
                  onSearchChange={setSearchQuery}
                  directionFilter={directionFilter}
                  onDirectionFilterChange={setDirectionFilter}
                  showErrorsOnly={showErrorsOnly}
                  onShowErrorsOnlyChange={setShowErrorsOnly}
                />
              </CardContent>
            </Card>

            {/* Messages table */}
            <div className="flex-1 flex flex-col min-h-0 w-full">
              <h2 className="text-xl font-semibold mb-3 flex-shrink-0">
                Messages ({filteredMessages.length})
              </h2>
              <div className="flex-1 min-h-0 w-full">
                <MessageTable
                  messages={filteredMessages}
                  selectedMessageId={selectedMessageId}
                  onSelectMessage={setSelectedMessageId}
                  newMessageIds={newMessageIds}
                  sessions={sessions}
                  showSessionColumn={true}
                />
              </div>
            </div>
          </div>
          </div>
        </div>
      </main>

      {/* Overlay when sidebar is open */}
      {selectedMessageId && (
        <div
          className="fixed inset-0 bg-black/50 z-40 transition-opacity"
          onClick={() => setSelectedMessageId(null)}
        />
      )}

      {/* Slide-in sidebar for message detail */}
      <div
        className={`fixed top-0 right-0 h-full w-[800px] bg-background border-l shadow-2xl z-50 transform transition-transform duration-300 ease-in-out overflow-y-auto ${
          selectedMessageId ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {selectedMessageId && (
          <MessageDetail
            message={selectedMessage}
            onReplaySuccess={() => setRefreshTrigger(prev => prev + 1)}
            onClose={() => setSelectedMessageId(null)}
          />
        )}
      </div>
    </div>
  );
}

export default App;

