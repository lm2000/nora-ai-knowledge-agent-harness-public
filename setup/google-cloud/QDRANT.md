# Qdrant on a cloud host

[Cloud foundation](README.md) · [Shared setup](../README.md) · [Qdrant service](../containers/qdrant.md)

After provisioning a suitable VM, run Nora from the same [root Compose file](../../compose.yaml) used locally. Qdrant uses a named volume, an API key and the private service network. A second database-only Compose configuration is no longer maintained in the public source.

The optional foundation CLI prepares a VM and a separate data disk. Attaching a disk does not format, mount or back it up. Choose and validate the host's persistent storage before installing the application; keep any existing data intact during migration.

Use the admin profile to import and verify a prepared bundle. Keep the service behind private host access. [The setup guide](../README.md#run-the-application) owns the commands; [operations](../private-deployment/ROLLOUT.md#operate-and-recover) owns recovery considerations. Cloud resource creation and a complete fresh-host application install were not executed during the source refactor.
