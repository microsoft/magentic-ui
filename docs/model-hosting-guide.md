# Model Hosting Guide

MagenticLite talks to models through an **OpenAI-compatible `/v1/chat/completions` endpoint**. This guide walks through hosting the recommended models with **Microsoft Foundry Managed Compute** on Azure.

After deployment, you end up with three values to paste into MagenticLite's onboarding (or into **Settings → Models**): an OpenAI-compatible URL, a model name, and an API key.

> **Each model needs its own endpoint.** MagenticLite uses one model for the orchestrator role and another for browser use. In Foundry, that means **two deployments**, each with its own URL and key.

---

## Microsoft Foundry Managed Compute

### Prerequisites

- An [Azure subscription](https://azure.microsoft.com/free/) with a valid payment method. Free and trial subscriptions don't work for GPU deployments.
- A **hub-based** project in Foundry. The newer "Foundry project" type does not support Managed Compute. If you don't have one, create it from the [Foundry portal](https://ai.azure.com/) under **+ New project → Hub-based project**. Pick a region with H100 or A100 inventory (East US 2 and Sweden Central are good defaults).
- Quota for at least one GPU SKU large enough to host the models. **Standard_NC24ads_A100_v4** is a good default for both [Fara1.5-9B](https://aka.ms/fara-foundry) and [MagenticBrain](https://aka.ms/MagenticBrain-foundry) for testing and typical single-user use. In [Azure Quotas](https://portal.azure.com/#view/Microsoft_Azure_Capacity/QuotaMenuBlade/~/overview), select **Machine learning**, then request **Standard NCADSA100v4 Family Cluster Dedicated vCPUs** in the same region as your Foundry project. Larger A100 or H100 SKUs also work if you want extra headroom or have them readily available, but they cost more. Approval can take 24–48 hours.

### 1. Deploy the model

You'll repeat this once per model role you want to use (browser use and/or orchestrator).

1. Open the model card in [Foundry Explore models](https://ai.azure.com/explore/models): [Fara1.5-9B](https://aka.ms/fara-foundry) for browser use or [MagenticBrain-14B](https://aka.ms/MagenticBrain-foundry) for orchestration.

2. On the model card, click **Use this model**. If Foundry asks you to select a project, choose an existing hub-based project or create a new one. For a new project, keep the default hub unless you already have a shared hub for this work, and pick a region with GPU inventory such as East US 2 or Sweden Central.

   If project creation fails with a `Microsoft.Resources/subscriptions/resourcegroups/write` authorization error, your account can see the model but cannot create the Azure resource group behind the Foundry project. Use an existing project where you have access, or ask the subscription owner to grant you a role such as Contributor on the subscription or target resource group, then refresh your credentials and try again.

3. Continue to the deployment wizard. If you're presented with purchase options, pick **Managed Compute**.

4. Configure the deployment:

   | Field           | Value                                                                                                      |
   | --------------- | ---------------------------------------------------------------------------------------------------------- |
   | Endpoint name   | anything, e.g. `fara-15-9b-magentic-lite`. Becomes part of the URL.                                        |
   | Deployment name | anything, e.g. `fara1-5-9b-1` or `magenticbrain-14b-1`. This is for tracking the deployment in Foundry.    |
   | Virtual machine | **Standard_NC24ads_A100_v4**. Larger A100 or H100 SKUs also work, but they are usually unnecessary for testing. |
   | Instance count  | **1**. Foundry may default to 3 instances; reduce it to 1 for testing or typical single-user use to avoid unnecessary cost. |

   Both Fara and MagenticBrain are served by vLLM under the hood, so the deployed endpoint exposes a fully OpenAI-compatible `/v1/chat/completions` route — text and vision-language requests both work.

5. Click **Deploy**.

   Provisioning takes ~15–20 minutes per model: Foundry allocates the VM, pulls the container, and warms up vLLM. **Billing starts when the VM is allocated**, not when the endpoint reaches `Healthy`.

### 2. Connect MagenticLite

For each deployment, open **Models + endpoints** in your Foundry project and click into the deployment:

- **REST endpoint** (Details tab): copy the endpoint through `/v1`, for example `https://<endpoint-name>.<region>.inference.ml.azure.com/v1`.
- **Model ID** (deployment details): use the model name segment after `/models/`, for example `Fara1.5-9B` or `MagenticBrain-14B`. Do not use the deployment name here.
- **Primary key** (Consume tab): the API key Foundry generated for that endpoint.

Open MagenticLite and fill in the **Browser use model** card (and/or the **Orchestrator** card). On first launch this is part of the onboarding flow; if you've already onboarded, find the same fields under **Settings → Models**.

| Field        | Browser use model (Fara)                                      | Orchestrator model (MagenticBrain)                             |
| ------------ | ------------------------------------------------------------- | -------------------------------------------------------------- |
| Endpoint URL | `https://<fara-endpoint>.<region>.inference.ml.azure.com/v1`  | `https://<brain-endpoint>.<region>.inference.ml.azure.com/v1`  |
| Model Name   | `Fara1.5-9B`                                                  | `MagenticBrain-14B`                                            |
| API Key      | the primary key from the Fara endpoint's Consume tab          | the primary key from the MagenticBrain endpoint's Consume tab  |

Click **Verify & Save**. See [Verification fails](#verification-fails) below if you hit an error.

### 3. Idle behavior and cost

Foundry Managed Compute deployments **do not scale to zero**. The VM stays allocated and billed by the hour for as long as the deployment exists, whether or not traffic is flowing. An A100 deployment in East US 2 runs roughly $3–4 per hour at list price (H100 is roughly twice that); check the [Azure VM pricing page](https://azure.microsoft.com/pricing/details/virtual-machines/linux/) for current rates in your region. Multiply by the number of deployments you keep running.

To stop the meter, **delete the deployment** from the **Models + endpoints** page. Redeploying from the catalog later takes the same ~15–20 minutes.

---

## Verification fails

When you click **Verify & Save**, MagenticLite sends a probe request to the endpoint:

- During onboarding, a successful verification finishes the onboarding flow and sends you to the sample-tasks page.
- In Settings, the button updates to **Connection Verified** (with a check icon) once the endpoint responds.

If verification fails, the banner usually pinpoints the problem:

| Symptom (banner)                                                      | Likely cause                                                                                            |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `Endpoint returned HTTP 401` or `403`                                 | API Key field is empty or wrong (different endpoints return one or the other for the same problem)      |
| `Connection refused — is the server running?` or other network errors | Endpoint URL is wrong (typo in the host, missing `https://`, VPN/firewall issue)                        |
