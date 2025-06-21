#!/usr/bin/env python3
"""
Knowledge Base Vectorization Script
Processes source documents into ChromaDB vector database using OpenAI embeddings

DEPENDENCIES:
    pip install PyPDF2 beautifulsoup4 markdown chromadb openai tenacity

SETUP:
    export OPENAI_API_KEY="your_openai_api_key_here"

Usage:
    cd knowledge-base/
    python build-kb.py [--rebuild] [--test-mode]
    
Arguments:
    --rebuild: Force rebuild of existing vector DB
    --test-mode: Process only a subset of documents for testing
    --source-dir: Source documents directory (default: source-docs)
    --output-dir: Output vector database directory (default: vector-db)

Examples:
    # Test with subset of documents
    cd knowledge-base/
    python build-kb.py --test-mode
    
    # Full knowledge base build
    python build-kb.py
    
    # Force complete rebuild
    python build-kb.py --rebuild
    
Cost Estimate:
    Expected cost: $13-20 for ~900MB corpus using text-embedding-3-large
"""

import os
import sys
import json
import logging
import argparse
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
import time
import random
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Document processing imports
import PyPDF2
from bs4 import BeautifulSoup
import markdown
import re

# Vector DB and embeddings
import chromadb
from chromadb.config import Settings
import openai

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - KB-BUILD - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KnowledgeBaseBuilder:
    """
    Builds Census expertise knowledge base from source documents.
    
    Processes PDFs, HTML, markdown, and text files into a ChromaDB vector database
    using OpenAI embeddings for high-quality semantic search.
    """
    
    def __init__(self, source_dir: Path, output_dir: Path, test_mode: bool = False):
        """Initialize the knowledge base builder."""
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.test_mode = test_mode
        
        # OpenAI client
        self.openai_client = openai.OpenAI()
        
        # Document processing stats
        self.stats = {
            'files_processed': 0,
            'chunks_created': 0,
            'embedding_calls': 0,
            'total_tokens': 0,
            'errors': 0
        }
        
        # Initialize ChromaDB
        self._init_vector_db()
        
        logger.info(f"Knowledge base builder initialized")
        logger.info(f"Source directory: {self.source_dir}")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Test mode: {self.test_mode}")
    
    def _init_vector_db(self):
        """Initialize ChromaDB client and collection."""
        try:
            # Create output directory
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize ChromaDB client
            self.chroma_client = chromadb.PersistentClient(
                path=str(self.output_dir),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Create or get collection
            collection_name = "census_knowledge"
            try:
                self.collection = self.chroma_client.get_collection(collection_name)
                logger.info(f"Loaded existing collection: {collection_name}")
            except Exception:  # ChromaDB raises various exceptions for missing collections
                self.collection = self.chroma_client.create_collection(
                    name=collection_name,
                    metadata={"description": "Census expertise knowledge base"}
                )
                logger.info(f"Created new collection: {collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {str(e)}")
            raise
    
    def build_knowledge_base(self, rebuild: bool = False):
        """Main entry point to build the knowledge base."""
        
        logger.info("=" * 60)
        logger.info("BUILDING CENSUS KNOWLEDGE BASE")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        try:
            # Check if rebuild is needed
            if rebuild:
                logger.info("Rebuild requested - clearing existing collection")
                # Delete the collection and recreate it
                try:
                    self.chroma_client.delete_collection(self.collection.name)
                    logger.info("Deleted existing collection")
                except ValueError:
                    pass  # Collection doesn't exist
                except Exception as e:
                    logger.error(f"Failed to delete collection: {e}")
                    raise
                
                # Recreate the collection
                self.collection = self.chroma_client.create_collection(
                    name="census_knowledge",
                    metadata={"description": "Census expertise knowledge base"}
                )
                logger.info("Created fresh collection for rebuild")
            
            existing_count = self.collection.count()
            if existing_count > 0 and not rebuild:
                logger.info(f"Collection already has {existing_count} documents")
                response = input("Continue building? (y/n): ")
                if response.lower() != 'y':
                    logger.info("Build cancelled")
                    return
            
            # Process all source documents
            self._process_source_documents()
            
            # Generate build manifest
            self._generate_build_manifest()
            
            # Display final statistics
            build_time = time.time() - start_time
            self._display_final_stats(build_time)
            
            logger.info("=" * 60)
            logger.info("KNOWLEDGE BASE BUILD COMPLETE")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Knowledge base build failed: {str(e)}")
            raise
    
    def _process_source_documents(self):
        """Process all source documents by category."""
        
        # Define document categories and their priorities
        categories = {
            'tidycensus-complete': {'priority': 1, 'max_files': 50 if self.test_mode else None},
            'tigris-complete': {'priority': 2, 'max_files': 20 if self.test_mode else None},
            'census-r-book': {'priority': 1, 'max_files': 30 if self.test_mode else None},
            'census-methodology': {'priority': 1, 'max_files': 10 if self.test_mode else None},
            'variable-definitions': {'priority': 1, 'max_files': 15 if self.test_mode else None},
            'equity-guidance': {'priority': 1, 'max_files': 15 if self.test_mode else None},
            'geographic-reference': {'priority': 2, 'max_files': 10 if self.test_mode else None},
            'data-privacy': {'priority': 2, 'max_files': 5 if self.test_mode else None},
            'training-best-practices': {'priority': 1, 'max_files': 10 if self.test_mode else None}
        }
        
        # Process each category
        for category, config in categories.items():
            category_path = self.source_dir / category
            if category_path.exists():
                logger.info(f"Processing category: {category}")
                self._process_category(category_path, category, config)
            else:
                logger.warning(f"Category directory not found: {category}")
    
    def _process_category(self, category_path: Path, category_name: str, config: Dict):
        """Process all files in a document category."""
        
        files_processed = 0
        max_files = config.get('max_files')
        
        # Get all files in category (recursively)
        all_files = []
        for pattern in ['*.pdf', '*.html', '*.md', '*.txt', '*.Rmd']:
            all_files.extend(category_path.rglob(pattern))
        
        # Sort by priority (smaller files first for testing)
        if self.test_mode:
            all_files.sort(key=lambda f: f.stat().st_size)
        
        for file_path in all_files:
            if max_files and files_processed >= max_files:
                logger.info(f"Reached max files limit for {category_name}: {max_files}")
                break
            
            try:
                # Skip hidden files and directories
                if any(part.startswith('.') for part in file_path.parts):
                    continue
                
                # Skip very large files in test mode
                if self.test_mode and file_path.stat().st_size > 5 * 1024 * 1024:  # 5MB
                    logger.info(f"Skipping large file in test mode: {file_path.name}")
                    continue
                
                logger.info(f"Processing: {file_path.relative_to(self.source_dir)}")
                self._process_document(file_path, category_name)
                files_processed += 1
                
                # Rate limiting for OpenAI API
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error processing {file_path}: {str(e)}")
                self.stats['errors'] += 1
                continue
        
        logger.info(f"Completed category {category_name}: {files_processed} files processed")
    
    def _process_document(self, file_path: Path, category: str):
        """Process a single document into chunks and embeddings."""
        
        try:
            # Extract text based on file type
            if file_path.suffix.lower() == '.pdf':
                text = self._extract_pdf_text(file_path)
            elif file_path.suffix.lower() in ['.html', '.htm']:
                text = self._extract_html_text(file_path)
            elif file_path.suffix.lower() in ['.md', '.rmd']:
                text = self._extract_markdown_text(file_path)
            else:
                # Plain text
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
            
            if not text or len(text.strip()) < 100:
                logger.warning(f"Insufficient text extracted from {file_path.name}")
                return
            
            # Create chunks
            chunks = self._create_chunks(text, file_path, category)
            
            if not chunks:
                logger.warning(f"No chunks created from {file_path.name}")
                return
            
            # Generate embeddings and store
            self._store_chunks(chunks)
            
            self.stats['files_processed'] += 1
            logger.info(f"Processed {file_path.name}: {len(chunks)} chunks created")
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {str(e)}")
            raise
    
    def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF file."""
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text:  # Guard against None
                        text += f"\n--- Page {page_num + 1} ---\n{page_text}"
            return text
        except Exception as e:
            logger.error(f"PDF extraction failed for {file_path}: {str(e)}")
            return ""
    
    def _extract_html_text(self, file_path: Path) -> str:
        """Extract text from HTML file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()
            
            # Extract text
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text
        except Exception as e:
            logger.error(f"HTML extraction failed for {file_path}: {str(e)}")
            return ""
    
    def _extract_markdown_text(self, file_path: Path) -> str:
        """Extract text from Markdown file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                md_content = f.read()
            
            # Convert markdown to HTML then extract text
            html = markdown.markdown(md_content)
            soup = BeautifulSoup(html, 'html.parser')
            return soup.get_text()
        except Exception as e:
            logger.error(f"Markdown extraction failed for {file_path}: {str(e)}")
            return ""
    
    def _create_chunks(self, text: str, file_path: Path, category: str) -> List[Dict[str, Any]]:
        """Split document into chunks for embedding with robust size handling."""
        
        chunks = []
        
        # Clean text
        text = re.sub(r'\s+', ' ', text).strip()
        
        if len(text) < 100:
            return chunks
        
        # Optimized chunking strategy for technical documents
        chunk_size = 800      # Target size
        max_chunk_size = 1200 # Hard limit to stay under token limits  
        overlap = 200         # 25% overlap for context preservation
        
        # Multi-level splitting: paragraphs → sentences → words
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        chunk_num = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # If paragraph itself is too large, split by sentences
            if len(paragraph) > max_chunk_size:
                sentences = re.split(r'[.!?]+', paragraph)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    
                    # If sentence is still too large, split by words (last resort)
                    if len(sentence) > max_chunk_size:
                        words = sentence.split()
                        current_sentence = ""
                        
                        for word in words:
                            if len(current_sentence + " " + word) > max_chunk_size and current_sentence:
                                # Store the current sentence chunk
                                if len(current_sentence.strip()) > 100:
                                    chunks.append(self._create_chunk_metadata(
                                        current_sentence.strip(), 
                                        file_path, 
                                        category, 
                                        chunk_num
                                    ))
                                    chunk_num += 1
                                
                                # Start new chunk with overlap
                                overlap_words = current_sentence.split()[-20:]  # Last 20 words
                                current_sentence = " ".join(overlap_words) + " " + word
                            else:
                                current_sentence += " " + word if current_sentence else word
                        
                        # Add final sentence chunk
                        if len(current_sentence.strip()) > 100:
                            if len(current_chunk + " " + current_sentence) <= max_chunk_size:
                                current_chunk += " " + current_sentence if current_chunk else current_sentence
                            else:
                                # Store current chunk first
                                if len(current_chunk.strip()) > 100:
                                    chunks.append(self._create_chunk_metadata(
                                        current_chunk.strip(), 
                                        file_path, 
                                        category, 
                                        chunk_num
                                    ))
                                    chunk_num += 1
                                current_chunk = current_sentence
                    else:
                        # Normal sentence, try to add to current chunk
                        if len(current_chunk + " " + sentence) > chunk_size and current_chunk:
                            # Store current chunk
                            if len(current_chunk.strip()) > 100:
                                chunks.append(self._create_chunk_metadata(
                                    current_chunk.strip(), 
                                    file_path, 
                                    category, 
                                    chunk_num
                                ))
                                chunk_num += 1
                            
                            # Start new chunk with overlap
                            overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                            current_chunk = overlap_text + " " + sentence
                        else:
                            current_chunk += " " + sentence if current_chunk else sentence
            else:
                # Normal paragraph processing
                if len(current_chunk + " " + paragraph) > chunk_size and current_chunk:
                    # Store current chunk
                    if len(current_chunk.strip()) > 100:
                        chunks.append(self._create_chunk_metadata(
                            current_chunk.strip(), 
                            file_path, 
                            category, 
                            chunk_num
                        ))
                        chunk_num += 1
                    
                    # Start new chunk with overlap
                    overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                    current_chunk = overlap_text + " " + paragraph
                else:
                    current_chunk += " " + paragraph if current_chunk else paragraph
        
        # Add final chunk
        if len(current_chunk.strip()) > 100:
            # Ensure final chunk isn't too large
            if len(current_chunk) > max_chunk_size:
                # Split final chunk if needed
                words = current_chunk.split()
                while len(" ".join(words)) > max_chunk_size and len(words) > 10:
                    chunk_words = words[:len(words)//2]
                    chunks.append(self._create_chunk_metadata(
                        " ".join(chunk_words), 
                        file_path, 
                        category, 
                        chunk_num
                    ))
                    chunk_num += 1
                    words = words[len(words)//2:]
                
                if words:
                    chunks.append(self._create_chunk_metadata(
                        " ".join(words), 
                        file_path, 
                        category, 
                        chunk_num
                    ))
            else:
                chunks.append(self._create_chunk_metadata(
                    current_chunk.strip(), 
                    file_path, 
                    category, 
                    chunk_num
                ))
        
        return chunks
    
    def _create_chunk_metadata(self, text: str, file_path: Path, category: str, chunk_num: int) -> Dict[str, Any]:
        """Create metadata for a text chunk."""
        
        # Generate unique ID with full hash for better traceability
        content_hash = hashlib.md5(text.encode()).hexdigest()
        chunk_id = f"{file_path.stem}_{chunk_num}_{content_hash}"
        
        return {
            'id': chunk_id,
            'text': text,
            'metadata': {
                'source_file': str(file_path.relative_to(self.source_dir)),
                'category': category,
                'chunk_number': chunk_num,
                'file_name': file_path.name,
                'file_type': file_path.suffix,
                'text_length': len(text)
            }
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIError))
    )
    def _generate_embeddings_with_retry(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings with retry logic and rate limiting."""
        try:
            response = self.openai_client.embeddings.create(
                input=texts,
                model="text-embedding-3-large"
            )
            return [item.embedding for item in response.data]
        except openai.RateLimitError as e:
            logger.warning(f"Rate limit hit, backing off: {e}")
            raise
        except openai.APIError as e:
            logger.warning(f"API error, retrying: {e}")
            raise
    
    def _store_chunks(self, chunks: List[Dict[str, Any]]):
        """Generate embeddings and store chunks in ChromaDB."""
        
        if not chunks:
            return
        
        try:
            # Prepare data for batch processing
            texts = [chunk['text'] for chunk in chunks]
            chunk_ids = [chunk['id'] for chunk in chunks]
            metadatas = [chunk['metadata'] for chunk in chunks]
            
            # Generate embeddings using OpenAI
            logger.info(f"Generating embeddings for {len(texts)} chunks...")
            
            embeddings = []
            batch_size = 100  # OpenAI batch limit
            
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                
                # Skip any texts that are too long (fallback protection)
                safe_texts = []
                safe_ids = []
                safe_metadatas = []
                
                for j, text in enumerate(batch_texts):
                    if len(text) > 6000:  # Conservative token limit
                        logger.warning(f"Skipping oversized chunk: {len(text)} characters")
                        continue
                    safe_texts.append(text)
                    safe_ids.append(chunk_ids[i + j])
                    safe_metadatas.append(metadatas[i + j])
                
                if not safe_texts:
                    logger.warning(f"No valid chunks in batch {i//batch_size + 1}, skipping")
                    continue
                
                # Use retry mechanism for embeddings
                batch_embeddings = self._generate_embeddings_with_retry(safe_texts)
                embeddings.extend(batch_embeddings)
                
                # Store the safe chunks with matching IDs and metadata
                if batch_embeddings:
                    self.collection.add(
                        documents=safe_texts,
                        embeddings=batch_embeddings,
                        metadatas=safe_metadatas,
                        ids=safe_ids
                    )
                
                # Track usage (approximate since we're using retry)
                self.stats['embedding_calls'] += 1
                self.stats['total_tokens'] += len(' '.join(safe_texts).split())  # Rough estimate
                
                # Rate limiting
                time.sleep(0.5 + random.uniform(0, 0.5))  # Add jitter to avoid thundering herd
            
            # Count successful embeddings
            self.stats['chunks_created'] += len([e for e in embeddings if e])
            logger.info(f"Stored {len([e for e in embeddings if e])} valid chunks in vector database")
            
        except Exception as e:
            logger.error(f"Error storing chunks: {str(e)}")
            raise
    
    def _generate_build_manifest(self):
        """Generate build manifest with statistics and metadata."""
        
        manifest = {
            'build_timestamp': time.time(),
            'build_date': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
            'test_mode': self.test_mode,
            'stats': self.stats,
            'collection_info': {
                'name': self.collection.name,
                'document_count': self.collection.count(),
            },
            'openai_model': 'text-embedding-3-large',
            'source_directory': str(self.source_dir),
            'output_directory': str(self.output_dir)
        }
        
        # Save manifest
        manifest_path = self.output_dir / 'build_manifest.json'
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"Build manifest saved: {manifest_path}")
    
    def _display_final_stats(self, build_time: float):
        """Display final build statistics."""
        
        total_cost = (self.stats['total_tokens'] / 1000000) * 0.13  # $0.13 per 1M tokens
        
        logger.info("BUILD STATISTICS:")
        logger.info(f"  Files processed: {self.stats['files_processed']}")
        logger.info(f"  Chunks created: {self.stats['chunks_created']}")
        logger.info(f"  Embedding API calls: {self.stats['embedding_calls']}")
        logger.info(f"  Total tokens: {self.stats['total_tokens']:,}")
        logger.info(f"  Estimated cost: ${total_cost:.4f}")
        logger.info(f"  Build time: {build_time:.2f} seconds")
        logger.info(f"  Errors: {self.stats['errors']}")
        
        final_count = self.collection.count()
        logger.info(f"  Final collection size: {final_count} documents")

