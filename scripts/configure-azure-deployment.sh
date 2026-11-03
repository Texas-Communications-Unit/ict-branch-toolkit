#!/usr/bin/env bash
# One-time Azure administrator setup. No application deployment or NSG changes.
set -euo pipefail
umask 077

if [[ $# != 3 ]]; then
  echo 'Usage: configure-azure-deployment.sh <resource-group> <vm-name> <private-output.json>' >&2
  exit 2
fi
resource_group="$1"
vm_name="$2"
output_file="$3"
repository='Texas-Communications-Unit/ict-branch-toolkit'
environment='shared-test'
identity_name="${vm_name}-github-deploy"

# Use GitHub's effective prefix, including permanent IDs when enabled. Never
# guess the legacy name-only subject or change GitHub's identity settings.
oidc_prefix="$(gh api "repos/$repository/actions/oidc/customization/sub" --jq \
  'if .use_default == true and (.sub_claim_prefix | type) == "string" then .sub_claim_prefix else error("Unsupported OIDC template or missing effective prefix") end')"
immutable_prefix_pattern="^repo:${repository%/*}@[0-9]+/${repository#*/}@[0-9]+$"
if [[ "$oidc_prefix" != "repo:$repository" && ! "$oidc_prefix" =~ $immutable_prefix_pattern ]]; then
  echo 'GitHub returned an unexpected OIDC subject prefix; no Azure changes made.' >&2
  exit 1
fi
oidc_subject="${oidc_prefix}:environment:${environment}"

subscription="$(az account show --query id -o tsv)"
tenant="$(az account show --query tenantId -o tsv)"
vm_id="$(az vm show -g "$resource_group" -n "$vm_name" --query id -o tsv)"
location="$(az vm show -g "$resource_group" -n "$vm_name" --query location -o tsv)"
group_id="${vm_id%/providers/Microsoft.Compute/virtualMachines/*}"

if [[ "$(az provider show -n Microsoft.ManagedIdentity --query registrationState -o tsv)" != Registered ]]; then
  az provider register -n Microsoft.ManagedIdentity --wait -o none
fi

if ! az identity show -g "$resource_group" -n "$identity_name" -o none 2>/dev/null; then
  az identity create -g "$resource_group" -n "$identity_name" --location "$location" -o none
fi
client="$(az identity show -g "$resource_group" -n "$identity_name" --query clientId -o tsv)"
principal="$(az identity show -g "$resource_group" -n "$identity_name" --query principalId -o tsv)"

# Environment subject is intentional: GitHub must restrict this environment to
# main and require human approval. Do not attach this identity to the VM.
az identity federated-credential create \
  -g "$resource_group" --identity-name "$identity_name" \
  --name github-shared-test \
  --issuer https://token.actions.githubusercontent.com \
  --subject "$oidc_subject" \
  --audiences api://AzureADTokenExchange -o none

temporary="$(mktemp -d)"
trap 'rm -rf -- "$temporary"' EXIT
export ICT_AZURE_VM_ID="$vm_id" ICT_AZURE_GROUP_ID="$group_id"
python3 - "$temporary/role.json" <<'PY'
import json
import os
import sys
role = {
    'Name': 'ICT Toolkit managed deployment ' + os.environ['ICT_AZURE_VM_ID'].rsplit('/', 1)[-1],
    'IsCustom': True,
    'Description': 'Read one Toolkit VM and execute managed deployment commands; assignment must be VM scoped.',
    'Actions': [
        'Microsoft.Compute/virtualMachines/read',
        'Microsoft.Compute/virtualMachines/runCommands/read',
        'Microsoft.Compute/virtualMachines/runCommands/write',
        'Microsoft.Compute/virtualMachines/runCommands/delete',
    ],
    'NotActions': [], 'DataActions': [], 'NotDataActions': [],
    'AssignableScopes': [os.environ['ICT_AZURE_GROUP_ID']],
}
with open(sys.argv[1], 'w') as handle:
    json.dump(role, handle)
PY
role_name="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["Name"])' "$temporary/role.json")"
if [[ "$(az role definition list --name "$role_name" --query 'length(@)' -o tsv)" == 0 ]]; then
  az role definition create --role-definition "@$temporary/role.json" -o none
else
  # Do not silently reuse a role whose permissions differ from this contract.
  az role definition list --name "$role_name" -o json > "$temporary/existing.json"
  python3 - "$temporary/role.json" "$temporary/existing.json" <<'PY'
import json
import sys
expected = json.load(open(sys.argv[1]))
existing = json.load(open(sys.argv[2]))[0]
assert existing['assignableScopes'] == expected['AssignableScopes'], 'Existing role scope differs'
permissions = existing['permissions']
assert len(permissions) == 1, 'Existing role permission blocks differ'
for key in ('actions', 'notActions', 'dataActions', 'notDataActions'):
    assert sorted(permissions[0].get(key, [])) == sorted(expected[key[0].upper() + key[1:]]), 'Existing role permissions differ'
PY
fi
az role assignment create --assignee-object-id "$principal" \
  --assignee-principal-type ServicePrincipal --role "$role_name" --scope "$vm_id" -o none

export ICT_AZURE_CLIENT="$client" ICT_AZURE_TENANT="$tenant" ICT_AZURE_SUBSCRIPTION="$subscription"
export ICT_AZURE_RESOURCE_GROUP="$resource_group" ICT_AZURE_VM="$vm_name"
python3 - "$output_file" <<'PY'
import json
import os
import sys
values = {
    'AZURE_CLIENT_ID': os.environ['ICT_AZURE_CLIENT'],
    'AZURE_TENANT_ID': os.environ['ICT_AZURE_TENANT'],
    'AZURE_SUBSCRIPTION_ID': os.environ['ICT_AZURE_SUBSCRIPTION'],
    'AZURE_RESOURCE_GROUP': os.environ['ICT_AZURE_RESOURCE_GROUP'],
    'AZURE_VM_NAME': os.environ['ICT_AZURE_VM'],
}
descriptor = os.open(sys.argv[1], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, 'w') as handle:
    json.dump(values, handle)
PY
echo 'Azure identity configured. Import the private output values as shared-test environment secrets.'
