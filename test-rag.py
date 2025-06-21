# test_rag.py - Run this in your project root
import chromadb
import openai
import os

# Test the vector DB directly
client = chromadb.PersistentClient(path='data/vector_db')
collection = client.get_collection('census_knowledge')

print(f"Collection has {collection.count()} documents")

# Test a simple query without embeddings first
results = collection.get(limit=5)
print(f"Sample documents:")
for i, doc in enumerate(results['documents'][:3]):
    print(f"{i+1}. {doc[:100]}...")

# Test with OpenAI embeddings
openai_client = openai.OpenAI()
query = "ACS methodology"

response = openai_client.embeddings.create(
    input=[query],
    model="text-embedding-3-large"
)
query_embedding = response.data[0].embedding

# Search with embedding
search_results = collection.query(
    query_embeddings=[query_embedding],
    n_results=5
)

print(f"\nSearch results for '{query}':")
print(f"Found {len(search_results['documents'][0])} results")

if search_results['documents'][0]:
    for i, (doc, distance) in enumerate(zip(search_results['documents'][0], search_results['distances'][0])):
        similarity = 1 - distance
        print(f"{i+1}. Similarity: {similarity:.3f}")
        print(f"   {doc[:150]}...")
else:
    print("No results found!")
