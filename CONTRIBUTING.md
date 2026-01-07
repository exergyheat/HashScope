# Contributing to HashScope

Thank you for your interest in contributing to HashScope!

## Development Setup

### Backend

```bash
cd backend
pip install -r requirements.txt

# Set required config
export POOL_HOST=stratum+tcp://your-test-pool.com
export POOL_PORT=3333

# Run tests
pytest -q

# Run in development
uvicorn hashscope.api.app:create_app --factory --reload
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

## Code Style

### Python
- Type hints required for all public functions
- Follow PEP 8
- Use `ruff` or `black` for formatting if available
- No blocking calls in async code

### TypeScript
- Strict mode enabled
- Use functional components with hooks
- Prefer composition over complex components

## Testing

All new features should include tests:

```bash
# Backend
cd backend
pytest -q

# Frontend
cd frontend
npm test  # (when tests are added)
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linters
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Architecture Guidelines

See [AGENTS.md](AGENTS.md) for detailed architecture documentation and guidelines.

### Key Principles

1. **Never modify message contents** (Iteration 1) - byte-for-byte relay
2. **Best-effort parsing** - parse errors should not crash the proxy
3. **Security first** - treat all input as untrusted
4. **Type safety** - use type hints and TypeScript strictly

## Iteration Planning

We follow a structured iteration approach:

- **Iteration 1 (current)**: Basic transparent proxy with visualization
- **Iteration 2 (future)**: Message routing and shadow miner support

See AGENTS.md for detailed requirements of each iteration.

## Questions?

Open an issue for any questions about contributing!

