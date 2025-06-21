# Single-stage Dockerfile for Census MCP Server
FROM python:3.11-slim

# Install system dependencies including R
RUN apt-get update && apt-get install -y \
    r-base \
    r-base-dev \
    r-cran-dplyr \
    r-cran-jsonlite \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    libgdal-dev \
    libudunits2-dev \
    libproj-dev \
    libgeos-dev \
    libfontconfig1-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libfreetype6-dev \
    libpng-dev \
    libtiff5-dev \
    libjpeg-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install only tidycensus from CRAN (dplyr and jsonlite installed from apt)
RUN R -e "options(repos = c(CRAN = 'https://cloud.r-project.org/')); install.packages('tidycensus', dependencies=TRUE)"

# Verify all packages work
RUN R -e "library(jsonlite); library(dplyr); library(tidycensus); cat('All R packages loaded successfully\n')"

# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/

# Copy the pre-built vector database (85MB)
COPY data/vector_db/ ./data/vector_db/

# Set environment variables
ENV CENSUS_MCP_CONTAINER=true
ENV PYTHONPATH=/app/src
ENV R_EXECUTABLE=/usr/bin/Rscript

# Create non-root user
RUN useradd -m -u 1000 census && chown -R census:census /app
USER census

# Health check that actually works
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, '/app/src'); from utils.config import get_config; c = get_config(); print('OK')" || exit 1

# Default command
CMD ["python", "src/census_mcp_server.py"]