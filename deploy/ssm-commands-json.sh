#!/usr/bin/env bash
# Encode a shell script as the AWS-RunShellScript `commands` StringList.
#
# Must be a single array element (the whole script), not split by newline.
# Line-splitting makes `#!/bin/bash` its own command.
set -euo pipefail
script_path="${1:?script path required}"
jq -Rs '[.]' "$script_path"
