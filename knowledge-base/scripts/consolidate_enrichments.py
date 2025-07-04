#!/usr/bin/env python3
"""
Dataset Consolidation Script - Combine COOS, Early, and Bulk Enrichments
Combines all enriched datasets into complete 2023 ACS Universe with priority-based deduplication and quality tracking.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EnrichmentConsolidator:
    """Consolidate multiple enrichment datasets with quality tracking"""
    
    def __init__(self):
        self.quality_hierarchy = {
            'coos': {'priority': 1, 'description': 'Research-grade, domain specialist ensemble'},
            'early': {'priority': 2, 'description': 'High-quality ensemble testing'},
            'bulk': {'priority': 3, 'description': 'Single-agent production coverage'}
        }
        
        self.consolidated_data = {}
        self.processing_stats = {
            'total_variables': 0,
            'duplicates_resolved': 0,
            'quality_distribution': {
                'coos': 0,
                'early': 0,
                'bulk': 0
            }
        }
    
    def load_dataset(self, file_path: str, dataset_type: str) -> Dict[str, Any]:
        """Load enrichment dataset and standardize format"""
        logger.info(f"Loading {dataset_type} dataset from {file_path}")
        
        if not Path(file_path).exists():
            logger.warning(f"File not found: {file_path}")
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Loaded {len(data)} variables from {dataset_type} dataset")
            return data
            
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return {}
    
    def standardize_record(self, var_id: str, data: Any, source_type: str) -> Dict[str, Any]:
        """Standardize enrichment record format across different sources"""
        
        # Base record structure
        record = {
            'variable_id': var_id,
            'source_type': source_type,
            'quality_tier': self.quality_hierarchy[source_type]['description'],
            'priority': self.quality_hierarchy[source_type]['priority'],
            'processing_timestamp': datetime.now().isoformat()
        }
        
        # Handle different input formats
        if isinstance(data, dict):
            # Standard enrichment format
            record.update({
                'label': data.get('label', data.get('official_label', 'Unknown')),
                'concept': data.get('concept', 'Unknown'),
                'table_family': var_id[:3] if len(var_id) >= 3 else 'Unknown',
                'survey': data.get('survey', 'ACS'),
                'complexity': data.get('complexity', 'medium')
            })
            
            # Extract enrichment content
            enrichment_text = self._extract_enrichment_text(data)
            record['enrichment_text'] = enrichment_text
            
            # Preserve metadata fields
            for field in ['agreement_score', 'processing_cost', 'analysis', 'methodology_notes']:
                if field in data:
                    record[field] = data[field]
                    
        else:
            # Fallback for unexpected formats
            record.update({
                'label': 'Unknown',
                'concept': 'Unknown',
                'table_family': var_id[:3] if len(var_id) >= 3 else 'Unknown',
                'enrichment_text': str(data) if data else '',
                'survey': 'ACS',
                'complexity': 'unknown'
            })
        
        return record
    
    def _extract_enrichment_text(self, data: Dict) -> str:
        """Extract enrichment text from various possible fields"""
        enrichment_parts = []
        
        # Check various enrichment fields
        enrichment_sources = [
            data.get('enrichment', ''),
            data.get('analysis', {}),
            data.get('summary', ''),
            data.get('description', '')
        ]
        
        for source in enrichment_sources:
            if isinstance(source, dict):
                # Extract from analysis dictionary
                for key in ['summary', 'concept', 'statistical_method', 'limitations', 'methodology_notes']:
                    if key in source and source[key]:
                        enrichment_parts.append(f"{key}: {source[key]}")
            elif isinstance(source, str) and source.strip():
                enrichment_parts.append(source.strip())
        
        return ' | '.join(enrichment_parts) if enrichment_parts else 'No enrichment available'
    
    def consolidate_datasets(self, datasets: Dict[str, Dict]) -> Dict[str, Any]:
        """Consolidate multiple datasets with priority-based deduplication"""
        logger.info("Starting dataset consolidation...")
        
        # Process datasets in priority order (highest priority first)
        for source_type in sorted(self.quality_hierarchy.keys(),
                                key=lambda x: self.quality_hierarchy[x]['priority']):
            
            if source_type not in datasets or not datasets[source_type]:
                logger.info(f"No data for {source_type}, skipping...")
                continue
                
            dataset = datasets[source_type]
            logger.info(f"Processing {len(dataset)} variables from {source_type} dataset")
            
            # Handle both dict and list formats
            if isinstance(dataset, list):
                # List format - each item should have variable_id
                for item in dataset:
                    if isinstance(item, dict) and 'variable_id' in item:
                        var_id = item['variable_id']
                        data = item
                    else:
                        logger.warning(f"Skipping malformed item in {source_type}: {item}")
                        continue
            elif isinstance(dataset, dict):
                # Dict format - iterate over items
                for var_id, data in dataset.items():
                    pass  # Will be handled in the loop body below
            else:
                logger.error(f"Unsupported dataset format for {source_type}: {type(dataset)}")
                continue
            
            # Process each variable (works for both list and dict formats)
            items_to_process = []
            if isinstance(dataset, list):
                for item in dataset:
                    if isinstance(item, dict) and 'variable_id' in item:
                        items_to_process.append((item['variable_id'], item))
            else:
                items_to_process = list(dataset.items())
            
            for var_id, data in items_to_process:
                # Standardize the record
                record = self.standardize_record(var_id, data, source_type)
                
                # Handle duplicates with priority-based resolution
                if var_id in self.consolidated_data:
                    existing_priority = self.consolidated_data[var_id]['priority']
                    new_priority = record['priority']
                    
                    if new_priority < existing_priority:  # Lower number = higher priority
                        logger.debug(f"Upgrading {var_id} from {self.consolidated_data[var_id]['source_type']} to {source_type}")
                        self.consolidated_data[var_id] = record
                        self.processing_stats['duplicates_resolved'] += 1
                    else:
                        logger.debug(f"Keeping existing {var_id} from {self.consolidated_data[var_id]['source_type']}")
                else:
                    self.consolidated_data[var_id] = record
                
                # Update quality distribution
                self.processing_stats['quality_distribution'][source_type] += 1
        
        self.processing_stats['total_variables'] = len(self.consolidated_data)
        
        logger.info("Consolidation complete!")
        return self.consolidated_data
    
    def generate_quality_report(self) -> Dict[str, Any]:
        """Generate quality report showing source distribution and statistics"""
        report = {
            'consolidation_summary': self.processing_stats,
            'quality_tiers': self.quality_hierarchy,
            'dataset_composition': {},
            'recommendations': []
        }
        
        # Calculate composition percentages
        total = self.processing_stats['total_variables']
        for source_type, count in self.processing_stats['quality_distribution'].items():
            percentage = (count / total * 100) if total > 0 else 0
            report['dataset_composition'][source_type] = {
                'count': count,
                'percentage': round(percentage, 2),
                'description': self.quality_hierarchy[source_type]['description']
            }
        
        # Generate recommendations
        coos_percentage = report['dataset_composition']['coos']['percentage']
        if coos_percentage > 25:
            report['recommendations'].append("High COOS coverage - excellent for research applications")
        
        if self.processing_stats['duplicates_resolved'] > 0:
            report['recommendations'].append(f"Resolved {self.processing_stats['duplicates_resolved']} duplicates using priority hierarchy")
        
        return report
    
    def save_consolidated_dataset(self, output_path: str, include_metadata: bool = True):
        """Save consolidated dataset with optional metadata"""
        logger.info(f"Saving consolidated dataset to {output_path}")
        
        output_data = {
            'variables': self.consolidated_data,
            'consolidation_metadata': {
                'created_at': datetime.now().isoformat(),
                'processing_stats': self.processing_stats,
                'quality_hierarchy': self.quality_hierarchy,
                'total_variables': len(self.consolidated_data)
            } if include_metadata else None
        }
        
        # Remove metadata if not requested
        if not include_metadata:
            output_data = self.consolidated_data
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(self.consolidated_data)} consolidated variables")

def main():
    parser = argparse.ArgumentParser(description='Consolidate enrichment datasets')
    parser.add_argument('--coos-file', type=str, default='coos_enriched_results.json',
                        help='COOS enrichment file (highest priority)')
    parser.add_argument('--early-file', type=str, default='../spatial_topology_discovery/enrichment_checkpoint.json',
                        help='Early sample enrichment file (medium priority)')
    parser.add_argument('--bulk-file', type=str, default='bulk_enriched_results.json',
                        help='Bulk enrichment file (lowest priority)')
    parser.add_argument('--output', type=str, default='2023_ACS_Enriched_Universe.json',
                        help='Output file for consolidated dataset')
    parser.add_argument('--report', type=str, default='consolidation_report.json',
                        help='Quality report output file')
    parser.add_argument('--include-metadata', action='store_true', default=True,
                        help='Include consolidation metadata in output')
    
    args = parser.parse_args()
    
    # Initialize consolidator
    consolidator = EnrichmentConsolidator()
    
    # Load datasets
    datasets = {
        'coos': consolidator.load_dataset(args.coos_file, 'coos'),
        'early': consolidator.load_dataset(args.early_file, 'early'),
        'bulk': consolidator.load_dataset(args.bulk_file, 'bulk')
    }
    
    # Consolidate
    consolidated = consolidator.consolidate_datasets(datasets)
    
    # Generate quality report
    quality_report = consolidator.generate_quality_report()
    
    # Save outputs
    consolidator.save_consolidated_dataset(args.output, args.include_metadata)
    
    with open(args.report, 'w', encoding='utf-8') as f:
        json.dump(quality_report, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "="*60)
    print("CONSOLIDATION COMPLETE")
    print("="*60)
    print(f"Total variables: {quality_report['consolidation_summary']['total_variables']}")
    print(f"Duplicates resolved: {quality_report['consolidation_summary']['duplicates_resolved']}")
    print("\nQuality Distribution:")
    for source, info in quality_report['dataset_composition'].items():
        print(f"  {source.upper()}: {info['count']} variables ({info['percentage']:.1f}%)")
    print(f"\nOutputs:")
    print(f"  Consolidated dataset: {args.output}")
    print(f"  Quality report: {args.report}")
    print("="*60)

if __name__ == "__main__":
    main()
