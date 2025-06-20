#!/bin/bash
# Knowledge Base Cleanup Script
# Removes web scraping artifacts and unnecessary files from source documents
# Keeps only content files needed for vectorization

# USAGE:
#   cd knowledge-base/
#   chmod +x kb-cleanup.sh
#   ./kb-cleanup.sh
#
# This script will:
#   - Clean up source-docs/ directory (default)
#   - Remove web assets (CSS, JS, images, fonts)
#   - Delete common junk directories
#   - Clean up temporary/cache files
#   - Preserve all text content (PDF, HTML, MD, TXT)
#   - Show before/after size comparison
#   - Create cleanup manifest for transparency

set -e  # Exit on any error

SOURCE_DIR="${1:-source-docs}"
CLEANUP_DATE=$(date +"%Y-%m-%d %H:%M:%S")

echo "🧹 Knowledge Base Cleanup Script"
echo "==============================="
echo "Target directory: $SOURCE_DIR"
echo "Cleanup date: $CLEANUP_DATE"
echo ""

# Validate source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "❌ ERROR: Source directory not found: $SOURCE_DIR"
    echo "Make sure you're running this from the knowledge-base/ directory"
    echo "Usage: $0 [source-directory]"
    exit 1
fi

# Get initial size
echo "📊 Calculating initial size..."
INITIAL_SIZE=$(du -sh "$SOURCE_DIR" | cut -f1)
INITIAL_BYTES=$(du -sb "$SOURCE_DIR" | cut -f1)
echo "Initial size: $INITIAL_SIZE"
echo ""

# Change to source directory
cd "$SOURCE_DIR"

echo "🗑️  Removing web assets and junk files..."

#############################################################################
# Remove Web Assets
#############################################################################
echo "  → Removing CSS files..."
find . -name "*.css" -type f -delete 2>/dev/null || true

echo "  → Removing JavaScript files..."
find . -name "*.js" -type f -delete 2>/dev/null || true

echo "  → Removing image files..."
find . -name "*.png" -type f -delete 2>/dev/null || true
find . -name "*.jpg" -type f -delete 2>/dev/null || true
find . -name "*.jpeg" -type f -delete 2>/dev/null || true
find . -name "*.gif" -type f -delete 2>/dev/null || true
find . -name "*.svg" -type f -delete 2>/dev/null || true
find . -name "*.ico" -type f -delete 2>/dev/null || true
find . -name "*.webp" -type f -delete 2>/dev/null || true

echo "  → Removing font files..."
find . -name "*.woff" -type f -delete 2>/dev/null || true
find . -name "*.woff2" -type f -delete 2>/dev/null || true
find . -name "*.ttf" -type f -delete 2>/dev/null || true
find . -name "*.otf" -type f -delete 2>/dev/null || true
find . -name "*.eot" -type f -delete 2>/dev/null || true

#############################################################################
# Remove Common Junk Directories
#############################################################################
echo "  → Removing asset directories..."
find . -name "_static" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "assets" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "images" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "img" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "css" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "js" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "fonts" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "media" -type d -exec rm -rf {} + 2>/dev/null || true

#############################################################################
# Remove Cache and Temporary Files
#############################################################################
echo "  → Removing cache and temporary files..."
find . -name ".DS_Store" -type f -delete 2>/dev/null || true
find . -name "Thumbs.db" -type f -delete 2>/dev/null || true
find . -name "*.tmp" -type f -delete 2>/dev/null || true
find . -name "*.cache" -type f -delete 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

#############################################################################
# Remove Common Web Framework Files
#############################################################################
echo "  → Removing web framework files..."
find . -name "*.map" -type f -delete 2>/dev/null || true  # Source maps
find . -name "manifest.json" -type f -delete 2>/dev/null || true
find . -name "service-worker.js" -type f -delete 2>/dev/null || true
find . -name "sw.js" -type f -delete 2>/dev/null || true

#############################################################################
# Remove Empty Directories
#############################################################################
echo "  → Removing empty directories..."
find . -type d -empty -delete 2>/dev/null || true

#############################################################################
# Clean up specific scraping artifacts
#############################################################################
echo "  → Removing wget artifacts..."
find . -name "robots.txt*" -type f -delete 2>/dev/null || true
find . -name "*.orig" -type f -delete 2>/dev/null || true

