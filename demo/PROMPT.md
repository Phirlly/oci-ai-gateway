# Presenter script

1. After **Ready**, open Compare and sign in with the reported username and
   generated Resource Manager password (or GitHub's `DEMO_PASSWORD`).
2. Select enabled models: `oci-managed`, `external-anthropic`, `external-openai`.
   Compare starts with two panels. For one model, remove the duplicate panel;
   for three, add a third panel. Disabled providers do not appear.
3. Submit:

   > Classify this support request as BILLING, ACCESS or TECHNICAL. Reply with
   > exactly one category: My invoice contains the same charge twice.

4. Each selected model should return **BILLING**. With multiple models, compare
   their responses and streaming. Explain that one gateway running on OCI routes
   requests to the selected model services using a common interface.
5. To repeat automated checks, increase Resource Manager's `verification_run`
   and Apply, or choose GitHub's **Verify samples**. Verification covers only
   enabled models. Unknown usage/cost is not presented as a measured value.
