#!/bin/bash

echo "🚀 Creating TripClip AI project structure..."

# Docs klasörü
mkdir -p docs
touch docs/architecture.md
touch docs/api-documentation.md
touch docs/setup-guide.md
touch docs/project-timeline.md

# Backend klasörü
mkdir -p backend/app/{api/{routes,dependencies},models,services,ml,core}
mkdir -p backend/tests
mkdir -p backend/scripts

touch backend/README.md
touch backend/requirements.txt
touch backend/Dockerfile
touch backend/.env.example
touch backend/.gitignore
touch backend/docker-compose.yml

touch backend/app/__init__.py
touch backend/app/main.py
touch backend/app/config.py

touch backend/app/api/__init__.py
touch backend/app/api/dependencies.py
touch backend/app/api/routes/__init__.py
touch backend/app/api/routes/videos.py
touch backend/app/api/routes/plans.py
touch backend/app/api/routes/users.py

touch backend/app/models/__init__.py
touch backend/app/models/user.py
touch backend/app/models/video.py
touch backend/app/models/plan.py

touch backend/app/services/__init__.py
touch backend/app/services/video_processor.py
touch backend/app/services/ai_analyzer.py
touch backend/app/services/route_optimizer.py

touch backend/app/ml/__init__.py
touch backend/app/ml/computer_vision.py
touch backend/app/ml/nlp.py
touch backend/app/ml/embeddings.py
touch backend/app/ml/speech_to_text.py

touch backend/app/core/__init__.py
touch backend/app/core/database.py
touch backend/app/core/redis.py
touch backend/app/core/celery_app.py

# Mobile klasörü (placeholder, Xcode'da oluşacak)
mkdir -p mobile
touch mobile/README.md
touch mobile/.gitignore

# Web klasörü (opsiyonel)
mkdir -p web/src
touch web/README.md
touch web/package.json
touch web/.gitignore

# Root dosyalar
touch .gitignore
touch LICENSE
touch CONTRIBUTING.md
touch docker-compose.yml

echo "✅ Project structure created successfully!"
echo ""
echo "Next steps:"
echo "1. Fill in README files"
echo "2. Setup backend dependencies"
echo "3. Create Xcode project for mobile"
echo ""
