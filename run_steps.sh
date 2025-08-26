#!/bin/bash

# This script safely executes a series of bash commands passed as a JSON array.
# It respects timeouts, enforces an execution policy, and returns a structured JSON result.

set -e # Exit immediately if a command exits with a non-zero status.

# --- Configuration ---
POLICY_FILE="exec_policy.json"

# --- Input Validation ---
if [ -z "$1" ]; then
  echo '{"error": "No JSON input provided."}'
  exit 1
fi
STEPS_JSON="$1"

# --- Load Policy ---
if [ ! -f "$POLICY_FILE" ]; then
  echo "{\"error\": \"Execution policy file not found at ${POLICY_FILE}\"}"
  exit 1
fi
POLICY_JSON=$(cat "$POLICY_FILE")
ALLOWED_BINS=$(echo "$POLICY_JSON" | grep '"allow_bins"' | sed 's/.*\[\(.*\)\].*/\1/' | sed 's/"//g' | sed 's/,/ /g')
ALLOWED_NET_BINS=$(echo "$POLICY_JSON" | grep '"allow_net_bins"' | sed 's/.*\[\(.*\)\].*/\1/' | sed 's/"//g' | sed 's/,/ /g')

# --- State Initialization ---
SUCCESS_STEPS=()
FAILED_STEPS=()
REPORT_MD="# Execution Report: $(date -uIs)\n\n"

# --- Main Execution Loop ---
# We use `jq` to parse the JSON. It's a safe bet to have it in the Docker image.
# If not available, a more complex bash parsing would be needed.
# For now, let's assume a minimal Docker image might not have it and use a simple loop.
# A robust solution would ensure jq is in the Dockerfile.
# This pure-bash parser is a simplified fallback.
CLEAN_JSON=$(echo "$STEPS_JSON" | sed 's/\\"/###/g' | sed 's/"/ /g' | sed 's/###/"/g')

while IFS= read -r line; do
    if [[ ! "$line" =~ "title" ]]; then continue; fi

    title=$(echo "$line" | grep -o 'title: *"[^"]*"' | sed 's/title: *"//;s/"//')
    bash_cmd=$(echo "$line" | grep -o 'bash: *"[^"]*"' | sed 's/bash: *"//;s/"//')
    timeout_sec=$(echo "$line" | grep -o 'timeout_sec: *[0-9]*' | grep -o '[0-9]*')
    allow_net=$(echo "$line" | grep -o 'allow_net: *[^,]*' | sed 's/allow_net: *//')
    
    # Defaults
    timeout_sec=${timeout_sec:-60}
    allow_net=${allow_net:-false}
    
    # --- Policy Enforcement ---
    first_word=$(echo "$bash_cmd" | awk '{print $1}')
    is_allowed=false
    
    for bin in $ALLOWED_BINS; do
        if [[ "$first_word" == "$bin" ]]; then
            is_allowed=true
            break
        fi
    done
    
    if [[ "$allow_net" == "true" ]]; then
        for bin in $ALLOWED_NET_BINS; do
            if [[ "$first_word" == "$bin" ]]; then
                is_allowed=true
                break
            fi
        done
    elif [[ "$allow_net" != "true" ]]; then
         for bin in $ALLOWED_NET_BINS; do
            if [[ "$first_word" == "$bin" ]]; then
                is_allowed=false # Deny net command if allow_net is not explicitly true
                break
            fi
        done
    fi

    if [[ "$is_allowed" == "false" ]]; then
        stderr="Execution denied by policy. Command '${first_word}' is not in the allowed list."
        step_result="{\"title\":\"$title\",\"exit_code\":-1,\"stdout\":\"\",\"stderr\":\"$stderr\"}"
        FAILED_STEPS+=("$step_result")
        REPORT_MD+="## ❌ FAILED (Policy): $title\n\`\`\`bash\n$bash_cmd\n\`\`\`\n**Stderr:**\n$stderr\n\n"
        continue
    fi

    # --- Execute with Timeout ---
    # We create a subshell to run the command.
    output=$( (timeout "$timeout_sec" bash -c "$bash_cmd") 2>&1 )
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        step_result="{\"title\":\"$title\",\"exit_code\":0,\"stdout\":\"$(echo "$output" | sed 's/"/\\"/g' | tr -d '\n')\",\"stderr\":\"\"}"
        SUCCESS_STEPS+=("$step_result")
        REPORT_MD+="## ✅ SUCCESS: $title\n\`\`\`bash\n$bash_cmd\n\`\`\`\n**Stdout:**\n$output\n\n"
    elif [ $exit_code -eq 124 ]; then
        stderr="Command timed out after ${timeout_sec} seconds."
        step_result="{\"title\":\"$title\",\"exit_code\":124,\"stdout\":\"\",\"stderr\":\"$stderr\"}"
        FAILED_STEPS+=("$step_result")
        REPORT_MD+="## ❌ FAILED (Timeout): $title\n\`\`\`bash\n$bash_cmd\n\`\`\`\n**Stderr:**\n$stderr\n\n"
    else
        stderr=$(echo "$output" | sed 's/"/\\"/g' | tr -d '\n')
        step_result="{\"title\":\"$title\",\"exit_code\":$exit_code,\"stdout\":\"\",\"stderr\":\"$stderr\"}"
        FAILED_STEPS+=("$step_result")
        REPORT_MD+="## ❌ FAILED (Exit Code $exit_code): $title\n\`\`\`bash\n$bash_cmd\n\`\`\`\n**Stderr:**\n$output\n\n"
    fi

done <<< "$CLEAN_JSON"

# --- Final Output ---
SUCCESS_JSON=$(IFS=,; echo "${SUCCESS_STEPS[*]}")
FAILED_JSON=$(IFS=,; echo "${FAILED_STEPS[*]}")
REPORT_MD_JSON=$(echo "$REPORT_MD" | sed 's/"/\\"/g' | tr '\n' ' ')

echo "{"
echo "\"success\": [${SUCCESS_JSON}],"
echo "\"failed\": [${FAILED_JSON}],"
echo "\"final_report_md\": \"${REPORT_MD_JSON}\""
echo "}"
