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
- Structured logging preferred

### TypeScript
- Strict mode enabled
- Use functional components with hooks
- Prefer composition over complex components
- Follow existing component patterns

## Testing

All new features should include tests:

```bash
# Backend
cd backend
pytest -q

# Frontend lint
cd frontend
npm run lint
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

### Key Principles

1. **Never modify message contents** - byte-for-byte relay
2. **Best-effort parsing** - parse errors should not crash the proxy
3. **Security first** - treat all input as untrusted
4. **Type safety** - use type hints and TypeScript strictly
5. **Nostr publishing never blocks relay** - background tasks only

### Development Approach

HashScope is built in phases:

- **Core Proxy**: Transparent proxy with real-time visualization
- **Distributed Testing**: Agent fleet with Nostr coordination for load testing
- **Future Enhancements**: Additional protocol support, persistent storage, authentication

## Code Review

All submissions require review. We look for:

- Code quality and style consistency
- Test coverage
- Documentation updates
- Performance considerations
- Security implications

## Reporting Issues

When reporting issues, include:

- HashScope version
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs
- System information (OS, Docker version, etc.)

## Feature Requests

We welcome feature requests! Please:

- Check existing issues first
- Describe the use case
- Explain expected behavior
- Consider implementation complexity

## Questions?

Open an issue for any questions about contributing!

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License).

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

Copyright © 2024 256 Foundation

