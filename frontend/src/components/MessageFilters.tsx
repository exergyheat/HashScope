import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

interface MessageFiltersProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  directionFilter: 'all' | 'miner_to_pool' | 'pool_to_miner';
  onDirectionFilterChange: (filter: 'all' | 'miner_to_pool' | 'pool_to_miner') => void;
  showErrorsOnly: boolean;
  onShowErrorsOnlyChange: (show: boolean) => void;
}

export function MessageFilters({
  searchQuery,
  onSearchChange,
  directionFilter,
  onDirectionFilterChange,
  showErrorsOnly,
  onShowErrorsOnlyChange,
}: MessageFiltersProps) {
  return (
    <div className="flex flex-wrap gap-3 items-center">
      <Input
        type="search"
        placeholder="Search messages..."
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
        className="max-w-xs"
      />

      <div className="flex gap-2">
        <Button
          variant={directionFilter === 'all' ? 'default' : 'outline'}
          size="sm"
          onClick={() => onDirectionFilterChange('all')}
        >
          All
        </Button>
        <Button
          variant={directionFilter === 'miner_to_pool' ? 'default' : 'outline'}
          size="sm"
          onClick={() => onDirectionFilterChange('miner_to_pool')}
        >
          Miner → Pool
        </Button>
        <Button
          variant={directionFilter === 'pool_to_miner' ? 'default' : 'outline'}
          size="sm"
          onClick={() => onDirectionFilterChange('pool_to_miner')}
        >
          Pool → Miner
        </Button>
      </div>

      <Button
        variant={showErrorsOnly ? 'destructive' : 'outline'}
        size="sm"
        onClick={() => onShowErrorsOnlyChange(!showErrorsOnly)}
      >
        {showErrorsOnly ? 'Showing Errors Only' : 'Show All'}
      </Button>
    </div>
  );
}

