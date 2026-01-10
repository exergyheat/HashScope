import { useState, useEffect } from 'react';
import { CapturedMessage } from '@/lib/api';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { StratumDecoder } from './StratumDecoder';
import { api } from '@/lib/api';

interface MessageDetailProps {
  message: CapturedMessage | null;
  onReplaySuccess?: () => void;
  onClose?: () => void;
}

interface ReplayFormData {
  worker_name: string;
  job_id: string;
  extranonce2: string;
  ntime: string;
  nonce: string;
  version_bits: string;
  message_id: string | number;
}

export function MessageDetail({ message, onReplaySuccess, onClose }: MessageDetailProps) {
  const [isReplaying, setIsReplaying] = useState(false);
  const [replayError, setReplayError] = useState<string | null>(null);
  const [showReplayDialog, setShowReplayDialog] = useState(false);
  const [replayFormData, setReplayFormData] = useState<ReplayFormData>({
    worker_name: '',
    job_id: '',
    extranonce2: '',
    ntime: '',
    nonce: '',
    version_bits: '',
    message_id: 0,
  });

  // Clear error when message changes
  useEffect(() => {
    setReplayError(null);
  }, [message?.id]);

  // Handle ESC key to close sidebar
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && onClose) {
        onClose();
      }
    };

    if (message) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [message, onClose]);

  // Initialize form data when dialog opens
  const handleOpenReplayDialog = () => {
    if (!message || !message.decoded) return;

    const params = message.decoded.params as any[];
    if (!params || params.length < 5) return;

    setReplayFormData({
      worker_name: params[0] || '',
      job_id: params[1] || '',
      extranonce2: params[2] || '',
      ntime: params[3] || '',
      nonce: params[4] || '',
      version_bits: params[5] || '', // Optional parameter
      message_id: message.decoded.id || 0,
    });
    setReplayError(null);
    setShowReplayDialog(true);
  };

  const handleReplaySubmit = async () => {
    if (!message) return;

    setIsReplaying(true);
    setReplayError(null);

    try {
      // Construct the modified mining.submit message
      const params = [
        replayFormData.worker_name,
        replayFormData.job_id,
        replayFormData.extranonce2,
        replayFormData.ntime,
        replayFormData.nonce,
      ];

      // Add version_bits if present
      if (replayFormData.version_bits) {
        params.push(replayFormData.version_bits);
      }

      const modifiedMessage = {
        id: replayFormData.message_id,
        method: 'mining.submit',
        params: params,
      };

      // Call the replay API with modified message
      await api.replayMessage(message.id, JSON.stringify(modifiedMessage));

      // Success
      setShowReplayDialog(false);
      if (onReplaySuccess) {
        onReplaySuccess();
      }
    } catch (error) {
      setReplayError(error instanceof Error ? error.message : 'Failed to replay message');
    } finally {
      setIsReplaying(false);
    }
  };

  const canReplay = message &&
                    message.direction === 'miner_to_pool' &&
                    message.decoded?.method === 'mining.submit';

  const getDirectionLabel = (direction: string): string => {
    if (direction === 'miner_to_pool') return 'Miner → Pool';
    if (direction === 'hashscope_to_pool') return 'HashScope → Pool (Replay)';
    return 'Pool → Miner';
  };

  const getResponseDirectionLabel = (direction: string): string => {
    if (direction === 'miner_to_pool') return '(Pool → Miner)';
    if (direction === 'hashscope_to_pool') return '(Pool → HashScope)';
    return '(Miner → Pool)';
  };

  if (!message) {
    return null;
  }

  const formatTimestamp = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const getLatencyColor = (latencyMs: number | null | undefined): string => {
    if (latencyMs === null || latencyMs === undefined) return '';
    if (latencyMs > 200) return 'text-red-600 font-semibold';
    if (latencyMs > 50) return 'text-yellow-600 font-semibold';
    return 'text-green-600';
  };

  const formatLatency = (latencyMs: number | null | undefined): string => {
    if (latencyMs === null || latencyMs === undefined) return '-';
    return `${latencyMs.toFixed(1)}ms`;
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header with close button */}
      <div className="sticky top-0 z-10 bg-background border-b px-6 py-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold">Message Detail</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="hover:bg-accent"
          >
            ✕
          </Button>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {canReplay && (
            <Button
              onClick={handleOpenReplayDialog}
              disabled={isReplaying}
              size="sm"
              variant="outline"
              title="Edit and replay this mining.submit message to the pool"
            >
              🔄 Replay & Edit
            </Button>
          )}
          {message.parse_error ? (
            <Badge variant="destructive">Parse Error</Badge>
          ) : (
            <Badge variant="outline">OK</Badge>
          )}
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
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
              {getDirectionLabel(message.direction)}
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
          {message.latency_ms !== null && message.latency_ms !== undefined && (
            <div>
              <div className="font-medium text-muted-foreground">Response Latency</div>
              <div className={`font-mono ${getLatencyColor(message.latency_ms)}`}>
                {formatLatency(message.latency_ms)}
              </div>
            </div>
          )}
        </div>

        {/* Replay Error (if any) */}
        {replayError && (
          <div className="p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-md">
            <div className="font-semibold text-red-900 dark:text-red-100 mb-1">Replay Error</div>
            <div className="text-sm text-red-700 dark:text-red-300">{replayError}</div>
          </div>
        )}

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
                  Request ({getDirectionLabel(message.direction)})
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
                    <span>Response {getResponseDirectionLabel(message.direction)}</span>
                    {message.response_ts_recv && (
                      <span className="text-xs font-normal text-muted-foreground">
                        at {new Date(message.response_ts_recv).toLocaleTimeString()}.
                        {new Date(message.response_ts_recv).getMilliseconds().toString().padStart(3, '0')}
                      </span>
                    )}
                    {message.latency_ms !== null && message.latency_ms !== undefined && (
                      <span className={`text-xs font-mono ${getLatencyColor(message.latency_ms)}`}>
                        ({formatLatency(message.latency_ms)})
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
      </div>

      {/* Replay Form Dialog */}
      <Dialog open={showReplayDialog} onOpenChange={setShowReplayDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit & Replay mining.submit</DialogTitle>
            <DialogDescription>
              Modify any parameters below before replaying this message to the pool. Perfect for testing pool validation logic.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Message ID */}
            <div className="space-y-2">
              <Label htmlFor="message_id">Message ID</Label>
              <Input
                id="message_id"
                value={replayFormData.message_id}
                onChange={(e) => setReplayFormData({ ...replayFormData, message_id: e.target.value })}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">The JSON-RPC message ID for this request</p>
            </div>

            {/* Worker Name */}
            <div className="space-y-2">
              <Label htmlFor="worker_name">Worker Name</Label>
              <Input
                id="worker_name"
                value={replayFormData.worker_name}
                onChange={(e) => setReplayFormData({ ...replayFormData, worker_name: e.target.value })}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">The worker/miner identifier (e.g., wallet.worker_name)</p>
            </div>

            {/* Job ID */}
            <div className="space-y-2">
              <Label htmlFor="job_id">Job ID</Label>
              <Input
                id="job_id"
                value={replayFormData.job_id}
                onChange={(e) => setReplayFormData({ ...replayFormData, job_id: e.target.value })}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">The mining job identifier from mining.notify</p>
            </div>

            {/* ExtraNonce2 */}
            <div className="space-y-2">
              <Label htmlFor="extranonce2">ExtraNonce2</Label>
              <Input
                id="extranonce2"
                value={replayFormData.extranonce2}
                onChange={(e) => setReplayFormData({ ...replayFormData, extranonce2: e.target.value })}
                className="font-mono text-sm"
                placeholder="e.g., 0b00000000b7ce3f"
              />
              <p className="text-xs text-muted-foreground">The miner's portion of the extra nonce (hex)</p>
            </div>

            {/* nTime */}
            <div className="space-y-2">
              <Label htmlFor="ntime">nTime</Label>
              <Input
                id="ntime"
                value={replayFormData.ntime}
                onChange={(e) => setReplayFormData({ ...replayFormData, ntime: e.target.value })}
                className="font-mono text-sm"
                placeholder="e.g., 695f100e"
              />
              <p className="text-xs text-muted-foreground">Block header timestamp (hex, little-endian)</p>
            </div>

            {/* Nonce */}
            <div className="space-y-2">
              <Label htmlFor="nonce">Nonce</Label>
              <Input
                id="nonce"
                value={replayFormData.nonce}
                onChange={(e) => setReplayFormData({ ...replayFormData, nonce: e.target.value })}
                className="font-mono text-sm"
                placeholder="e.g., 2ae00486"
              />
              <p className="text-xs text-muted-foreground">Block header nonce (hex, little-endian)</p>
            </div>

            {/* Version Bits */}
            <div className="space-y-2">
              <Label htmlFor="version_bits">Version Bits (Optional)</Label>
              <Input
                id="version_bits"
                value={replayFormData.version_bits}
                onChange={(e) => setReplayFormData({ ...replayFormData, version_bits: e.target.value })}
                className="font-mono text-sm"
                placeholder="e.g., 0492a000"
              />
              <p className="text-xs text-muted-foreground">BIP320 version bits mask (hex) - some pools may require this</p>
            </div>

            {/* Error Display */}
            {replayError && (
              <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-md">
                <div className="text-sm font-semibold text-destructive mb-1">Replay Error</div>
                <div className="text-xs text-destructive/90">{replayError}</div>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowReplayDialog(false)}
              disabled={isReplaying}
            >
              Cancel
            </Button>
            <Button
              onClick={handleReplaySubmit}
              disabled={isReplaying}
            >
              {isReplaying ? 'Replaying...' : '🔄 Replay to Pool'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

