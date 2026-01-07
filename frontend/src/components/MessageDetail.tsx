import { CapturedMessage } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { StratumDecoder } from './StratumDecoder';

interface MessageDetailProps {
  message: CapturedMessage | null;
}

export function MessageDetail({ message }: MessageDetailProps) {
  if (!message) {
    return (
      <Card>
        <CardContent className="p-12 text-center text-muted-foreground">
          Select a message to view details
        </CardContent>
      </Card>
    );
  }

  const formatTimestamp = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Message Detail</CardTitle>
          {message.parse_error ? (
            <Badge variant="destructive">Parse Error</Badge>
          ) : (
            <Badge variant="outline">OK</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <div className="font-medium text-muted-foreground">Message ID</div>
            <div className="font-mono">{message.id}</div>
          </div>
          <div>
            <div className="font-medium text-muted-foreground">Session ID</div>
            <div className="font-mono text-xs">{message.session_id}</div>
          </div>
          <div>
            <div className="font-medium text-muted-foreground">Direction</div>
            <div>
              {message.direction === 'miner_to_pool' ? 'Miner → Pool' : 'Pool → Miner'}
            </div>
          </div>
          <div>
            <div className="font-medium text-muted-foreground">Peer</div>
            <div className="font-mono text-xs">{message.peer}</div>
          </div>
          <div>
            <div className="font-medium text-muted-foreground">Received</div>
            <div className="text-xs">{formatTimestamp(message.ts_recv)}</div>
          </div>
          <div>
            <div className="font-medium text-muted-foreground">Forwarded</div>
            <div className="text-xs">
              {message.ts_fwd ? formatTimestamp(message.ts_fwd) : '-'}
            </div>
          </div>
          <div>
            <div className="font-medium text-muted-foreground">Size</div>
            <div>{message.size_bytes} bytes</div>
          </div>
          {message.decoded?.method && (
            <div>
              <div className="font-medium text-muted-foreground">Method</div>
              <div className="font-mono">{message.decoded.method}</div>
            </div>
          )}
        </div>

        <Tabs defaultValue="decoded" className="w-full">
          <TabsList className="w-full">
            <TabsTrigger value="decoded" className="flex-1">
              Decoded (Stratum)
            </TabsTrigger>
            <TabsTrigger value="raw" className="flex-1">
              Raw JSON
            </TabsTrigger>
          </TabsList>

          <TabsContent value="decoded" className="mt-4">
            {message.parse_error ? (
              <div className="p-4 bg-destructive/10 text-destructive rounded-md">
                <div className="font-medium mb-2">Parse Error:</div>
                <pre className="text-xs whitespace-pre-wrap">{message.parse_error}</pre>
              </div>
            ) : (
              <StratumDecoder
                decoded={message.decoded}
                response={message.response}
                responseTimestamp={message.response_ts_recv}
              />
            )}
          </TabsContent>

          <TabsContent value="raw" className="mt-4">
            <div className="space-y-4">
              {/* Request */}
              <div>
                <div className="text-sm font-semibold text-foreground mb-3">
                  Request {message.direction === 'miner_to_pool' ? '(Miner → Pool)' : '(Pool → Miner)'}
                </div>
                <div className="space-y-3">
                  <div>
                    <div className="text-xs font-medium text-muted-foreground mb-2">Formatted JSON</div>
                    <pre className="p-4 bg-muted rounded-md text-xs overflow-auto max-h-64">
                      {message.decoded ? JSON.stringify(message.decoded, null, 2) : 'No decoded data'}
                    </pre>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-muted-foreground mb-2">Raw Bytes</div>
                    <pre className="p-4 bg-muted rounded-md text-xs overflow-auto max-h-64 break-all whitespace-pre-wrap">
                      {message.raw}
                    </pre>
                  </div>
                </div>
              </div>

              {/* Response (if paired) */}
              {message.response && (
                <div className="border-t-2 border-primary/20 pt-4">
                  <div className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                    <span>Response {message.direction === 'miner_to_pool' ? '(Pool → Miner)' : '(Miner → Pool)'}</span>
                    {message.response_ts_recv && (
                      <span className="text-xs font-normal text-muted-foreground">
                        at {new Date(message.response_ts_recv).toLocaleTimeString()}.
                        {new Date(message.response_ts_recv).getMilliseconds().toString().padStart(3, '0')}
                      </span>
                    )}
                  </div>
                  <div className="space-y-3">
                    <div>
                      <div className="text-xs font-medium text-muted-foreground mb-2">Formatted JSON</div>
                      <pre className="p-4 bg-muted rounded-md text-xs overflow-auto max-h-64">
                        {JSON.stringify(message.response, null, 2)}
                      </pre>
                    </div>
                    {message.response_raw && (
                      <div>
                        <div className="text-xs font-medium text-muted-foreground mb-2">Raw Bytes</div>
                        <pre className="p-4 bg-muted rounded-md text-xs overflow-auto max-h-64 break-all whitespace-pre-wrap">
                          {message.response_raw}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

