# References and attribution

[Architecture](Architecture%20Concept.md) · [Technology choices](Technology%20Options.md) · [Notices](../NOTICE.md)

These references explain the technologies and patterns behind Nora. A linked tutorial is not evidence that its features are installed, and Nora does not inherit a tutorial's provider or hosting choices.

## Core references

| Reference | Contribution to Nora |
| --- | --- |
| [LangChain products and concepts](https://docs.langchain.com/oss/python/concepts/products) | Distinguish framework, runtime and harness |
| [OSS Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) | Agent harness inside Coordination |
| [Deep Agents RAG](https://docs.langchain.com/oss/python/deepagents/rag) | Agent and retrieval-tool integration |
| [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | Checkpoints and thread-scoped state |
| [CopilotKit LangGraph architecture](https://docs.copilotkit.ai/langgraph-python/concepts/architecture) | Browser, runtime and AG-UI integration |
| [MCP specification](https://modelcontextprotocol.io/specification/latest) | Shared tool protocol boundary |
| [BGE model card](https://huggingface.co/BAAI/bge-base-en-v1.5) | Embedding model and usage context |
| [Qdrant documentation](https://qdrant.tech/documentation/) | Vector and sparse retrieval infrastructure |
| [Docling documentation](https://docling-project.github.io/docling/) | Document conversion |

## Routing and evaluation references

| Reference | Category and use |
| --- | --- |
| [LiteLLM](https://docs.litellm.ai/) | Inference gateway reference; not installed in the current router |
| [RouteLLM](https://github.com/lm-sys/RouteLLM) | Learned model-routing reference; the current scorer is heuristic |
| [MT-Bench and Chatbot Arena paper](https://arxiv.org/abs/2306.05685) | Model-judge methodology and limitations |
| [LangSmith evaluation](https://docs.langchain.com/langsmith/evaluation) | Selected future evaluation/observability tooling |
| [Harbor](https://www.harborframework.com/docs) | Candidate environment/task evaluation framework |

## Documentation and layout references

The [new-langgraph-project starter](https://github.com/langchain-ai/new-langgraph-project/tree/f7e2ee300d483b5c0602d57518f3351ad5d55850) and [retrieval-agent-template](https://github.com/langchain-ai/retrieval-agent-template) informed project and query/retrieve/respond organization. Their reference role does not create a second application scaffold.

The [managed agent project structure](https://docs.langchain.com/langsmith/python/managed-deep-agents-project-structure) informed the proposed per-role layout. Nora uses the OSS SDK, not managed discovery or automatic hosted-agent deployment.

Public diagrams use [GitHub-supported Mermaid Markdown](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams). Original private sketches remain preserved outside the public documentation. Retained license text is in [NOTICE.md](../NOTICE.md) and [Templates/LICENSE](../Templates/LICENSE).
