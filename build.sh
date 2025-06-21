#!/bin/bash
# Census MCP Container Build Script

set -e

echo "🏗️  Building Census MCP Server Container"
echo "========================================"

# Check if vector DB exists and has content
if [ ! -d "data/vector_db" ] || [ ! "$(ls -A data/vector_db)" ]; then
    echo "❌ Vector database not found at data/vector_db/"
    echo ""
    echo "Build the vector database first:"
    echo "   cd knowledge-base/"
    echo "   python build-kb.py --output-dir ../data/vector_db"
    echo ""
    exit 1
fi

# Show vector DB stats
echo "✅ Vector database found:"
DB_SIZE=$(du -sh data/vector_db | cut -f1)
DB_FILES=$(find data/vector_db -type f | wc -l)
echo "   Size: $DB_SIZE"
echo "   Files: $DB_FILES"

# Check that vector DB looks valid
if [ ! -f "data/vector_db/chroma.sqlite3" ]; then
    echo "⚠️  Warning: Vector DB might be incomplete (no chroma.sqlite3 found)"
fi

echo ""
echo "🐳 Building Docker container (this will include the 85MB vector DB)..."

# Build container with vector DB baked in
docker build -t census-mcp:latest .

# Get final image size
IMAGE_SIZE=$(docker images census-mcp:latest --format "{{.Size}}")

echo ""
echo "✅ Build complete!"
echo "   Container size: $IMAGE_SIZE"
echo ""
echo "🚀 Usage:"
echo "  # Basic run (vector DB already included)"
echo "  docker run census-mcp:latest"
echo ""
echo "  # With Census API key for better rate limits"
echo "  docker run -e CENSUS_API_KEY=your_key census-mcp:latest"
echo ""
echo "  # With docker-compose"
echo "  docker-compose up"
echo ""
echo "📦 The container includes:"
echo "   ✓ Pre-built vector database (85MB)"
echo "   ✓ All R packages and dependencies"
echo "   ✓ Sentence transformer model cache"
