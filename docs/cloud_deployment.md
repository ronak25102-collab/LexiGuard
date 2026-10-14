# Apply the verified cloud configuration to a hosted deployment

The new Aura instance is populated and was tested through the normal API and the
live ablation. These checks do not redeploy an existing Render service.

The prepared `render.yaml` now uses `NEO4J_USERNAME` (the old `NEO4J_USER` was ignored),
selects the working generation provider, keeps Google embeddings separate, and
includes the frontend route rewrite. Docker excludes private credentials and
evaluation caches from the build context.

When deploying this version, configure the backend's environment with your actual
Aura URI, username, password, CodeCraft key and Google key. Keep
`LLM_PROVIDER=codecraft`, `CODECRAFT_MODEL=gpt-5.6-luna` and
`EMBEDDING_PROVIDER=google` for the validated application configuration. The
benchmark's NVIDIA judge key is needed only for scoring, not serving queries.
Credentials are intentionally absent from these documents and the review package.

A hosted Chroma collection must be restored independently of Aura. A free service
with ephemeral storage loses local indexes and parsed sources across rebuilds.
Use existing persistent storage if available, or explicitly rebuild the same
Google embedding collection from saved Markdown after each deployment. The saved
Chroma SQLite file in older repository history is not the newly indexed collection.
Do not present graph-only degraded retrieval as the measured hybrid configuration.

Before sharing the hosted demo, verify `/health`, `/config/validate`, `/contracts`,
`/graph/stats`, and a source-grounded `/process` response. Health verifies Aura
connectivity; it does not establish that the semantic index is populated. Check
the restored Chroma collection count separately (386 for the full saved corpus).
The local review package includes the source corpus and restoration scripts.
