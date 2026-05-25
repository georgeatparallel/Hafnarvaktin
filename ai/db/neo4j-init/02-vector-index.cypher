// Vector index for Neo4j vector RAG (AI exam mandatory component)
// Runs once. Idempotent.
//
// 768 dimensions = output of intfloat/multilingual-e5-base
// cosine similarity = standard for sentence embeddings
//
// After this index exists, the MCP server's `search_vessels` tool can do:
//   CALL db.index.vector.queryNodes('vessel_desc_idx', $limit, $query_emb)
//   YIELD node, score
//   RETURN node.name, node.type, node.material, node.length_m, score

CREATE VECTOR INDEX vessel_desc_idx IF NOT EXISTS
FOR (v:Vessel) ON (v.description_embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 768,
    `vector.similarity_function`: 'cosine'
  }
};

// List indexes to verify
SHOW VECTOR INDEXES;
