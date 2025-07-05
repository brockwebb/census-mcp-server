#!/usr/bin/env python3
"""
Spatial Topology Discovery - COMPLETE FUNCTIONALITY RESTORED
Generate embeddings from enriched variables and discover spatial topology with full visualization suite
"""

import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import logging
from datetime import datetime
from typing import Dict, List, Any, Tuple
import warnings
import argparse
warnings.filterwarnings('ignore')

# Core ML libraries
from sentence_transformers import SentenceTransformer
from sklearn.cluster import HDBSCAN
import umap
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SpatialTopologyDiscovery:
    def __init__(self, output_dir="../spatial_topology_discovery/topology_results", coos_concepts_dir=None):
        self.topology_path = Path(output_dir)
        self.topology_path.mkdir(parents=True, exist_ok=True)
        
        # Load COOS category mappings if provided
        self.coos_categories = {}
        if coos_concepts_dir:
            self.coos_categories = self._load_coos_category_mappings(coos_concepts_dir)
            logger.info(f"✅ Loaded COOS category mappings for {len(self.coos_categories)} variables")
        
        # Initialize embedding model
        logger.info("🤖 Loading sentence transformer model...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("✅ Model loaded successfully")
        
        # Spatial topology parameters
        self.umap_params = {
            'n_neighbors': 15,
            'min_dist': 0.1,
            'n_components': 3,  # 3D for visualization
            'metric': 'cosine',
            'random_state': 42
        }
        
        # HDBSCAN parameters - THE MISSING PIECE THAT STARTED THIS MESS
        self.hdbscan_params = {
            'min_cluster_size': 10,
            'min_samples': 5,
            'metric': 'euclidean',
            'cluster_selection_epsilon': 0.1
        }
    
    def _load_coos_category_mappings(self, concepts_dir: str) -> Dict[str, str]:
        """Load COOS category mappings from concept files"""
        concepts_path = Path(concepts_dir)
        category_mappings = {}
        
        # Map of concept files to categories
        category_files = {
            'core_demographics.json': 'core_demographics',
            'economics.json': 'economics',
            'education.json': 'education',
            'geography.json': 'geography',
            'health_social.json': 'health_social',
            'housing.json': 'housing',
            'specialized_populations.json': 'specialized_populations',
            'transportation.json': 'transportation'
        }
        
        for filename, category in category_files.items():
            file_path = concepts_path / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    
                    concepts = data.get('concepts', [])
                    for concept in concepts:
                        census_tables = concept.get('census_tables', [])
                        for table_id in census_tables:
                            # Map table prefixes to categories
                            category_mappings[table_id] = category
                
                except Exception as e:
                    logger.warning(f"Could not load {filename}: {e}")
                    
        return category_mappings
    
    def _assign_coos_category(self, variable_id: str) -> str:
        """Assign COOS category to a variable, or 'uncategorized' if not found"""
        
        # Direct mapping first
        if variable_id in self.coos_categories:
            return self.coos_categories[variable_id]
        
        # Try table family prefix matching
        for table_prefix, category in self.coos_categories.items():
            if variable_id.startswith(table_prefix):
                return category
        
        return 'uncategorized'

    def load_enriched_data(self, input_file: str, sample_size: int = None) -> pd.DataFrame:
        """Load enriched variable data and prepare for topology discovery"""
        
        logger.info(f"📊 Loading enriched data from {input_file}...")
        
        with open(input_file, 'r') as f:
            raw_data = json.load(f)
        
        # Handle the correct nested structure
        if 'variables' in raw_data:
            enriched_data = raw_data['variables']
            logger.info(f"✅ Found variables container with {len(enriched_data)} variables")
        elif isinstance(raw_data, dict) and any(key.startswith('B') for key in list(raw_data.keys())[:5]):
            # Direct variable dict (no container)
            enriched_data = raw_data
            logger.info(f"✅ Direct variable dict with {len(enriched_data)} variables")
        else:
            raise ValueError(f"Unrecognized data structure. Top-level keys: {list(raw_data.keys())}")
        
        # Convert to DataFrame with standardized structure
        records = []
        for var_id, data in enriched_data.items():
            record = self._standardize_enriched_record(var_id, data)
            if record:
                records.append(record)
        
        logger.info(f"✅ Processed {len(records)} valid records")
        
        df = pd.DataFrame(records)
        
        # Sample if requested
        if sample_size and len(df) > sample_size:
            logger.info(f"📌 Sampling {sample_size} variables from {len(df)} total")
            df = df.sample(n=sample_size, random_state=42).reset_index(drop=True)
        
        logger.info(f"🎯 Ready to analyze {len(df)} variables")
        
        return df
    def _standardize_enriched_record(self, var_id: str, data: Dict) -> Dict:
        """Standardize enriched record format for consistent processing"""
        
        # Handle COOS enriched format (what you actually have)
        if isinstance(data, dict):
            # Extract key fields with fallbacks
            record = {
                'variable_id': var_id,
                'table_family': var_id[:3] if len(var_id) >= 3 else 'Unknown',
                'survey': 'ACS',
                'complexity': 'medium'
            }
            
            # Extract rich information from agent responses
            agent_details = data.get('metadata', {}).get('agent_details', [])
            if agent_details:
                # Get the first (usually most detailed) agent response
                primary_response = agent_details[0].get('response', '')
                
                # Extract concept from the detailed analysis
                if 'Table B' in primary_response:
                    # Try to extract table description
                    lines = primary_response.split('\n')
                    for line in lines:
                        if 'Table B' in line and 'details' in line.lower():
                            record['concept'] = line.strip()[:100] + '...'
                            break
                        elif var_id in line:
                            record['concept'] = line.strip()[:100] + '...'
                            break
                    else:
                        record['concept'] = f"Census variable {var_id} analysis"
                else:
                    record['concept'] = f"Occupation/demographic analysis for {var_id}"
                
                # Extract meaningful label from analysis
                if 'Hispanic or Latino' in primary_response:
                    record['label'] = 'Hispanic/Latino demographic variable'
                elif 'occupation' in primary_response.lower():
                    record['label'] = 'Occupation classification variable'
                elif 'management, business, science' in primary_response:
                    record['label'] = 'Professional occupations variable'
                else:
                    record['label'] = f"ACS variable {var_id}"
                
                # Use the full response as enrichment text
                record['enrichment_text'] = primary_response[:500] + '...' if len(primary_response) > 500 else primary_response
            else:
                # Fallback for missing agent details
                record['label'] = f"Variable {var_id}"
                record['concept'] = "Census demographic variable"
                record['enrichment_text'] = ""
            
            # Add agreement metrics if available
            record['agreement_score'] = float(data.get('agreement_score', 0.5))
            record['final_confidence'] = float(data.get('agreement_score', 0.5))
            
            # Add COOS category - THE WHOLE POINT OF THIS EXERCISE
            record['coos_category'] = self._assign_coos_category(record['variable_id'])
            
            return record
        
        return None
    
    def create_embedding_text(self, row: pd.Series) -> str:
        """Create comprehensive text for embedding generation"""
        
        # Start with basic variable info
        text_parts = [
            f"Variable {row['variable_id']}: {row['label']}",
            f"Concept: {row['concept']}",
            f"Table Family: {row['table_family']}",
            f"Survey: {row['survey']}",
            f"Complexity: {row['complexity']}"
        ]
        
        # Add enrichment text
        if 'enrichment_text' in row and pd.notna(row['enrichment_text']):
            text_parts.append(f"Analysis: {row['enrichment_text']}")
        
        return " | ".join(text_parts)
    
    def generate_embeddings(self, df: pd.DataFrame) -> np.ndarray:
        """Generate sentence embeddings for all variables"""
        
        logger.info("🎯 Generating embeddings from enriched descriptions...")
        
        # Create embedding texts
        embedding_texts = df.apply(self.create_embedding_text, axis=1).tolist()
        
        # Generate embeddings
        embeddings = self.embedding_model.encode(
            embedding_texts,
            show_progress_bar=True,
            batch_size=32
        )
        
        logger.info(f"✅ Generated {embeddings.shape[0]} embeddings of dimension {embeddings.shape[1]}")
        
        # Save embeddings
        embeddings_file = self.topology_path / "variable_embeddings.npy"
        np.save(embeddings_file, embeddings)
        
        # Save embedding texts for reference
        texts_file = self.topology_path / "embedding_texts.json"
        with open(texts_file, 'w') as f:
            json.dump(embedding_texts, f, indent=2)
        
        return embeddings
    
    def discover_spatial_topology(self, embeddings: np.ndarray, df: pd.DataFrame) -> Dict[str, Any]:
        """Discover spatial topology through dimensionality reduction and clustering"""
        
        logger.info("🌌 Discovering spatial topology through UMAP + HDBSCAN...")
        
        # Step 1: UMAP dimensionality reduction (high-dim -> 3D)
        logger.info("  📐 UMAP dimensionality reduction...")
        umap_reducer = umap.UMAP(**self.umap_params)
        spatial_coords = umap_reducer.fit_transform(embeddings)
        
        logger.info(f"  ✅ Reduced to 3D coordinates: {spatial_coords.shape}")
        
        # Step 2: HDBSCAN clustering in 3D space
        logger.info("  🎯 HDBSCAN clustering...")
        clusterer = HDBSCAN(**self.hdbscan_params)
        cluster_labels = clusterer.fit_predict(spatial_coords)
        
        # Analyze clustering results
        unique_labels = np.unique(cluster_labels)
        n_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)  # Exclude noise (-1)
        n_noise = np.sum(cluster_labels == -1)
        
        logger.info(f"  ✅ Discovered {n_clusters} clusters with {n_noise} noise points")
        
        # Calculate clustering quality metrics
        if n_clusters > 1:
            # Silhouette score (excluding noise points)
            mask = cluster_labels != -1
            if np.sum(mask) > 0:
                silhouette = silhouette_score(spatial_coords[mask], cluster_labels[mask])
                logger.info(f"  📊 Silhouette score: {silhouette:.3f}")
            else:
                silhouette = -1
        else:
            silhouette = -1
        
        # Step 3: Create uncertainty surface from agreement scores
        logger.info("  🌡️ Mapping uncertainty surface...")
        uncertainty_surface = self.create_uncertainty_surface(spatial_coords, df)
        
        # Compile topology results
        topology_results = {
            'spatial_coordinates': spatial_coords,
            'cluster_labels': cluster_labels,
            'uncertainty_surface': uncertainty_surface,
            'n_clusters': n_clusters,
            'n_noise_points': n_noise,
            'silhouette_score': silhouette,
            'umap_params': self.umap_params,
            'hdbscan_params': self.hdbscan_params,
            'discovery_timestamp': datetime.now().isoformat()
        }
        
        # Save results
        self.save_topology_results(topology_results, df)
        
        return topology_results
    
    def create_uncertainty_surface(self, spatial_coords: np.ndarray, df: pd.DataFrame) -> np.ndarray:
        """Create uncertainty surface from LLM agreement scores"""
        
        # Use agreement scores as uncertainty measure (lower agreement = higher uncertainty)
        agreement_scores = df['agreement_score'].values
        uncertainty_scores = 1.0 - agreement_scores  # Flip: low agreement = high uncertainty
        
        # Map uncertainty to spatial coordinates
        uncertainty_surface = uncertainty_scores
        
        logger.info(f"  📊 Uncertainty surface: {uncertainty_surface.min():.3f} to {uncertainty_surface.max():.3f}")
        
        return uncertainty_surface
    
    def save_topology_results(self, results: Dict[str, Any], df: pd.DataFrame):
        """Save topology discovery results"""
        
        # Save spatial coordinates with metadata
        coords_df = df.copy()
        coords_df['x_coord'] = results['spatial_coordinates'][:, 0]
        coords_df['y_coord'] = results['spatial_coordinates'][:, 1]
        coords_df['z_coord'] = results['spatial_coordinates'][:, 2]
        coords_df['cluster_id'] = results['cluster_labels']
        coords_df['uncertainty'] = results['uncertainty_surface']
        
        coords_file = self.topology_path / "spatial_topology_coordinates.csv"
        coords_df.to_csv(coords_file, index=False)
        
        # Save topology metadata
        metadata = {
            'discovery_summary': {
                'total_variables': int(len(df)),
                'n_clusters': int(results['n_clusters']),
                'n_noise_points': int(results['n_noise_points']),
                'silhouette_score': float(results['silhouette_score']),
                'avg_uncertainty': float(np.mean(results['uncertainty_surface'])),
                'discovery_timestamp': results['discovery_timestamp']
            },
            'parameters': {
                'umap': results['umap_params'],
                'hdbscan': results['hdbscan_params']
            }
        }
        
        metadata_file = self.topology_path / "topology_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Save numpy arrays
        np.save(self.topology_path / "spatial_coordinates.npy", results['spatial_coordinates'])
        np.save(self.topology_path / "cluster_labels.npy", results['cluster_labels'])
        np.save(self.topology_path / "uncertainty_surface.npy", results['uncertainty_surface'])
        
        logger.info(f"💾 Topology results saved to {self.topology_path}")
    
    def analyze_cluster_characteristics(self, df: pd.DataFrame, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze what characterizes each discovered cluster - FULL DETAILED ANALYSIS"""
        
        logger.info("🔍 Analyzing cluster characteristics...")
        
        coords_df = df.copy()
        coords_df['cluster_id'] = results['cluster_labels']
        coords_df['uncertainty'] = results['uncertainty_surface']
        # Add spatial coordinates with consistent naming
        coords_df['x_coord'] = results['spatial_coordinates'][:, 0]
        coords_df['y_coord'] = results['spatial_coordinates'][:, 1]
        coords_df['z_coord'] = results['spatial_coordinates'][:, 2]
        
        cluster_analysis = {}
        
        for cluster_id in sorted(coords_df['cluster_id'].unique()):
            if cluster_id == -1:  # Skip noise
                continue
                
            cluster_vars = coords_df[coords_df['cluster_id'] == cluster_id]
            
            # COMPREHENSIVE cluster analysis
            analysis = {
                'size': int(len(cluster_vars)),
                'table_families': {k: int(v) for k, v in cluster_vars['table_family'].value_counts().head(10).to_dict().items()},
                'concepts': {k: int(v) for k, v in cluster_vars['concept'].value_counts().head(10).to_dict().items()},
                'coos_categories': {k: int(v) for k, v in cluster_vars['coos_category'].value_counts().to_dict().items()},
                'complexity_distribution': {k: int(v) for k, v in cluster_vars['complexity'].value_counts().to_dict().items()},
                'survey_distribution': {k: int(v) for k, v in cluster_vars['survey'].value_counts().to_dict().items()},
                'avg_agreement': float(cluster_vars['agreement_score'].mean()),
                'avg_confidence': float(cluster_vars['final_confidence'].mean()),
                'avg_uncertainty': float(cluster_vars['uncertainty'].mean()),
                'sample_variables': cluster_vars[['variable_id', 'label', 'concept']].head(5).to_dict('records'),
                'spatial_center': {
                    'x': float(cluster_vars['x_coord'].mean()),
                    'y': float(cluster_vars['y_coord'].mean()),
                    'z': float(cluster_vars['z_coord'].mean())
                }
            }
            
            cluster_analysis[f'cluster_{cluster_id}'] = analysis
        
        # Save cluster analysis
        analysis_file = self.topology_path / "cluster_analysis.json"
        with open(analysis_file, 'w') as f:
            json.dump(cluster_analysis, f, indent=2)
        
        # Log summary - THE DETAILED OUTPUT YOU WANTED
        logger.info(f"  📊 Cluster Analysis Summary:")
        for cluster_id, analysis in cluster_analysis.items():
            logger.info(f"    {cluster_id}: {analysis['size']} variables, "
                       f"avg agreement: {analysis['avg_agreement']:.3f}")
            
            # Show top COOS categories in this cluster
            top_coos = list(analysis['coos_categories'].items())[:3]
            if top_coos:
                coos_str = ", ".join([f"{cat}({count})" for cat, count in top_coos])
                logger.info(f"      COOS categories: {coos_str}")
        
        return cluster_analysis
    
    def create_topology_visualizations(self, df: pd.DataFrame, results: Dict[str, Any]):
        """Create COMPLETE interactive visualization suite - ALL THE MISSING FUNCTIONALITY"""
        
        logger.info("📊 Creating comprehensive topology visualizations...")
        
        # Prepare data for visualization
        coords_df = df.copy()
        coords_df['x'] = results['spatial_coordinates'][:, 0]
        coords_df['y'] = results['spatial_coordinates'][:, 1]
        coords_df['z'] = results['spatial_coordinates'][:, 2]
        coords_df['cluster'] = results['cluster_labels'].astype(str)
        coords_df['uncertainty'] = results['uncertainty_surface']
        
        # 1. 3D Cluster Visualization
        logger.info("  🎯 Creating 3D cluster visualization...")
        fig_clusters = px.scatter_3d(
            coords_df,
            x='x', y='y', z='z',
            color='cluster',
            size='final_confidence',
            hover_data=['variable_id', 'label', 'table_family', 'concept'],
            title='Census Variable Spatial Topology - 3D Clusters',
            labels={'x': 'Spatial Dimension 1', 'y': 'Spatial Dimension 2', 'z': 'Spatial Dimension 3'}
        )
        fig_clusters.update_layout(height=800)
        fig_clusters.write_html(self.topology_path / "3d_topology_clusters.html")
        
        # 2. Uncertainty Surface Visualization
        logger.info("  🌡️ Creating uncertainty surface visualization...")
        fig_uncertainty = px.scatter_3d(
            coords_df,
            x='x', y='y', z='z',
            color='uncertainty',
            color_continuous_scale='Viridis',
            hover_data=['variable_id', 'label', 'agreement_score'],
            title='Census Variable Spatial Topology - Uncertainty Surface',
            labels={'uncertainty': 'Uncertainty Score'}
        )
        fig_uncertainty.update_layout(height=800)
        fig_uncertainty.write_html(self.topology_path / "3d_topology_uncertainty.html")
        
        # 3. COOS Categories Visualization - THE WHOLE POINT!
        logger.info("  🎨 Creating COOS categories visualization...")
        fig_coos = px.scatter_3d(
            coords_df,
            x='x', y='y', z='z',
            color='coos_category',
            hover_data=['variable_id', 'label', 'concept', 'table_family'],
            title='Census Variable Spatial Topology - COOS Categories',
            labels={'coos_category': 'COOS Category'}
        )
        fig_coos.update_layout(height=800)
        fig_coos.write_html(self.topology_path / "3d_topology_categories.html")
        
        # 4. Table Families Visualization
        logger.info("  📊 Creating table families visualization...")
        fig_families = px.scatter_3d(
            coords_df,
            x='x', y='y', z='z',
            color='table_family',
            hover_data=['variable_id', 'label', 'concept'],
            title='Census Variable Spatial Topology - Table Families',
            labels={'table_family': 'Table Family'}
        )
        fig_families.update_layout(height=800)
        fig_families.write_html(self.topology_path / "3d_topology_families.html")
        
        # 5. 2D Projections for Different Perspectives
        logger.info("  📐 Creating 2D projection visualizations...")
        fig_2d = make_subplots(
            rows=2, cols=2,
            subplot_titles=['X-Y Projection', 'X-Z Projection', 'Y-Z Projection', 'COOS Distribution'],
            specs=[[{'type': 'scatter'}, {'type': 'scatter'}],
                   [{'type': 'scatter'}, {'type': 'pie'}]]
        )
        
        # X-Y projection
        fig_2d.add_trace(
            go.Scatter(x=coords_df['x'], y=coords_df['y'], mode='markers',
                      marker=dict(color=coords_df['cluster'].astype(int), colorscale='Viridis'),
                      text=coords_df['variable_id'], name='Clusters'),
            row=1, col=1
        )
        
        # X-Z projection
        fig_2d.add_trace(
            go.Scatter(x=coords_df['x'], y=coords_df['z'], mode='markers',
                      marker=dict(color=coords_df['uncertainty'], colorscale='Plasma'),
                      text=coords_df['variable_id'], name='Uncertainty'),
            row=1, col=2
        )
        
        # Y-Z projection
        fig_2d.add_trace(
            go.Scatter(x=coords_df['y'], y=coords_df['z'], mode='markers',
                      marker=dict(color=coords_df['agreement_score'], colorscale='RdYlBu'),
                      text=coords_df['variable_id'], name='Agreement'),
            row=2, col=1
        )
        
        # COOS category distribution
        coos_counts = coords_df['coos_category'].value_counts()
        fig_2d.add_trace(
            go.Pie(labels=coos_counts.index, values=coos_counts.values, name='COOS Distribution'),
            row=2, col=2
        )
        
        fig_2d.update_layout(height=800, title_text="Census Variable Topology - 2D Projections")
        fig_2d.write_html(self.topology_path / "2d_topology_projections.html")
        
        # 6. Comprehensive Dashboard
        logger.info("  📋 Creating comprehensive dashboard...")
        dashboard_html = self._create_topology_dashboard(coords_df, results)
        with open(self.topology_path / "topology_dashboard.html", 'w') as f:
            f.write(dashboard_html)
        
        logger.info(f"📊 All visualizations saved to {self.topology_path}")
    
    def _create_topology_dashboard(self, coords_df: pd.DataFrame, results: Dict[str, Any]) -> str:
        """Create a comprehensive HTML dashboard with all analysis results"""
        
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Census Variable Spatial Topology Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #2c3e50; color: white; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .metric {{ display: inline-block; margin: 10px; padding: 10px; background-color: #ecf0f1; border-radius: 3px; }}
                .visualization-links {{ margin: 20px 0; }}
                .visualization-links a {{ display: inline-block; margin: 10px; padding: 10px 20px; background-color: #3498db; color: white; text-decoration: none; border-radius: 3px; }}
                .cluster-summary {{ margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Census Variable Spatial Topology Discovery</h1>
                <p>Generated on {results['discovery_timestamp']}</p>
            </div>
            
            <div class="section">
                <h2>Discovery Summary</h2>
                <div class="metric">Total Variables: {len(coords_df)}</div>
                <div class="metric">Clusters Discovered: {results['n_clusters']}</div>
                <div class="metric">Noise Points: {results['n_noise_points']}</div>
                <div class="metric">Silhouette Score: {results['silhouette_score']:.3f}</div>
                <div class="metric">Avg Uncertainty: {np.mean(results['uncertainty_surface']):.3f}</div>
            </div>
            
            <div class="section">
                <h2>Interactive Visualizations</h2>
                <div class="visualization-links">
                    <a href="3d_topology_clusters.html">3D Clusters</a>
                    <a href="3d_topology_uncertainty.html">Uncertainty Surface</a>
                    <a href="3d_topology_categories.html">COOS Categories</a>
                    <a href="3d_topology_families.html">Table Families</a>
                    <a href="2d_topology_projections.html">2D Projections</a>
                </div>
            </div>
            
            <div class="section">
                <h2>COOS Category Distribution</h2>
                {self._generate_coos_summary_html(coords_df)}
            </div>
            
            <div class="section">
                <h2>Data Files</h2>
                <ul>
                    <li><strong>spatial_topology_coordinates.csv</strong> - Complete coordinate data with metadata</li>
                    <li><strong>cluster_analysis.json</strong> - Detailed cluster characteristics</li>
                    <li><strong>topology_metadata.json</strong> - Discovery parameters and summary</li>
                    <li><strong>variable_embeddings.npy</strong> - Raw embeddings data</li>
                </ul>
            </div>
        </body>
        </html>
        """
        
        return html_template
    
    def _generate_coos_summary_html(self, coords_df: pd.DataFrame) -> str:
        """Generate HTML summary of COOS category distribution"""
        
        coos_counts = coords_df['coos_category'].value_counts()
        
        html = "<table border='1' style='width:100%; border-collapse: collapse;'>"
        html += "<tr><th>COOS Category</th><th>Variable Count</th><th>Percentage</th></tr>"
        
        total_vars = len(coords_df)
        for category, count in coos_counts.items():
            percentage = (count / total_vars) * 100
            html += f"<tr><td>{category}</td><td>{count}</td><td>{percentage:.1f}%</td></tr>"
        
        html += "</table>"
        
        return html
    
    def discover_complete_topology(self, input_file: str, sample_size: int = None) -> Dict[str, Any]:
        """COMPLETE topology discovery pipeline - FULL FUNCTIONALITY RESTORED"""
        
        logger.info("🚀 Starting COMPLETE spatial topology discovery...")
        logger.info("=" * 60)
        
        # Step 1: Load enriched data
        df = self.load_enriched_data(input_file, sample_size)
        
        # Step 2: Generate embeddings
        embeddings = self.generate_embeddings(df)
        
        # Step 3: Discover spatial topology
        results = self.discover_spatial_topology(embeddings, df)
        
        # Step 4: Analyze cluster characteristics - DETAILED ANALYSIS
        cluster_analysis = self.analyze_cluster_characteristics(df, results)
        
        # Step 5: Create COMPLETE visualization suite
        self.create_topology_visualizations(df, results)
        
        # Final comprehensive summary
        summary = {
            'input_file': input_file,
            'total_variables_processed': int(len(df)),
            'sample_size': int(sample_size) if sample_size else None,
            'spatial_dimensions': 3,
            'discovered_clusters': int(results['n_clusters']),
            'noise_points': int(results['n_noise_points']),
            'silhouette_score': float(results['silhouette_score']),
            'topology_quality': 'excellent' if results['silhouette_score'] > 0.5 else
                               'good' if results['silhouette_score'] > 0.3 else 'needs_tuning',
            'avg_uncertainty': float(np.mean(results['uncertainty_surface'])),
            'cluster_analysis': cluster_analysis,
            'coos_category_distribution': df['coos_category'].value_counts().to_dict(),
            'files_generated': [
                'spatial_topology_coordinates.csv',
                'topology_metadata.json',
                'cluster_analysis.json',
                '3d_topology_clusters.html',
                '3d_topology_uncertainty.html',
                '3d_topology_categories.html',
                '3d_topology_families.html',
                '2d_topology_projections.html',
                'topology_dashboard.html',
                'variable_embeddings.npy',
                'spatial_coordinates.npy',
                'cluster_labels.npy',
                'uncertainty_surface.npy'
            ],
            'discovery_timestamp': results['discovery_timestamp']
        }
        
        # Save final comprehensive summary
        summary_file = self.topology_path / "topology_discovery_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info("🎉 COMPLETE SPATIAL TOPOLOGY DISCOVERY FINISHED!")
        logger.info(f"   📊 {summary['discovered_clusters']} clusters discovered")
        logger.info(f"   📈 Silhouette score: {summary['silhouette_score']:.3f}")
        logger.info(f"   🎨 COOS categories mapped and visualized")
        logger.info(f"   📁 {len(summary['files_generated'])} files generated")
        logger.info(f"   💾 Results saved to: {self.topology_path}")
        logger.info("   🌐 Open topology_dashboard.html for complete analysis")
        
        return summary

def main():
    parser = argparse.ArgumentParser(description='Discover spatial topology from enriched Census variables - COMPLETE SUITE')
    parser.add_argument('--input-file', required=True, help='Input enriched JSON file')
    parser.add_argument('--output-dir', default='../topology_results/complete_analysis',
                       help='Output directory for topology results')
    parser.add_argument('--sample-size', type=int, help='Sample size (optional)')
    parser.add_argument('--coos-concepts-dir', help='Directory with COOS concept files (for category mapping)')
    
    args = parser.parse_args()
    
    # Initialize discovery engine with COOS mapping capability
    discoverer = SpatialTopologyDiscovery(
        output_dir=args.output_dir,
        coos_concepts_dir=args.coos_concepts_dir
    )
    
    # Run COMPLETE topology discovery with full functionality
    summary = discoverer.discover_complete_topology(args.input_file, args.sample_size)
    
    # Save summary
    summary_file = Path(args.output_dir) / "discovery_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

if __name__ == "__main__":
    main()
