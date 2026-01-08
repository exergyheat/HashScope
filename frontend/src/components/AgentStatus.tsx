import { useEffect, useState } from 'react';
import { Agent, api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export function AgentStatus() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    // Fetch initial agent list
    const fetchAgents = async () => {
      try {
        const agentList = await api.getAgents();
        setAgents(agentList);
      } catch (error) {
        console.error('Failed to fetch agents:', error);
      }
    };

    fetchAgents();

    // Connect to WebSocket for real-time updates
    const websocket = api.connectAgentsWebSocket((data) => {
      if (data.type === 'init') {
        setAgents(data.agents || []);
        setIsConnected(true);
      } else if (data.type === 'telemetry') {
        // Update agent in list
        setAgents((prevAgents) => {
          const agentIndex = prevAgents.findIndex((a) => a.agent_id === data.agent_id);
          if (agentIndex >= 0) {
            // Update existing agent
            const updatedAgents = [...prevAgents];
            updatedAgents[agentIndex] = {
              agent_id: data.agent_id,
              last_seen: data.data.ts,
              conn_state: data.data.conn_state,
              stats: data.data.stats,
              pool_target: data.data.pool_target,
            };
            return updatedAgents;
          } else {
            // Add new agent
            return [
              ...prevAgents,
              {
                agent_id: data.agent_id,
                last_seen: data.data.ts,
                conn_state: data.data.conn_state,
                stats: data.data.stats,
                pool_target: data.data.pool_target,
              },
            ];
          }
        });
      }
    });

    websocket.onopen = () => {
      setIsConnected(true);
    };

    websocket.onclose = () => {
      setIsConnected(false);
    };

    return () => {
      websocket.close();
    };
  }, []);

  const getStateColor = (state: string) => {
    switch (state) {
      case 'connected':
        return 'bg-green-600';
      case 'reconnecting':
        return 'bg-yellow-600';
      case 'error':
        return 'bg-red-600';
      default:
        return 'bg-gray-600';
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleTimeString();
  };

  // Filter out agents that haven't checked in for more than 1 minute
  const activeAgents = agents.filter((agent) => {
    const lastSeenTime = new Date(agent.last_seen).getTime();
    const now = Date.now();
    const secondsSinceLastSeen = (now - lastSeenTime) / 1000;
    return secondsSinceLastSeen < 60; // Only show agents that checked in within last 60 seconds
  });

  // Calculate aggregate rates across active agents only
  const aggregateRates = activeAgents.reduce(
    (acc, agent) => {
      if (agent.stats.submits_per_second_1min !== null) {
        acc.rate_1min += agent.stats.submits_per_second_1min;
      }
      if (agent.stats.submits_per_second_10sec !== null) {
        acc.rate_10sec += agent.stats.submits_per_second_10sec;
      }
      return acc;
    },
    { rate_1min: 0, rate_10sec: 0 }
  );

  const totalSubmits = activeAgents.reduce(
    (sum, agent) => sum + agent.stats.submits_attempted_total,
    0
  );

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Agent Fleet</CardTitle>
          <div className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full ${isConnected ? 'bg-green-600' : 'bg-red-600'}`} />
            <span className="text-sm text-muted-foreground">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>

        {/* Aggregate Stats */}
        {activeAgents.length > 0 && (
          <div className="mt-4 p-3 bg-muted rounded-lg">
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <div className="text-muted-foreground text-xs">Active Agents</div>
                <div className="font-semibold text-lg">{activeAgents.length}</div>
              </div>
              <div>
                <div className="text-muted-foreground text-xs">Total Submits</div>
                <div className="font-semibold text-lg">{totalSubmits.toLocaleString()}</div>
              </div>
              <div>
                <div className="text-muted-foreground text-xs">Aggregate Rate</div>
                <div className="font-mono font-semibold text-lg text-blue-600">
                  {aggregateRates.rate_1min.toFixed(2)} /s
                </div>
                <div className="text-xs text-muted-foreground font-mono">
                  (10s: {aggregateRates.rate_10sec.toFixed(2)} /s)
                </div>
              </div>
            </div>
          </div>
        )}
      </CardHeader>
      <CardContent>
        {activeAgents.length === 0 ? (
          <div className="text-center text-muted-foreground py-8">
            No active agents (agents auto-removed after 60s of inactivity)
          </div>
        ) : (
          <div className="space-y-4">
            {activeAgents.map((agent) => (
              <div
                key={agent.agent_id}
                className="border rounded-lg p-4 space-y-3"
              >
                {/* Agent Header */}
                <div className="flex items-center justify-between">
                  <div className="font-mono text-sm font-semibold">{agent.agent_id}</div>
                  <Badge className={getStateColor(agent.conn_state)}>
                    {agent.conn_state}
                  </Badge>
                </div>

                {/* Pool Target */}
                <div className="text-xs text-muted-foreground">
                  Pool: {agent.pool_target.host}:{agent.pool_target.port}
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <div className="text-muted-foreground text-xs">Shares Received</div>
                    <div className="font-semibold">{agent.stats.share_events_received_total}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground text-xs">Submits Attempted</div>
                    <div className="font-semibold">{agent.stats.submits_attempted_total}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground text-xs">Accepted</div>
                    <div className="font-semibold text-green-600">
                      {agent.stats.submits_accepted_total}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground text-xs">Rejected</div>
                    <div className="font-semibold text-red-600">
                      {agent.stats.submits_rejected_total}
                    </div>
                  </div>
                </div>

                {/* Submission Rates */}
                {(agent.stats.submits_per_second_1min !== null || agent.stats.submits_per_second_10sec !== null) && (
                  <div className="grid grid-cols-2 gap-2 text-xs border-t pt-2">
                    {agent.stats.submits_per_second_1min !== null && (
                      <div>
                        <span className="text-muted-foreground">Rate (1m):</span>{' '}
                        <span className="font-mono font-semibold">{agent.stats.submits_per_second_1min.toFixed(2)} /s</span>
                      </div>
                    )}
                    {agent.stats.submits_per_second_10sec !== null && (
                      <div>
                        <span className="text-muted-foreground">Rate (10s):</span>{' '}
                        <span className="font-mono font-semibold">{agent.stats.submits_per_second_10sec.toFixed(2)} /s</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Latency */}
                {agent.stats.last_submit_latency_ms !== null && (
                  <div className="text-xs">
                    <span className="text-muted-foreground">Last Submit Latency:</span>{' '}
                    <span className="font-mono">{agent.stats.last_submit_latency_ms.toFixed(2)} ms</span>
                  </div>
                )}

                {/* Last Seen */}
                <div className="text-xs text-muted-foreground">
                  Last seen: {formatDate(agent.last_seen)}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

