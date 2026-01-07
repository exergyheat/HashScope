import { Badge } from '@/components/ui/badge';

interface StratumDecoderProps {
  decoded: Record<string, any> | null;
  response?: Record<string, any> | null;
  responseTimestamp?: string | null;
}

export function StratumDecoder({ decoded, response, responseTimestamp }: StratumDecoderProps) {
  if (!decoded) {
    return <div className="text-muted-foreground">No decoded data</div>;
  }

  const { id, method, params, result, error } = decoded;

  return (
    <div className="space-y-4">
      {/* Message Type & ID */}
      <div className="grid grid-cols-2 gap-4">
        {id !== undefined && id !== null && (
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">Message ID</div>
            <div className="font-mono">{id}</div>
          </div>
        )}
        {method && (
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">Method</div>
            <Badge variant="default">{method}</Badge>
          </div>
        )}
      </div>

      {/* Request Methods */}
      {method === 'mining.subscribe' && <MiningSubscribe params={params} />}
      {method === 'mining.authorize' && <MiningAuthorize params={params} />}
      {method === 'mining.submit' && <MiningSubmit params={params} />}
      {method === 'mining.notify' && <MiningNotify params={params} />}
      {method === 'mining.set_difficulty' && <MiningSetDifficulty params={params} />}
      {method === 'mining.set_extranonce' && <MiningSetExtranonce params={params} />}

      {/* Paired Response (if exists) */}
      {response && (
        <div className="border-t-2 border-primary/20 pt-4">
          <div className="flex items-center gap-2 mb-3">
            <Badge variant="secondary">← Response</Badge>
            {responseTimestamp && (
              <span className="text-xs text-muted-foreground">
                {new Date(responseTimestamp).toLocaleTimeString()}.
                {new Date(responseTimestamp).getMilliseconds().toString().padStart(3, '0')}
              </span>
            )}
          </div>
          {response.result !== undefined && response.result !== null && (
            <ResponseResult result={response.result} method={method} />
          )}
          {response.error !== undefined && response.error !== null && (
            <ErrorResponse error={response.error} />
          )}
        </div>
      )}

      {/* Response with Result (for unpaired responses) */}
      {!response && result !== undefined && result !== null && <ResponseResult result={result} method={method} />}

      {/* Error Response (for unpaired error responses) */}
      {!response && error !== undefined && error !== null && <ErrorResponse error={error} />}

      {/* Unknown method - show generic params */}
      {method && !['mining.subscribe', 'mining.authorize', 'mining.submit', 'mining.notify', 'mining.set_difficulty', 'mining.set_extranonce'].includes(method) && params && (
        <GenericParams params={params} />
      )}
    </div>
  );
}

function MiningSubscribe({ params }: { params: any }) {
  if (!params || !Array.isArray(params)) return null;

  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="font-medium text-sm">Mining Subscribe Request</div>
      {params[0] && (
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1">User Agent</div>
          <div className="font-mono text-sm">{params[0]}</div>
        </div>
      )}
      {params[1] && (
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1">Session ID (Resume)</div>
          <div className="font-mono text-sm">{params[1]}</div>
        </div>
      )}
    </div>
  );
}

function MiningAuthorize({ params }: { params: any }) {
  if (!params || !Array.isArray(params)) return null;

  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="font-medium text-sm">Mining Authorize Request</div>
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1">Worker Name</div>
        <div className="font-mono text-sm">{params[0] || '-'}</div>
      </div>
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1">Password</div>
        <div className="font-mono text-sm">{params[1] ? '••••••••' : '-'}</div>
      </div>
    </div>
  );
}

function MiningSubmit({ params }: { params: any }) {
  if (!params || !Array.isArray(params)) return null;

  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="font-medium text-sm">Mining Submit (Share Submission)</div>
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1">Worker Name</div>
        <div className="font-mono text-sm">{params[0] || '-'}</div>
      </div>
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1">Job ID</div>
        <div className="font-mono text-sm">{params[1] || '-'}</div>
      </div>
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1">Extranonce2</div>
        <div className="font-mono text-sm break-all">{params[2] || '-'}</div>
      </div>
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1">Time</div>
        <div className="font-mono text-sm">{params[3] || '-'}</div>
      </div>
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1">Nonce</div>
        <div className="font-mono text-sm">{params[4] || '-'}</div>
      </div>
    </div>
  );
}

