# Contributing to FireWatch AI

Thank you for your interest in contributing to FireWatch AI! This project aims to detect wildfires faster and save lives through open-source technology.

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- A NASA FIRMS API key ([Get one free](https://firms.modaps.eosdis.nasa.gov/api/area/))

### Development Setup

1. **Fork the repository**
   
   Click the "Fork" button on GitHub

2. **Clone your fork**
   ```bash
   git clone https://github.com/YOUR_USERNAME/FireWatch-AI.git
   cd FireWatch-AI
   ```

3. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or: venv\Scripts\activate  # Windows
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your FIRMS_API_KEY
   ```

6. **Run tests**
   ```bash
   pytest
   ```

## 📝 How to Contribute

### Reporting Bugs

- Check existing issues first
- Use the bug report template
- Include steps to reproduce
- Include error messages and logs

### Suggesting Features

- Check existing feature requests
- Explain the use case
- Consider implementation complexity

### Submitting Code

1. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or: git checkout -b fix/bug-description
   ```

2. **Make your changes**
   - Follow the code style (Black, isort)
   - Add tests for new features
   - Update documentation

3. **Format and lint**
   ```bash
   black src tests
   isort src tests
   mypy src
   ```

4. **Run tests**
   ```bash
   pytest --cov=src
   ```

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add: brief description of changes"
   ```
   
   Commit message prefixes:
   - `Add:` New feature
   - `Fix:` Bug fix
   - `Update:` Improvement to existing feature
   - `Docs:` Documentation only
   - `Refactor:` Code restructuring
   - `Test:` Test additions/changes

6. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then open a Pull Request on GitHub.

## 🎯 Areas We Need Help

### High Priority
- [ ] Unit tests for FIRMS client
- [ ] API endpoint tests
- [ ] Docker configuration
- [ ] CI/CD pipeline (GitHub Actions)

### Medium Priority
- [ ] Weather data integration (Open-Meteo)
- [ ] Email alert system
- [ ] User authentication
- [ ] Rate limiting

### Future
- [ ] ML model for smoke detection
- [ ] Mobile app (React Native or PWA)
- [ ] Multi-language support

## 📐 Code Style

- **Python**: We use Black (line length 100) and isort
- **Type hints**: Required for all public functions
- **Docstrings**: Google style
- **Tests**: pytest with >80% coverage goal

Example:
```python
def process_hotspots(
    hotspots: list[FireHotspot],
    min_confidence: str = "n",
) -> list[FireHotspot]:
    """
    Filter hotspots by minimum confidence level.
    
    Args:
        hotspots: List of fire hotspot detections
        min_confidence: Minimum confidence ("l", "n", or "h")
        
    Returns:
        Filtered list of hotspots
        
    Raises:
        ValueError: If min_confidence is invalid
    """
    ...
```

## 🤝 Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- No harassment or discrimination

## 📫 Questions?

- Open a Discussion on GitHub
- Tag maintainers in issues

---

Thank you for helping make wildfire detection better! 🔥🌍