def main():
    """Main entry point."""
    
    parser = argparse.ArgumentParser(description='Build Census Knowledge Base')
    parser.add_argument('--rebuild', action='store_true', 
                       help='Force rebuild of existing vector DB')
    parser.add_argument('--test-mode', action='store_true',
                       help='Process only a subset of documents for testing')
    parser.add_argument('--source-dir', type=str, default='source-docs',
                       help='Source documents directory')
    parser.add_argument('--output-dir', type=str, default='vector-db',
                       help='Output vector database directory')
    
    args = parser.parse_args()
    
    # Check for OpenAI API key
    if not os.getenv('OPENAI_API_KEY'):
        logger.error("OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    
    # Validate source directory
    source_dir = Path(args.source_dir)
    if not source_dir.exists():
        logger.error(f"Source directory not found: {source_dir}")
        sys.exit(1)
    
    # Build knowledge base
    try:
        builder = KnowledgeBaseBuilder(
            source_dir=source_dir,
            output_dir=Path(args.output_dir),
            test_mode=args.test_mode
        )
        
        builder.build_knowledge_base(rebuild=args.rebuild)
        
        logger.info("Knowledge base build completed successfully!")
        
    except KeyboardInterrupt:
        logger.info("Build interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Build failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()


def test_smoke_build_pipeline():
    """
    Smoke test: verify document processing and chunking without OpenAI calls.
    Run with: python -c "from build_kb import test_smoke_build_pipeline; test_smoke_build_pipeline()"
    """
    import tempfile
    
    # Create temporary directories
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_dir = temp_path / "test_source"
        output_dir = temp_path / "test_output"
        
        # Create test category and document
        test_category = source_dir / "test_category"
        test_category.mkdir(parents=True)
        
        test_file = test_category / "test_doc.md"
        test_content = """# Test Document
        
This is a test document for the knowledge base builder.
It contains multiple paragraphs to test chunking and text extraction.

## Section 1
This section has some content about testing the document processing pipeline.
The chunking algorithm should split this appropriately into manageable pieces.

## Section 2  
This is another section with different content for testing purposes.
It should create separate chunks for better retrieval and processing.

## Section 3
Additional content to ensure we have enough text for multiple chunks.
This helps verify that the chunking logic is working correctly.
"""
        test_file.write_text(test_content)
        
        try:
            # Test just the processing pipeline without embeddings
            builder = KnowledgeBaseBuilder(
                source_dir=source_dir,
                output_dir=output_dir, 
                test_mode=True
            )
            
            # Test text extraction
            extracted_text = builder._extract_markdown_text(test_file)
            assert len(extracted_text) > 100, f"Insufficient text extracted: {len(extracted_text)} chars"
            
            # Test chunking
            chunks = builder._create_chunks(extracted_text, test_file, "test_category")
            assert len(chunks) > 0, f"No chunks created from {len(extracted_text)} chars of text"
            assert all(len(chunk['text']) >= 100 for chunk in chunks), "Some chunks are too small"
            
            # Test metadata creation
            for i, chunk in enumerate(chunks):
                assert 'id' in chunk, f"Chunk {i} missing ID"
                assert 'text' in chunk, f"Chunk {i} missing text"
                assert 'metadata' in chunk, f"Chunk {i} missing metadata"
                assert chunk['metadata']['category'] == 'test_category', f"Wrong category in chunk {i}"
            
            print("✅ Smoke test passed!")
            print(f"   Text extracted: {len(extracted_text)} characters")
            print(f"   Chunks created: {len(chunks)}")
            print(f"   Average chunk size: {sum(len(c['text']) for c in chunks) // len(chunks)} chars")
            print(f"   Sample chunk ID: {chunks[0]['id'][:50]}...")
            
        except Exception as e:
            print(f"❌ Smoke test failed: {e}")
            raise
