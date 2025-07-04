#!/usr/bin/env python3
"""
Auto-shard overly broad concept categories using clustering.
Based on Spock's design to fix education/economics over-matching.
"""

import json
import numpy as np
import argparse
from pathlib import Path
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from collections import Counter
import re

MODEL_NAME = "sentence-transformers/all-roberta-large-v1"
MIN_K, MAX_K = 2, 5  # try 2-5 clusters, pick best silhouette

def embed_texts(texts, model):
    """Embed list of texts using the model"""
    return model.encode(texts, batch_size=16, show_progress_bar=False)

def find_best_k(embeds):
    """Find optimal number of clusters using silhouette score"""
    if len(embeds) < MIN_K:
        return min(len(embeds), 2)
    
    best_k, best_score = 2, -1
    for k in range(MIN_K, min(MAX_K + 1, len(embeds))):
        try:
            km = KMeans(k, random_state=42, n_init=10)
            labels = km.fit_predict(embeds)
            score = silhouette_score(embeds, labels)
            if score > best_score:
                best_k, best_score = k, score
        except Exception as e:
            print(f"Warning: K={k} failed: {e}")
            continue
    return best_k

def extract_key_terms(concepts):
    """Extract key terms from concept labels for sub-category naming"""
    all_text = " ".join([c.get('label', '') for c in concepts])
    # Simple word frequency - could be more sophisticated
    words = re.findall(r'\b[a-zA-Z]{3,}\b', all_text.lower())
    word_counts = Counter(words)
    # Return most common non-generic words
    generic_words = {'the', 'and', 'for', 'with', 'this', 'that', 'from', 'they', 'have', 'been', 'their'}
    return [word for word, count in word_counts.most_common(5)
            if word not in generic_words]

def create_sub_category_name(category_name, cluster_idx, concepts):
    """Generate meaningful sub-category name"""
    key_terms = extract_key_terms(concepts)
    if key_terms:
        main_term = key_terms[0]
    else:
        main_term = f"group{cluster_idx + 1}"
    
    return f"{category_name}_{cluster_idx + 1}_{main_term}"

def split_category_concepts(ontology_data, category_name, model):
    """Split concepts for a specific category using clustering"""
    
    # Extract concepts for this category
    all_concepts = (ontology_data.get('approved_concepts', []) +
                   ontology_data.get('modified_concepts', []))
    
    category_concepts = [c for c in all_concepts
                        if c.get('category', '').lower() == category_name.lower()]
    
    if len(category_concepts) < 2:
        print(f"Category {category_name} has {len(category_concepts)} concepts - skipping")
        return category_concepts, []
    
    print(f"Splitting {category_name}: {len(category_concepts)} concepts")
    
    # Create texts for embedding
    texts = []
    for concept in category_concepts:
        text_parts = [
            concept.get('label', ''),
            concept.get('definition', ''),
            concept.get('universe', '')
        ]
        text = ' | '.join([part for part in text_parts if part])
        texts.append(text)
    
    # Embed and cluster
    embeds = embed_texts(texts, model)
    k = find_best_k(embeds)
    
    print(f"  Optimal clusters: {k}")
    
    if k == 1:
        return category_concepts, []
    
    # Perform clustering
    km = KMeans(k, random_state=42, n_init=10)
    labels = km.fit_predict(embeds)
    
    # Group concepts by cluster
    clusters = {i: [] for i in range(k)}
    for concept, label in zip(category_concepts, labels):
        clusters[label].append(concept)
    
    # Create new sub-categories
    new_categories = []
    original_concepts = []
    
    for cluster_idx, cluster_concepts in clusters.items():
        if len(cluster_concepts) == 0:
            continue
            
        # Create sub-category name
        sub_name = create_sub_category_name(category_name, cluster_idx, cluster_concepts)
        
        print(f"  Cluster {cluster_idx + 1}: {len(cluster_concepts)} concepts -> {sub_name}")
        
        # Create new category concept
        sample_concepts = cluster_concepts[:3]  # First 3 for preview
        sample_labels = [c.get('label', 'Unknown') for c in sample_concepts]
        
        new_category = {
            'label': sub_name,
            'definition': f"Auto-clustered {category_name} concepts: {', '.join(sample_labels)}...",
            'category': sub_name,  # Use the sub-name as the category
            'universe': 'Mixed',  # Could be more sophisticated
            'cluster_size': len(cluster_concepts),
            'cluster_index': cluster_idx,
            'source_category': category_name
        }
        
        new_categories.append(new_category)
        
        # Update original concepts to point to new sub-category
        for concept in cluster_concepts:
            updated_concept = concept.copy()
            updated_concept['category'] = sub_name
            updated_concept['original_category'] = category_name
            original_concepts.append(updated_concept)
    
    return original_concepts, new_categories

