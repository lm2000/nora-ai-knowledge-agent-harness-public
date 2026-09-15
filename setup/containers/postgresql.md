# PostgreSQL

[Services](README.md) · [Coordination](coordination.md)

PostgreSQL saves conversation checkpoints so a user can continue a thread after reloading the UI. It does not store the search corpus or batch-ingestion status.

[Root Compose](../../compose.yaml) pins PostgreSQL 17, uses a named volume and publishes no database host port. Coordination uses the official async LangGraph Postgres saver and initializes its schema at startup. [Settings](../configuration.md#credentials-and-postgresql) define the connection without embedding credentials in source.

The source tests use an in-memory checkpointer to validate graph history. An isolated ARM Linux container trial also verified PostgreSQL reconnect after Coordination restart and restoration of the same conversation into a separate PostgreSQL instance with a fresh volume. [Validation](../../evaluation/VALIDATION.md) records the exact scope; crash behavior, migration and other host architectures remain to test. [Operations](../private-deployment/ROLLOUT.md#operate-and-recover) describes the separate recovery checks.


In the selected target, this remains one shared PostgreSQL container with its own data volume. Each role runtime writes conversation checkpoints; role/thread namespacing and access isolation must be defined and implemented before enabling multiple roles. Ingestion job state remains independent.
