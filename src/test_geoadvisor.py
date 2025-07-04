#!/usr/bin/env python3

from utils.geoadvisor import GeoAdvisor

def test_geoadvisor():
    print("🧪 Testing GeoAdvisor...\n")
    
    # Initialize with your table data
    advisor = GeoAdvisor(table_geo_file="../data/table_geos.json",
              geo_weight_file="../data/geo_weights.json"
    )
    
    # Simple test
    result = advisor.recommend("B01001_001E", "tract")
    print(f"B01001_001E at tract level: {result['status']}")
    print(f"Message: {result['message']}")
    
    # Show stats
    stats = advisor.get_stats()
    print(f"\nLoaded {stats['tables_loaded']} tables")

if __name__ == "__main__":
    test_geoadvisor()