def split_ontology(input_file, categories_to_split, output_file=None, model_name=MODEL_NAME):
    """Split specified categories in the ontology"""
    
    # Load ontology
    with open(input_file, 'r') as f:
        ontology = json.load(f)
    
    # Load model
    print(f"Loading model: {model_name}")
    model = SentenceTransformer(model_name)
    
    # Track all concepts (split and unsplit)
    all_approved = []
    all_modified = []
    new_categories = []
    
    # Get concepts for categories we're NOT splitting
    original_approved = ontology.get('approved_concepts', [])
    original_modified = ontology.get('modified_concepts', [])
    
    # Categories to keep as-is
    keep_approved = [c for c in original_approved
                    if c.get('category', '').lower() not in [cat.lower() for cat in categories_to_split]]
    keep_modified = [c for c in original_modified
                    if c.get('category', '').lower() not in [cat.lower() for cat in categories_to_split]]
    
    all_approved.extend(keep_approved)
    all_modified.extend(keep_modified)
    
    # Split specified categories
    for category in categories_to_split:
        print(f"\n=== Splitting {category} ===")
        
        # Split this category
        split_concepts, category_definitions = split_category_concepts(ontology, category, model)
        
        # Add split concepts back (they could go into approved or modified based on original status)
        for concept in split_concepts:
            if any(c.get('label') == concept.get('label') for c in original_approved):
                all_approved.append(concept)
            else:
                all_modified.append(concept)
        
        # Store new category definitions
        new_categories.extend(category_definitions)
    
    # Create new ontology structure
    new_ontology = ontology.copy()
    new_ontology['approved_concepts'] = all_approved
    new_ontology['modified_concepts'] = all_modified
    new_ontology['split_categories'] = new_categories
    
    # Update metadata
    if 'metadata' in new_ontology:
        new_ontology['metadata']['split_timestamp'] = str(np.datetime64('now'))
        new_ontology['metadata']['categories_split'] = categories_to_split
        new_ontology['metadata']['new_subcategories'] = len(new_categories)
    
    # Save result
    if output_file is None:
        output_file = input_file.replace('.json', '_split.json')
    
    with open(output_file, 'w') as f:
        json.dump(new_ontology, f, indent=2)
    
    print(f"\n=== Results ===")
    print(f"Original concepts: {len(original_approved) + len(original_modified)}")
    print(f"Final concepts: {len(all_approved) + len(all_modified)}")
    print(f"New sub-categories created: {len(new_categories)}")
    print(f"Output saved to: {output_file}")
    
    # Print summary of new categories
    print(f"\nNew sub-categories:")
    for cat in new_categories:
        print(f"  {cat['label']}: {cat['cluster_size']} concepts")
    
    return output_file

def main():
    parser = argparse.ArgumentParser(description='Auto-shard overly broad concept categories')
    parser.add_argument('--input', default='COOS_Complete_Ontology.json',
                       help='Input ontology file (default: COOS_Complete_Ontology.json)')
    parser.add_argument('--output', help='Output file (default: input_split.json)')
    parser.add_argument('--categories', nargs='+', default=['education', 'economics'],
                       help='Categories to split (default: education economics)')
    parser.add_argument('--model', default=MODEL_NAME, help=f'Model to use (default: {MODEL_NAME})')
    
    args = parser.parse_args()
    
    # Use the model from args (don't modify global)
    model_name = args.model
    
    print(f"🔄 Auto-sharding broad categories")
    print(f"Input: {args.input}")
    print(f"Categories to split: {args.categories}")
    print(f"Model: {model_name}")
    
    if not Path(args.input).exists():
        print(f"Error: Input file {args.input} not found")
        return
    
    output_file = split_ontology(args.input, args.categories, args.output, model_name)
    
    print(f"\n✅ Splitting complete!")
    print(f"Next steps:")
    print(f"1. Backup original: mv {args.input} {args.input}.backup")
    print(f"2. Use split version: mv {output_file} {args.input}")
    print(f"3. Re-run weight extractor with threshold 0.11")

if __name__ == "__main__":
    main()
