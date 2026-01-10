# HashScope Documentation

Welcome to the HashScope documentation! This folder contains all the documentation for HashScope, organized into separate markdown files for easy maintenance and reuse.

## Documentation Files

- **[overview.md](overview.md)** - Introduction to HashScope, key features, and use cases
- **[quickstart.md](quickstart.md)** - 5-minute setup guide to get started quickly
- **[architecture.md](architecture.md)** - System architecture and component details
- **[agent-fleet.md](agent-fleet.md)** - Distributed agent fleet and Nostr integration
- **[developer-guide.md](developer-guide.md)** - Development setup, coding standards, and workflows
- **[api-reference.md](api-reference.md)** - REST and WebSocket API documentation
- **[contributing.md](contributing.md)** - How to contribute to HashScope

## Viewing the Documentation

### Interactive Web UI

For the best experience, view the documentation in the HashScope web interface with interactive Mermaid diagrams:

1. Start HashScope: `docker compose up -d`
2. Open http://localhost:3000
3. Click the "Documentation" button in the header
4. Browse through the documentation with beautiful visualizations

### GitHub

You can also read these markdown files directly on GitHub or in your favorite markdown viewer.

### GitHub Pages

If you want to publish these docs to GitHub Pages:

1. Enable GitHub Pages in your repository settings
2. Set the source to the `/docs` folder
3. The documentation will be available at `https://yourusername.github.io/HashScope/`

## Maintaining the Documentation

These markdown files are the single source of truth for HashScope documentation. They are:

- Used by the frontend web UI (imported as raw text)
- Readable on GitHub
- Suitable for GitHub Pages
- Easy to edit and maintain

When updating documentation, simply edit the relevant `.md` file in this folder. The changes will automatically be reflected in:
- The web UI (after rebuilding the frontend)
- GitHub repository
- GitHub Pages (if enabled)

## License

Copyright © 2024 256 Foundation

