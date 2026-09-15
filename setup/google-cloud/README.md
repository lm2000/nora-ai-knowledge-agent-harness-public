# Google Cloud foundation

[Setup](../README.md) · [CLI guide](CLI.md) · [Qdrant installation](QDRANT.md)

This optional configurable CLI prepares a private VM, network, identity and storage. For example, preview a VM and data disk before installing the application.

It does not install the [shared application](../README.md). Its provisioning tests passed offline; this bundle's tests do not establish the state of any running project.

1. Copy and fill the configuration examples, then preview the [CLI stages](CLI.md).
2. Apply the intended foundation stages with the selected operator account.
3. Follow the [Qdrant guide](QDRANT.md) on the resulting VM.

The foundation backup bucket and database disk are distinct from a prepared-document store. Coordination, UI, ingestion and model inference are not installed by this route.

[Offline validation](VALIDATION.md) explains reproducible checks. Saved plans from the original operator environment are kept in the private history; new plans are local generated output.