function MiningNotify({ params }: { params: any }) {
  if (!params || !Array.isArray(params)) return null;

  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="font-medium text-sm">Mining Notify (New Job)</div>
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1">Job ID</div>
        <div className="font-mono text-sm">{params[0] || '-'}</div>
      </div>
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1">Previous Block Hash</div>
        <div className="font-mono text-xs break-all">{params[1] || '-'}</div>
      </div>
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1">Coinbase Part 1</div>
        <div className="font-mono text-xs break-all">{params[2] || '-'}</div>
      </div>
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1">Coinbase Part 2</div>
        <div className="font-mono text-xs break-all">{params[3] || '-'}</div>
      </div>
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1">Merkle Branches</div>
        <div className="font-mono text-xs">
          {Array.isArray(params[4]) ? `[${params[4].length} branches]` : '-'}
        </div>
        {Array.isArray(params[4]) && params[4].length > 0 && (
          <div className="mt-1 pl-4 space-y-1 max-h-32 overflow-y-auto">
            {params[4].map((branch: string, idx: number) => (
              <div key={idx} className="text-xs break-all">{idx}: {branch}</div>
            ))}
          </div>
        )}
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1">Version</div>
          <div className="font-mono text-sm">{params[5] || '-'}</div>
        </div>
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1">nBits</div>
          <div className="font-mono text-sm">{params[6] || '-'}</div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1">nTime</div>
          <div className="font-mono text-sm">{params[7] || '-'}</div>
        </div>
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1">Clean Jobs</div>
          <Badge variant={params[8] ? 'destructive' : 'outline'}>
            {params[8] ? 'Yes (clear old jobs)' : 'No (can continue)'}
          </Badge>
        </div>
      </div>
    </div>
  );
}

function MiningSetDifficulty({ params }: { params: any }) {
  if (!params || !Array.isArray(params)) return null;

  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="font-medium text-sm">Set Difficulty</div>
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1">Difficulty</div>
        <div className="font-mono text-lg">{params[0] || '-'}</div>
      </div>
    </div>
  );
}

function MiningSetExtranonce({ params }: { params: any }) {
  if (!params || !Array.isArray(params)) return null;

  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="font-medium text-sm">Set Extranonce</div>
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1">Extranonce1</div>
        <div className="font-mono text-sm break-all">{params[0] || '-'}</div>
      </div>
      <div>
        <div className="text-xs font-medium text-muted-foreground mb-1">Extranonce2 Size</div>
        <div className="font-mono text-sm">{params[1] || '-'} bytes</div>
      </div>
    </div>
  );
}

function ResponseResult({ result, method }: { result: any; method?: string }) {
  // mining.subscribe response
  if (Array.isArray(result) && result.length >= 2 && method === 'mining.subscribe') {
    return (
      <div className="border rounded-lg p-4 space-y-3 bg-green-50 dark:bg-green-950">
        <div className="font-medium text-sm">Subscribe Response</div>
        {Array.isArray(result[0]) && (
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">Subscriptions</div>
            <div className="space-y-1">
              {result[0].map((sub: any, idx: number) => (
                <div key={idx} className="font-mono text-xs">
                  {Array.isArray(sub) ? `${sub[0]}: ${sub[1]}` : JSON.stringify(sub)}
                </div>
              ))}
            </div>
          </div>
        )}
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1">Extranonce1</div>
          <div className="font-mono text-sm break-all">{result[1] || '-'}</div>
        </div>
        {result[2] && (
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">Extranonce2 Size</div>
            <div className="font-mono text-sm">{result[2]} bytes</div>
          </div>
        )}
      </div>
    );
  }

  // Boolean result (authorize, submit)
  if (typeof result === 'boolean') {
    return (
      <div className="border rounded-lg p-4 bg-green-50 dark:bg-green-950">
        <div className="font-medium text-sm mb-2">Response</div>
        <Badge variant={result ? 'default' : 'destructive'}>
          {result ? '✓ Success' : '✗ Rejected'}
        </Badge>
      </div>
    );
  }

  // Generic result
  return (
    <div className="border rounded-lg p-4 bg-green-50 dark:bg-green-950">
      <div className="font-medium text-sm mb-2">Response Result</div>
      <pre className="text-xs font-mono overflow-auto">{JSON.stringify(result, null, 2)}</pre>
    </div>
  );
}

function ErrorResponse({ error }: { error: any }) {
  if (Array.isArray(error) && error.length >= 2) {
    return (
      <div className="border border-destructive rounded-lg p-4 bg-destructive/10">
        <div className="font-medium text-sm mb-2 text-destructive">Error Response</div>
        <div className="space-y-2">
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">Error Code</div>
            <div className="font-mono text-sm">{error[0]}</div>
          </div>
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-1">Error Message</div>
            <div className="font-mono text-sm">{error[1]}</div>
          </div>
          {error[2] && (
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-1">Additional Info</div>
              <div className="font-mono text-xs">{JSON.stringify(error[2])}</div>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="border border-destructive rounded-lg p-4 bg-destructive/10">
      <div className="font-medium text-sm mb-2 text-destructive">Error Response</div>
      <pre className="text-xs font-mono overflow-auto">{JSON.stringify(error, null, 2)}</pre>
    </div>
  );
}

function GenericParams({ params }: { params: any }) {
  return (
    <div className="border rounded-lg p-4 space-y-2">
      <div className="font-medium text-sm">Parameters</div>
      <pre className="text-xs font-mono overflow-auto">{JSON.stringify(params, null, 2)}</pre>
    </div>
  );
}

