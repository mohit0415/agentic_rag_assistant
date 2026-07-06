const StringData = {
  app: {
    name: "MedLearn",
    nameHighlight: "Learn",
    logoEmoji: "✚",
    tagline: "AI-powered medical research, grounded in your evidence",
  },

  nav: {
    sectionDocuments: "Documents",
    uploadBtn: "Upload files",
    resetDocsTooltip: "Reset document list (use after the backend index was cleared)",
    evalSectionLabel: "Answer Quality",
    evalFaithfulness: "Faithfulness",
    evalRelevance: "Relevance",
    evalEmpty: "—",
    evalPendingHint: "Scores appear after each answer",
  },

  chat: {
    title: "Chat",
    titleSuffix: "All documents",
    modelBadge: "text-embedding-3-large",
    inputPlaceholder: "Ask about your documents...",
    sendAriaLabel: "Send",
    welcomeMessage:
      "Hey! I've indexed {count} documents — {chunks} chunks stored in pgvector. Ask me anything about your docs and I'll cite exactly which chunk answered you.",
    thinkingLabel: "Retrieving {count} chunks · re-ranking...",
    scopeBadge: "{count} docs",
    emptyChatHint: "Upload a document and start asking questions.",
  },

  rightPanel: {
    tabSources: "Sources",
    tabPipeline: "Pipeline",
    tabSQL: "SQL",
    tabVector: "Vector",
    sourcesHeader: "Retrieved chunks",
    chunkCountBadge: "{count} chunks",
    pipelineHeader: "RAG Pipeline",
    pipelineConfigHeader: "Config",
  },

  pipeline: {
    lastQueryLabel: "Last query run",
    steps: [
      "Query received",
      "Embed query → 3072-d",
      "pgvector ANN search",
      "Top-20 retrieved",
      "Cross-encoder re-rank",
      "Top-5 selected",
      "LLM generating...",
      "Citations mapped",
      "Response delivered",
    ],
    configKeys: {
      chunkSize: "Chunk size",
      overlap: "Overlap",
      topK: "Top-k retrieve",
      rerankTo: "Re-rank to",
      indexType: "Index type",
    },
    configValues: {
      chunkSize: "512 tokens",
      overlap: "64 tokens",
      topK: "20",
      rerankTo: "5",
      indexType: "HNSW",
    },
  },

  sqlTool: {
    pageTitle: "SQL Tool",
    pageTitleSuffix: "Query your vector metadata",
    dbBadge: "PostgreSQL",
    editorPlaceholder: "-- Write your SQL query here",
    defaultQuery: `SELECT doc_id, chunk_index,\n       1 - (embedding <=> query_embedding) AS similarity,\n       content, metadata->>'page' AS page\nFROM   document_chunks\nWHERE  1 - (embedding <=> query_embedding) > 0.80\nORDER  BY similarity DESC\nLIMIT  10;`,
    runBtn: "▶  Run Query",
    resultsLabel: "RESULTS",
    schemaLabel: "SCHEMA EXPLORER",
    tableHeaders: ["doc_id", "chunk", "similarity", "page", "content preview"],
    noResults: "Run a query to see results.",
  },

  vectorTool: {
    pageTitle: "Vector Tool",
    pageTitleSuffix: "Explore embedding space",
    dbBadge: "pgvector · HNSW",
    searchLabel: "SIMILARITY SEARCH",
    searchPlaceholder: "Enter query or paste embedding...",
    topKLabel: "Top-K:",
    searchBtn: "Search",
    vizLabel: "EMBEDDING SPACE (t-SNE projection)",
    configLabel: "INDEX CONFIG",
    statsLabel: "EMBEDDING STATS",
    configKeys: {
      indexType: "Index type",
      dimensions: "Dimensions",
      distance: "Distance",
      m: "m (connections)",
      efConstruction: "ef_construction",
      efSearch: "ef_search",
      chunkSize: "Chunk size",
      overlap: "Overlap",
      topK: "Top-k retrieve",
      rerankTo: "Re-rank to",
    },
    configValues: {
      indexType: "HNSW",
      dimensions: "3072",
      distance: "cosine",
      m: "16",
      efConstruction: "64",
      efSearch: "40",
      chunkSize: "512 tokens",
      overlap: "64 tokens",
      topK: "20",
      rerankTo: "5",
    },
    statsKeys: {
      totalVectors: "Total vectors",
      indexSize: "Index size",
      avgQueryTime: "Avg query time",
    },
    statsValues: {
      totalVectors: "1,159",
      indexSize: "28.4 MB",
      avgQueryTime: "4.2 ms",
    },
  },

  docStatus: {
    ready: "ready",
    indexing: "indexing",
    indexingLabel: "Indexing...",
  },

  modal: {
    uploadSuccessTitle: "Document indexed",
    uploadSuccessMessage:
      "{file} was processed successfully — {count} document(s) added to the index.",
    uploadErrorTitle: "Upload failed",
    uploadErrorMessage:
      "We couldn't index {file}.",
    closeBtn: "Got it",
    retryBtn: "Try again",
    dismissAria: "Close dialog",
  },

  errors: {
    uploadFailed: "Upload failed. Please try again.",
    queryFailed: "Query failed. Please try again.",
  },

  aria: {
    sidebar: "Document sidebar",
    chatArea: "Chat messages",
    sendButton: "Send message",
    uploadButton: "Upload document",
    resetDocsButton: "Reset document list",
    closePanel: "Close panel",
  },
};

export default StringData;