# Remove common scraping artifacts from Census Reporter
echo "  → Removing Census Reporter artifacts..."
find . -path "*/censusreporter.org*" -name "*.json" -type f -delete 2>/dev/null || true

# Remove query parameters from filenames
echo "  → Cleaning up query parameter files..."
find . -name "*\?*" -type f | while read file; do
    newname=$(echo "$file" | sed 's/\?.*$//')
    if [ "$file" != "$newname" ] && [ ! -f "$newname" ]; then
        mv "$file" "$newname" 2>/dev/null || true
    else
        rm "$file" 2>/dev/null || true
    fi
done

cd - > /dev/null

#############################################################################
# Calculate final size and savings
#############################################################################
echo ""
echo "📊 Calculating final size..."
FINAL_SIZE=$(du -sh "$SOURCE_DIR" | cut -f1)
FINAL_BYTES=$(du -sb "$SOURCE_DIR" | cut -f1)

# Calculate savings
SAVED_BYTES=$((INITIAL_BYTES - FINAL_BYTES))
SAVED_MB=$((SAVED_BYTES / 1024 / 1024))
SAVED_PERCENT=$(( (SAVED_BYTES * 100) / INITIAL_BYTES ))

echo "Final size: $FINAL_SIZE"
echo "Space saved: ${SAVED_MB}MB (${SAVED_PERCENT}%)"
echo ""

#############################################################################
# Generate cleanup manifest
#############################################################################
echo "📋 Generating cleanup manifest..."

cat > "$SOURCE_DIR/cleanup_manifest.md" << EOF
# Knowledge Base Cleanup Manifest

**Cleanup Date**: $CLEANUP_DATE  
**Cleanup Script**: kb-cleanup.sh

## Size Reduction Summary
- **Initial Size**: $INITIAL_SIZE
- **Final Size**: $FINAL_SIZE  
- **Space Saved**: ${SAVED_MB}MB (${SAVED_PERCENT}%)

## Files Removed
- CSS stylesheets (*.css)
- JavaScript files (*.js)
- Image files (*.png, *.jpg, *.gif, *.svg, *.ico, *.webp)
- Font files (*.woff, *.woff2, *.ttf, *.otf, *.eot)
- Asset directories (_static, assets, images, css, js, fonts, media)
- Cache and temporary files (.DS_Store, Thumbs.db, *.tmp, *.cache)
- Web framework files (*.map, manifest.json, service-worker.js)
- Scraping artifacts (robots.txt, query parameters)
- Empty directories

## Files Preserved
- PDF documents (*.pdf)
- HTML content files (*.html, *.htm)
- Markdown files (*.md, *.rmd)
- Text files (*.txt)
- JSON data files (Census API responses)
- All R package documentation
- All authoritative source documents

## Verification
To verify no important content was removed:
1. Check that all PDF files are still present
2. Verify HTML files contain text content
3. Confirm R package documentation is intact
4. Test that build-kb.py processes files correctly

## Recovery
If important files were accidentally removed:
1. Re-run download-sources.sh to restore all sources
2. Apply selective cleanup as needed
3. Consider updating this script's exclusion patterns
EOF

echo "✅ Cleanup manifest generated: $SOURCE_DIR/cleanup_manifest.md"

#############################################################################
# Summary and recommendations
#############################################################################
echo ""
echo "🎉 Cleanup Complete!"
echo "==================="
echo ""
echo "📊 Summary:"
echo "  • Initial size: $INITIAL_SIZE"
echo "  • Final size: $FINAL_SIZE"
echo "  • Space saved: ${SAVED_MB}MB (${SAVED_PERCENT}%)"
echo ""
echo "✅ Preserved Content:"
echo "  • All PDF documents"
echo "  • All HTML text content"  
echo "  • All Markdown files"
echo "  • All R package documentation"
echo "  • All authoritative sources"
echo ""
echo "🗑️  Removed Junk:"
echo "  • Web assets (CSS, JS, images, fonts)"
echo "  • Cache and temporary files"
echo "  • Empty directories"
echo "  • Scraping artifacts"
echo ""
echo "📋 Next Steps:"
echo "  1. Review cleanup_manifest.md"
echo "  2. Run: python build-kb.py --test-mode"
echo "  3. If test passes: python build-kb.py"
echo ""
echo "🚀 Knowledge base ready for vectorization!"
