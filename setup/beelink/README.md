# Linux and Beelink target

[Setup](../README.md) · [Services](../containers/README.md) · [Model routing](../model-routing.md)

A Linux mini-PC can host Nora's application and databases. Use the [shared setup procedure](../README.md#run-the-application); there is no separate Beelink application copy or required SSH hostname.

Choose persistent storage for `.runtime/` and the named database volumes. Set `NORA_UID` and `NORA_GID` to the host account that owns the prepared files and credentials. Query encoding uses CPU BGE; optional local answer generation has a separate memory and compute requirement.

The default answer route remains Ollama Cloud. The optional `local-model` profile provides a local Ollama container after the operator chooses and installs a suitable tool-capable model. No local model or Docker service was started as part of this refactor.

The new package and synthetic retrieval were checked on a development machine. An isolated ARM Linux container trial also passed complete startup, file ownership, live Ollama answers, conversation restart and PostgreSQL restoration into fresh storage. Follow [shared setup](../README.md#run-the-application) for a fresh target. The original host-specific transfer, bootstrap and verification scripts are preserved outside the public release.
