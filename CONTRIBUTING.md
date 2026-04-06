# Contributing to PowerPulse

Contributions are welcome! This project is maintained by the community.

## How to Contribute

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/powerpulse.git
cd powerpulse

# Copy environment template
cp .env.example .env

# Install dependencies
cd frontend && npm install && cd ..
pip install -r requirements.txt
```

## Running Tests

```bash
# Run backend tests
docker compose run --rm api pytest tests/

# Run frontend tests
cd frontend && npm test
```

## Code Style

- Python: Follow PEP 8, use Black for formatting
- JavaScript/TypeScript: Follow project conventions, use ESLint

## Questions?

Open an issue for questions or discussions.
