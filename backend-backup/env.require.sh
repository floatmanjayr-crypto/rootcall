# Usage: . ./env.require.sh VAR1 VAR2 ...
for v in "$@"; do
  eval "val=\${$v:-}"
  if [ -z "$val" ]; then
    echo "Missing required env: $v" >&2
    exit 1
  fi
done
