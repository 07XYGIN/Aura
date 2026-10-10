"""Provider boundary for memory embeddings, pending an online provider."""

from langchain_core.embeddings import Embeddings


class MemoryEmbeddingsUnavailable(RuntimeError):
    """Semantic memory operations need a configured embedding provider."""


def get_memory_embeddings() -> Embeddings:
    """Return the future online client after existing memories are reindexed.

    Keep vector operations disabled until the provider and migration are ready;
    vectors from different models must not share the existing collections.
    """
    raise MemoryEmbeddingsUnavailable("Online memory embeddings are not connected yet.")
