# Atlas architecture decisions

This is a fictional test document, supplied under the repository's MIT license.

Atlas uses PostgreSQL for transactional records and Kafka for event delivery.
The team chose idempotent consumers to handle duplicate events. The incident review
requires every release to include a tested rollback procedure.
