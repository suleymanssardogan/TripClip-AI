# 🚀 TripClip AI

> Transform Instagram travel videos into organized itineraries with AI

[![Swift](https://img.shields.io/badge/Swift-5.9+-orange.svg)](https://swift.org)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

## 📱 What is TripClip AI?

TripClip AI is an AI-powered mobile application that analyzes Instagram travel videos and automatically generates optimized travel itineraries. Instead of saving countless videos that never turn into actual plans, users can share videos directly to our app and get instant, actionable travel plans.

### The Problem
- 📱 Users save hundreds of travel videos on Instagram
- 🤔 Videos remain disorganized and forgotten
- ⏰ Planning a trip from saved content is time-consuming
- 🗺️ No way to combine multiple videos into one coherent plan

### Our Solution
- 🎥 Share Instagram videos directly to TripClip AI
- 🤖 AI extracts locations, landmarks, and activities
- 🗺️ Generates optimized routes and timelines
- 💰 Provides budget estimates and recommendations
- 📅 Export to calendar, maps, or PDF

## ✨ Key Features

### AI-Powered Analysis
- **Computer Vision**: Detects landmarks and locations in video frames
- **Speech Recognition**: Extracts location names from audio (Whisper)
- **NLP/NER**: Identifies places, restaurants, and activities from captions
- **Route Optimization**: Calculates optimal visiting order using TSP algorithms

### Mobile Experience (iOS)
- Instagram Share Extension for seamless video sharing
- Interactive maps with route visualization
- Day-by-day itinerary timeline
- Budget calculator
- Calendar integration
- PDF export

### Smart Recommendations
- RAG-powered travel tips
- Similar location suggestions
- Weather-based recommendations
- Nearby hidden gems

## 🏗️ Architecture
```
┌─────────────────┐
│  Instagram App  │
└────────┬────────┘
         │ Share Extension
         ▼
┌─────────────────┐      ┌──────────────────┐
│   iOS App       │─────▶│  FastAPI Backend │
│   (Swift)       │◀─────│   (Python)       │
└─────────────────┘      └────────┬─────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              ┌──────────┐  ┌─────────┐  ┌──────────┐
              │ Computer │  │   NLP   │  │  Route   │
              │  Vision  │  │ Engine  │  │Optimizer │
              └──────────┘  └─────────┘  └──────────┘
                    │             │             │
                    └─────────────┼─────────────┘
                                  ▼
                          ┌───────────────┐
                          │ Qdrant Vector │
                          │   Database    │
                          └───────────────┘
```

## 🛠️ Tech Stack

### Backend (AI/ML Pipeline)
| Category | Technology |
|----------|-----------|
| **Framework** | FastAPI |
| **Language** | Python 3.11+ |
| **Computer Vision** | PyTorch, YOLOv8, Google Vision API |
| **Speech-to-Text** | OpenAI Whisper |
| **NLP** | HuggingFace Transformers, spaCy |
| **Vector DB** | Qdrant |
| **Database** | PostgreSQL (Supabase), MongoDB |
| **Cache** | Redis |
| **Queue** | Celery + RabbitMQ |
| **Deployment** | Docker, Railway |

### Mobile (iOS)
| Category | Technology |
|----------|-----------|
| **Language** | Swift 5.9+ |
| **UI Framework** | SwiftUI |
| **Maps** | MapKit |
| **Networking** | URLSession, Async/Await |
| **Storage** | CoreData |
| **Integration** | Share Extension, EventKit |

### External APIs
- Google Places API
- Google Maps Distance Matrix API
- OpenWeatherMap API

## 📂 Project Structure
```
TripClip-AI/
├── README.md
├── LICENSE
├── .gitignore
├── docker-compose.yml
├── docs/
│   ├── architecture.md
│   ├── api-documentation.md
│   ├── setup-guide.md
│   └── project-timeline.md
├── backend/
│   ├── README.md
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   ├── models/
│   │   ├── services/
│   │   └── ml/
│   └── tests/
├── mobile/
│   ├── README.md
│   ├── TripClipAI.xcodeproj
│   ├── TripClipAI/
│   │   ├── App/
│   │   ├── Views/
│   │   ├── ViewModels/
│   │   ├── Models/
│   │   └── Services/
│   └── TripClipAITests/
└── web/ (optional)
    ├── README.md
    ├── package.json
    └── src/
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Xcode 15.0+ (for iOS development)
- API Keys (Google Places, OpenWeather)

### Backend Setup
```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your API keys

# Start services with Docker
docker-compose up -d

# Run FastAPI server
uvicorn app.main:app --reload
```

API will be available at `http://localhost:8000`  
API Documentation: `http://localhost:8000/docs`

### Mobile Setup
```bash
# Navigate to mobile
cd mobile

# Open Xcode project
open TripClipAI.xcodeproj

# Configure API endpoint in Config.swift
# Run on simulator or device
```

## 📊 Development Timeline

This is a 12-week academic project for Software Engineering (3rd year).

| Week | Milestone |
|------|-----------|
| 1-2 | Backend infrastructure, video processing |
| 3-4 | Computer Vision pipeline |
| 5 | NLP & Speech recognition |
| 6 | Location enrichment & Vector DB |
| 7 | Route optimization |
| 8-9 | iOS app development |
| 10 | Backend optimization & caching |
| 11 | Web dashboard (optional) |
| 12 | Testing, deployment, documentation |

**Current Status**: Week 1 - Project Setup ✅

See [Project Timeline](docs/project-timeline.md) for detailed plan.

## 🎯 Milestones

- [x] Project planning and architecture
- [ ] Backend API infrastructure
- [ ] Computer Vision integration
- [ ] NLP pipeline
- [ ] Route optimization algorithm
- [ ] iOS app MVP
- [ ] Production deployment
- [ ] Public beta launch

## 📖 Documentation

- [Architecture Overview](docs/architecture.md)
- [API Documentation](docs/api-documentation.md)
- [Setup Guide](docs/setup-guide.md)
- [Contributing Guidelines](CONTRIBUTING.md)

## 🧪 Testing
```bash
# Backend tests
cd backend
pytest tests/ -v

# iOS tests
cd mobile
xcodebuild test -scheme TripClipAI -destination 'platform=iOS Simulator,name=iPhone 15'
```

## 🎓 Academic Context

**Student**: Süleyman Sardoğan  
**Institution**: Fırat University  
**Program**: Software Engineering (3rd Year)  
**Duration**: 12 weeks (March - June 2026)  
**Goal**: AI Engineer portfolio project

This project demonstrates:
- Multi-modal AI/ML systems
- Production-ready backend architecture
- Native mobile development
- Real-world problem solving
- End-to-end software engineering

## 🤝 Contributing

This is an academic project, but feedback and suggestions are welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- OpenAI Whisper for speech recognition
- HuggingFace for NLP models
- Google for Places & Maps APIs
- PyTorch community
- FastAPI framework

## 📧 Contact

**Süleyman Sardoğan**
- Email: sardogansuleyman04@gmail.com
- LinkedIn: [suleyman-sardogan](https://www.linkedin.com/in/suleyman-sardogan-369875286/)
- GitHub: [@suleymanssardogan](https://github.com/suleymanssardogan)

---

⭐ Star this repo if you find it interesting!

**Made with ❤️ and AI**

